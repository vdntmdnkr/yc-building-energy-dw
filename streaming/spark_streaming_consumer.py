"""
spark_streaming_consumer.py
============================
PySpark Structured Streaming consumer for the NYC Building Energy real-time
simulation pipeline.

This application:
  1. Reads JSON events from Kafka topic "building_energy_benchmarks"
  2. Parses and validates each event (quality_exception flag)
  3. Derives GHGIntensityRealtime = GHGEmissions / GrossFloorArea
  4. Applies event-time tumbling-window (1 min) aggregations
  5. Computes borough-level and property-type-level window stats
  6. Raises a performance_alert when avg SiteEUI > 150 in any window
  7. Writes raw events, KPI aggregates, borough stats, and exceptions to ClickHouse
  8. Also prints all streams to console for demo/debugging

ClickHouse JDBC URL (env var or default):
    CLICKHOUSE_JDBC_URL=jdbc:clickhouse://localhost:8123/building_energy_rt

Kafka bootstrap servers:
    KAFKA_BOOTSTRAP_SERVERS=localhost:9092

Usage:
    spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0,\\
                            com.clickhouse:clickhouse-jdbc:0.6.0-patch5 \\
                 spark_streaming_consumer.py
"""
from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# PySpark imports — guard for environments without Spark
# ---------------------------------------------------------------------------
try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    from pyspark.sql.types import (
        BooleanType,
        DoubleType,
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )
except ImportError:
    print("ERROR: PySpark is not installed. Run: pip install pyspark>=3.4.0")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration (from env or defaults)
# ---------------------------------------------------------------------------
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = "building_energy_benchmarks"

CLICKHOUSE_JDBC_URL = os.environ.get(
    "CLICKHOUSE_JDBC_URL",
    "jdbc:clickhouse://localhost:8123/building_energy_rt",
)
CLICKHOUSE_DRIVER = "com.clickhouse.jdbc.ClickHouseDriver"

CHECKPOINT_BASE = "/tmp/spark_checkpoint_building_energy"
WATERMARK_DELAY = "2 minutes"
WINDOW_DURATION = "1 minute"
SLIDE_DURATION  = "1 minute"           # tumbling (slide == window)

PERF_ALERT_EUI_THRESHOLD = 150.0

# ---------------------------------------------------------------------------
# JSON schema matching the producer event structure
# ---------------------------------------------------------------------------
EVENT_SCHEMA = StructType([
    StructField("event_id",             StringType(),    nullable=True),
    StructField("event_timestamp",      StringType(),    nullable=True),   # ISO8601 → cast to timestamp
    StructField("simulation_note",      StringType(),    nullable=True),
    StructField("PropertyID",           StringType(),    nullable=True),
    StructField("PropertyName",         StringType(),    nullable=True),
    StructField("Borough",              StringType(),    nullable=True),
    StructField("PrimaryPropertyType",  StringType(),    nullable=True),
    StructField("PropertyTypeGroup",    StringType(),    nullable=True),
    StructField("ReportingYear",        IntegerType(),   nullable=True),
    StructField("GrossFloorArea",       DoubleType(),    nullable=True),
    StructField("SiteEUI",              DoubleType(),    nullable=True),
    StructField("SourceEUI",            DoubleType(),    nullable=True),
    StructField("GHGEmissions",         DoubleType(),    nullable=True),
    StructField("WaterUse",             DoubleType(),    nullable=True),
    StructField("EnergyStarScore",      DoubleType(),    nullable=True),
    StructField("IsHighEnergyBuilding", IntegerType(),   nullable=True),
    StructField("IsHighGHGBuilding",    IntegerType(),   nullable=True),
    StructField("EnergyIntensityBand",  StringType(),    nullable=True),
    StructField("BuildingSizeBand",     StringType(),    nullable=True),
])

# Fields that must be non-null for a record to be valid
REQUIRED_FIELDS = [
    "event_id", "PropertyID", "Borough",
    "GrossFloorArea", "SiteEUI", "GHGEmissions",
]

# ---------------------------------------------------------------------------
# ClickHouse JDBC write helper
# ---------------------------------------------------------------------------
def write_to_clickhouse(batch_df, batch_id: int, table: str):
    """
    Micro-batch foreachBatch sink: writes each micro-batch to a ClickHouse table
    via JDBC.  Silently skips empty batches.
    """
    if batch_df.rdd.isEmpty():
        return
    try:
        (
            batch_df.write
            .format("jdbc")
            .option("url", CLICKHOUSE_JDBC_URL)
            .option("dbtable", table)
            .option("driver", CLICKHOUSE_DRIVER)
            .mode("append")
            .save()
        )
        print(f"[ClickHouse] batch_id={batch_id}  table={table}  rows={batch_df.count()}")
    except Exception as exc:
        # Log but do not crash the streaming query
        print(f"[ClickHouse ERROR] batch_id={batch_id} table={table}: {exc}")


# ---------------------------------------------------------------------------
# Main streaming application
# ---------------------------------------------------------------------------
def build_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("NYC_BuildingEnergy_StreamingConsumer")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.sql.streaming.schemaInference", "false")
        # Kafka connector package should be supplied via spark-submit --packages
        .getOrCreate()
    )


def main():
    spark = build_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    print("=" * 70)
    print("  NYC Building Energy — PySpark Structured Streaming Consumer")
    print("  *** REAL-TIME SIMULATION MODE ***")
    print(f"  Kafka  : {KAFKA_BOOTSTRAP_SERVERS} / topic={KAFKA_TOPIC}")
    print(f"  CH JDBC: {CLICKHOUSE_JDBC_URL}")
    print(f"  Window : {WINDOW_DURATION} tumbling  |  Watermark: {WATERMARK_DELAY}")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # 1. Read raw bytes from Kafka
    # -----------------------------------------------------------------------
    raw_kafka = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    # -----------------------------------------------------------------------
    # 2. Parse JSON payload
    # -----------------------------------------------------------------------
    parsed = (
        raw_kafka
        .selectExpr("CAST(value AS STRING) AS json_str",
                    "timestamp AS kafka_timestamp")
        .select(
            F.from_json(F.col("json_str"), EVENT_SCHEMA).alias("data"),
            F.col("kafka_timestamp"),
        )
        .select("data.*", "kafka_timestamp")
    )

    # Cast event_timestamp string → proper Spark TimestampType
    parsed = parsed.withColumn(
        "event_timestamp",
        F.to_timestamp(F.col("event_timestamp"))
    )

    # -----------------------------------------------------------------------
    # 3. Quality validation
    #    quality_exception = True if any required field is null
    # -----------------------------------------------------------------------
    quality_check = F.lit(False)
    for field in REQUIRED_FIELDS:
        quality_check = quality_check | F.col(field).isNull()

    validated = parsed.withColumn("quality_exception", quality_check.cast("integer"))

    issue_expr = F.concat_ws(
        "; ",
        *[
            F.when(F.col(f).isNull(), F.lit(f"NULL:{f}")).otherwise(F.lit(None))
            for f in REQUIRED_FIELDS
        ],
    )
    validated = validated.withColumn("issue_description", issue_expr)

    # -----------------------------------------------------------------------
    # 4. Derive streaming measures
    #    GHGIntensityRealtime = GHGEmissions / GrossFloorArea
    # -----------------------------------------------------------------------
    enriched = validated.withColumn(
        "GHGIntensityRealtime",
        F.when(
            (F.col("GrossFloorArea").isNotNull()) & (F.col("GrossFloorArea") > 0),
            F.col("GHGEmissions") / F.col("GrossFloorArea"),
        ).otherwise(F.lit(None).cast(DoubleType())),
    )

    # -----------------------------------------------------------------------
    # 5. Apply watermark for event-time processing
    # -----------------------------------------------------------------------
    watermarked = enriched.withWatermark("event_timestamp", WATERMARK_DELAY)

    # -----------------------------------------------------------------------
    # 6. Tumbling 1-minute window KPI aggregations
    # -----------------------------------------------------------------------
    kpi_agg = (
        watermarked
        .groupBy(
            F.window(F.col("event_timestamp"), WINDOW_DURATION)
        )
        .agg(
            F.count("*").alias("records_per_minute"),
            F.sum(
                F.when(
                    F.col("SiteEUI").isNotNull() & F.col("GrossFloorArea").isNotNull(),
                    F.col("SiteEUI") * F.col("GrossFloorArea"),
                ).otherwise(0.0)
            ).alias("total_energy_use"),
            F.sum(
                F.when(F.col("IsHighEnergyBuilding") == 1, 1).otherwise(0)
            ).alias("high_eui_count"),
            F.sum(
                F.when(F.col("GHGEmissions").isNotNull(), F.col("GHGEmissions")).otherwise(0.0)
            ).alias("total_ghg"),
            F.sum(F.col("quality_exception")).alias("quality_exceptions"),
            F.avg(
                F.when(F.col("SiteEUI").isNotNull(), F.col("SiteEUI"))
            ).alias("avg_site_eui"),
        )
        .select(
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            "records_per_minute",
            "total_energy_use",
            "high_eui_count",
            "total_ghg",
            "quality_exceptions",
            "avg_site_eui",
            F.when(F.col("avg_site_eui") > PERF_ALERT_EUI_THRESHOLD, 1)
             .otherwise(0)
             .cast("integer")
             .alias("performance_alert"),
        )
    )

    # -----------------------------------------------------------------------
    # 7. Borough-level window aggregation
    # -----------------------------------------------------------------------
    borough_agg = (
        watermarked
        .groupBy(
            F.window(F.col("event_timestamp"), WINDOW_DURATION),
            F.col("Borough"),
        )
        .agg(
            F.count("*").alias("record_count"),
            F.avg(
                F.when(F.col("SiteEUI").isNotNull(), F.col("SiteEUI"))
            ).alias("avg_site_eui"),
            F.sum(
                F.when(F.col("GHGEmissions").isNotNull(), F.col("GHGEmissions")).otherwise(0.0)
            ).alias("total_ghg"),
            F.sum(
                F.when(F.col("IsHighEnergyBuilding") == 1, 1).otherwise(0)
            ).alias("high_eui_count"),
        )
        .select(
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            "Borough",
            "record_count",
            "avg_site_eui",
            "total_ghg",
            "high_eui_count",
        )
    )

    # -----------------------------------------------------------------------
    # 8. PropertyType-level window aggregation
    # -----------------------------------------------------------------------
    proptype_agg = (
        watermarked
        .groupBy(
            F.window(F.col("event_timestamp"), WINDOW_DURATION),
            F.col("PropertyTypeGroup"),
        )
        .agg(
            F.count("*").alias("record_count"),
            F.avg(
                F.when(F.col("SiteEUI").isNotNull(), F.col("SiteEUI"))
            ).alias("avg_site_eui"),
            F.sum(
                F.when(F.col("GHGEmissions").isNotNull(), F.col("GHGEmissions")).otherwise(0.0)
            ).alias("total_ghg"),
        )
        .select(
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            "PropertyTypeGroup",
            "record_count",
            "avg_site_eui",
            "total_ghg",
        )
    )

    # -----------------------------------------------------------------------
    # 9. Quality exceptions stream
    # -----------------------------------------------------------------------
    exceptions_stream = (
        enriched
        .filter(F.col("quality_exception") == 1)
        .select(
            "event_id",
            "event_timestamp",
            "PropertyID",
            "Borough",
            "issue_description",
        )
    )

    # -----------------------------------------------------------------------
    # 10. Columns to write for raw events (match ClickHouse DDL)
    # -----------------------------------------------------------------------
    raw_events_cols = [
        "event_id", "event_timestamp", "simulation_note",
        "PropertyID", "PropertyName", "Borough",
        "PrimaryPropertyType", "PropertyTypeGroup",
        "ReportingYear",
        "GrossFloorArea", "SiteEUI", "SourceEUI",
        "GHGEmissions", "WaterUse", "EnergyStarScore",
        "IsHighEnergyBuilding", "IsHighGHGBuilding",
        "EnergyIntensityBand", "BuildingSizeBand",
        "GHGIntensityRealtime", "quality_exception",
    ]
    raw_events = enriched.select(*raw_events_cols)

    # -----------------------------------------------------------------------
    # 11. Write streams
    # -----------------------------------------------------------------------

    # -- 11a. Raw events → ClickHouse (foreachBatch)
    q_raw = (
        raw_events.writeStream
        .foreachBatch(lambda df, bid: write_to_clickhouse(df, bid, "building_energy_events"))
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/raw_events")
        .outputMode("append")
        .trigger(processingTime="10 seconds")
        .queryName("raw_events_to_clickhouse")
        .start()
    )

    # -- 11b. KPI aggregates → ClickHouse (foreachBatch)
    q_kpi = (
        kpi_agg.writeStream
        .foreachBatch(lambda df, bid: write_to_clickhouse(df, bid, "building_energy_kpis"))
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/kpis")
        .outputMode("update")
        .trigger(processingTime="30 seconds")
        .queryName("kpi_to_clickhouse")
        .start()
    )

    # -- 11c. Borough stats → ClickHouse
    q_borough = (
        borough_agg.writeStream
        .foreachBatch(lambda df, bid: write_to_clickhouse(df, bid, "building_energy_borough_stats"))
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/borough_stats")
        .outputMode("update")
        .trigger(processingTime="30 seconds")
        .queryName("borough_to_clickhouse")
        .start()
    )

    # -- 11d. Property-type stats → ClickHouse
    q_proptype = (
        proptype_agg.writeStream
        .foreachBatch(lambda df, bid: write_to_clickhouse(df, bid, "building_energy_property_type_stats"))
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/proptype_stats")
        .outputMode("update")
        .trigger(processingTime="30 seconds")
        .queryName("proptype_to_clickhouse")
        .start()
    )

    # -- 11e. Quality exceptions → ClickHouse
    q_exceptions = (
        exceptions_stream.writeStream
        .foreachBatch(lambda df, bid: write_to_clickhouse(df, bid, "building_energy_exceptions"))
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/exceptions")
        .outputMode("append")
        .trigger(processingTime="10 seconds")
        .queryName("exceptions_to_clickhouse")
        .start()
    )

    # -- 11f. Console sinks for demo / debugging
    q_console_kpi = (
        kpi_agg.writeStream
        .outputMode("update")
        .format("console")
        .option("truncate", "false")
        .option("numRows", "20")
        .trigger(processingTime="30 seconds")
        .queryName("kpi_console")
        .start()
    )

    q_console_borough = (
        borough_agg.writeStream
        .outputMode("update")
        .format("console")
        .option("truncate", "false")
        .option("numRows", "10")
        .trigger(processingTime="30 seconds")
        .queryName("borough_console")
        .start()
    )

    q_console_exc = (
        exceptions_stream.writeStream
        .outputMode("append")
        .format("console")
        .option("truncate", "false")
        .option("numRows", "10")
        .trigger(processingTime="10 seconds")
        .queryName("exceptions_console")
        .start()
    )

    print("\n[INFO] All streaming queries started. Waiting for termination ...")
    print("       Press Ctrl-C to stop.\n")

    # Wait for all queries; handle keyboard interrupt gracefully
    try:
        spark.streams.awaitAnyTermination()
    except KeyboardInterrupt:
        print("\n[INFO] Stopping streaming queries ...")
        for q in [
            q_raw, q_kpi, q_borough, q_proptype, q_exceptions,
            q_console_kpi, q_console_borough, q_console_exc,
        ]:
            q.stop()
        print("[INFO] All queries stopped.")

    spark.stop()


if __name__ == "__main__":
    main()
