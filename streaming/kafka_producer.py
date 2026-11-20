"""
kafka_producer.py
=================
REAL-TIME SIMULATION: Replays NYC Building Energy (Local Law 84) historical records
as live Kafka events, ordered chronologically by ReportingYear then PropertyID.

NOTE: This is a SIMULATION of real-time streaming using historical data.
      No live sensor data is involved.

Usage:
    python kafka_producer.py [--speed RECORDS_PER_SEC] [--csv PATH_TO_CSV]

Environment Variables:
    KAFKA_BOOTSTRAP_SERVERS  (default: localhost:9092)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import pandas as pd

try:
    from kafka import KafkaProducer
    from kafka.errors import KafkaError, NoBrokersAvailable
except ImportError:
    print("ERROR: kafka-python not installed. Run: pip install kafka-python")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TOPIC = "building_energy_benchmarks"
BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DEFAULT_CSV = os.path.join(
    os.path.dirname(__file__), "..", "data", "curated", "nyc_building_energy_curated.csv"
)
SIMULATION_NOTE = "REAL-TIME SIMULATION: historical record replayed as live event"


# ---------------------------------------------------------------------------
# Helper: safe float
# ---------------------------------------------------------------------------
def safe_float(val, default=None):
    try:
        f = float(val)
        return None if (f != f) else f          # NaN → None
    except (TypeError, ValueError):
        return default


def safe_int(val, default=None):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Build event dict from a DataFrame row
# ---------------------------------------------------------------------------
def row_to_event(row: pd.Series) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "simulation_note": SIMULATION_NOTE,
        # --- Identifier fields ---
        "PropertyID": str(row.get("PropertyID", "")),
        "PropertyName": str(row.get("PropertyName", "")),
        "Borough": str(row.get("Borough", "")),
        "PrimaryPropertyType": str(row.get("PrimaryPropertyType", "")),
        "PropertyTypeGroup": str(row.get("PropertyTypeGroup", "")),
        # --- Temporal ---
        "ReportingYear": safe_int(row.get("ReportingYear"), 0),
        # --- Energy / Area metrics ---
        "GrossFloorArea": safe_float(row.get("GrossFloorArea")),
        "SiteEUI": safe_float(row.get("SiteEUI")),
        "SourceEUI": safe_float(row.get("SourceEUI")),
        "GHGEmissions": safe_float(row.get("GHGEmissions")),
        "WaterUse": safe_float(row.get("WaterUse")),
        "EnergyStarScore": safe_float(row.get("EnergyStarScore")),
        # --- Derived / flag fields ---
        "IsHighEnergyBuilding": safe_int(row.get("IsHighEnergyBuilding"), 0),
        "IsHighGHGBuilding": safe_int(row.get("IsHighGHGBuilding"), 0),
        "EnergyIntensityBand": str(row.get("EnergyIntensityBand", "")),
        "BuildingSizeBand": str(row.get("BuildingSizeBand", "")),
    }


# ---------------------------------------------------------------------------
# Main producer logic
# ---------------------------------------------------------------------------
def create_producer(bootstrap_servers: str) -> KafkaProducer:
    """Instantiate KafkaProducer with JSON serialisation."""
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        key_serializer=lambda k: str(k).encode("utf-8"),
        acks="all",
        retries=3,
        linger_ms=5,
    )


def load_data(csv_path: str) -> pd.DataFrame:
    print(f"[INFO] Loading curated dataset from: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"[INFO] Loaded {len(df):,} records. Sorting by ReportingYear, PropertyID ...")
    df = df.sort_values(
        by=["ReportingYear", "PropertyID"],
        ascending=[True, True],
        na_position="last",
    ).reset_index(drop=True)
    print(f"[INFO] Sort complete. Years range: {df['ReportingYear'].min()} – {df['ReportingYear'].max()}")
    return df


def run_producer(csv_path: str, speed: float, bootstrap_servers: str):
    """
    Stream all rows from the curated CSV to Kafka at `speed` records/second.
    """
    df = load_data(csv_path)
    sleep_interval = 1.0 / speed  # seconds between records

    print(f"\n{'='*60}")
    print("  *** REAL-TIME SIMULATION MODE ***")
    print(f"  Topic            : {TOPIC}")
    print(f"  Bootstrap servers: {bootstrap_servers}")
    print(f"  Records          : {len(df):,}")
    print(f"  Replay speed     : {speed} records/sec  (sleep={sleep_interval:.4f}s)")
    print(f"  Note             : {SIMULATION_NOTE}")
    print(f"{'='*60}\n")

    # Connect to Kafka (with retry)
    producer = None
    for attempt in range(1, 6):
        try:
            print(f"[INFO] Connecting to Kafka at {bootstrap_servers} (attempt {attempt}/5) ...")
            producer = create_producer(bootstrap_servers)
            print("[INFO] Kafka producer connected.\n")
            break
        except NoBrokersAvailable:
            print(f"[WARN] No brokers available. Retrying in 5s ...")
            time.sleep(5)
        except KafkaError as exc:
            print(f"[ERROR] Kafka error on connect: {exc}")
            time.sleep(5)

    if producer is None:
        print("[ERROR] Could not connect to Kafka after 5 attempts. Exiting.")
        sys.exit(1)

    sent = 0
    errors = 0
    start_time = time.time()

    try:
        for idx, row in df.iterrows():
            event = row_to_event(row)
            key = event["PropertyID"]

            try:
                future = producer.send(TOPIC, key=key, value=event)
                # Non-blocking; we periodically flush
                sent += 1

                if sent % 100 == 0:
                    producer.flush()
                    elapsed = time.time() - start_time
                    actual_rate = sent / elapsed if elapsed > 0 else 0
                    print(
                        f"[PROGRESS] Sent {sent:,}/{len(df):,} records  "
                        f"| Rate: {actual_rate:.1f} rec/s  "
                        f"| Errors: {errors}  "
                        f"| Last: PropertyID={key}, Year={event['ReportingYear']}"
                    )

            except KafkaError as exc:
                errors += 1
                print(f"[ERROR] Failed to send record {idx}: {exc}")

            time.sleep(sleep_interval)

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user. Flushing remaining messages ...")

    finally:
        producer.flush()
        producer.close()
        elapsed = time.time() - start_time
        print(f"\n[DONE] Simulation complete.")
        print(f"       Sent   : {sent:,} records")
        print(f"       Errors : {errors}")
        print(f"       Elapsed: {elapsed:.1f}s")
        print(f"       Avg rate: {sent/elapsed:.1f} rec/s" if elapsed > 0 else "")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "REAL-TIME SIMULATION: Replay NYC Building Energy historical data "
            "as Kafka events on topic 'building_energy_benchmarks'."
        )
    )
    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV,
        help="Path to curated CSV (default: ../data/curated/nyc_building_energy_curated.csv)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=10.0,
        help="Replay speed in records/second (default: 10)",
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=BOOTSTRAP_SERVERS,
        help="Kafka bootstrap servers (default: env KAFKA_BOOTSTRAP_SERVERS or localhost:9092)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_producer(
        csv_path=args.csv,
        speed=args.speed,
        bootstrap_servers=args.bootstrap_servers,
    )
