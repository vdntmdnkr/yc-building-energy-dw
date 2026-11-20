-- =============================================================================
-- clickhouse_setup.sql
-- ClickHouse DDL for the NYC Building Energy Real-Time Streaming pipeline
-- Project: TY B.Tech Data Warehouse — Local Law 84 (NYC Energy Benchmarking)
-- =============================================================================

CREATE DATABASE IF NOT EXISTS building_energy_rt;

-- Switch context to the real-time database
USE building_energy_rt;

-- -----------------------------------------------------------------------------
-- 1. Raw streaming events table
--    Every event emitted by the Kafka producer is written here.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS building_energy_events
(
    event_id              String,
    event_timestamp       DateTime,
    simulation_note       String,

    -- Building identifiers
    PropertyID            String,
    PropertyName          String          DEFAULT '',
    Borough               String,
    PrimaryPropertyType   String,
    PropertyTypeGroup     String,

    -- Temporal
    ReportingYear         Int32,

    -- Energy / area metrics
    GrossFloorArea        Float64,
    SiteEUI               Float64,
    SourceEUI             Float64,
    GHGEmissions          Float64,
    WaterUse              Float64,
    EnergyStarScore       Float64,

    -- Derived flag fields
    IsHighEnergyBuilding  Int8,
    IsHighGHGBuilding     Int8            DEFAULT 0,
    EnergyIntensityBand   String,
    BuildingSizeBand      String          DEFAULT '',

    -- Streaming-derived fields
    GHGIntensityRealtime  Float64         DEFAULT 0.0,   -- GHGEmissions / GrossFloorArea
    quality_exception     UInt8           DEFAULT 0,     -- 1 = failed quality check

    -- Housekeeping
    ingest_time           DateTime        DEFAULT now()
)
ENGINE = MergeTree()
ORDER BY (event_timestamp, Borough, PropertyTypeGroup)
PARTITION BY toYYYYMM(event_timestamp)
TTL event_timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;


-- -----------------------------------------------------------------------------
-- 2. 1-minute tumbling window KPI aggregates
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS building_energy_kpis
(
    window_start          DateTime,
    window_end            DateTime,

    records_per_minute    Int64,
    total_energy_use      Float64,     -- sum(SiteEUI * GrossFloorArea) ≈ kBtu
    high_eui_count        Int64,       -- count where IsHighEnergyBuilding = 1
    total_ghg             Float64,     -- sum(GHGEmissions) in tCO2e
    quality_exceptions    Int64,       -- count where quality_exception = 1

    avg_site_eui          Float64      DEFAULT 0.0,
    performance_alert     UInt8        DEFAULT 0   -- 1 when avg SiteEUI > 150
)
ENGINE = MergeTree()
ORDER BY window_start
PARTITION BY toYYYYMM(window_start)
TTL window_start + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;


-- -----------------------------------------------------------------------------
-- 3. Borough-level window aggregates
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS building_energy_borough_stats
(
    window_start          DateTime,
    window_end            DateTime     DEFAULT addMinutes(window_start, 1),
    Borough               String,

    record_count          Int64,
    avg_site_eui          Float64,
    total_ghg             Float64      DEFAULT 0.0,
    high_eui_count        Int64        DEFAULT 0
)
ENGINE = MergeTree()
ORDER BY (window_start, Borough)
PARTITION BY toYYYYMM(window_start)
TTL window_start + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;


-- -----------------------------------------------------------------------------
-- 4. Property-type-level window aggregates
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS building_energy_property_type_stats
(
    window_start          DateTime,
    window_end            DateTime     DEFAULT addMinutes(window_start, 1),
    PropertyTypeGroup     String,

    record_count          Int64,
    avg_site_eui          Float64      DEFAULT 0.0,
    total_ghg             Float64      DEFAULT 0.0
)
ENGINE = MergeTree()
ORDER BY (window_start, PropertyTypeGroup)
PARTITION BY toYYYYMM(window_start)
TTL window_start + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;


-- -----------------------------------------------------------------------------
-- 5. Quality exceptions log
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS building_energy_exceptions
(
    event_id              String,
    event_timestamp       DateTime,
    PropertyID            String,
    Borough               String       DEFAULT '',
    issue_description     String,
    ingest_time           DateTime     DEFAULT now()
)
ENGINE = MergeTree()
ORDER BY event_timestamp
PARTITION BY toYYYYMM(event_timestamp)
TTL event_timestamp + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;


-- -----------------------------------------------------------------------------
-- Useful views for Grafana dashboards
-- -----------------------------------------------------------------------------

-- Latest KPI snapshot (most recent completed window)
CREATE VIEW IF NOT EXISTS v_latest_kpis AS
SELECT *
FROM building_energy_kpis
ORDER BY window_start DESC
LIMIT 1;

-- Borough summary (all time)
CREATE VIEW IF NOT EXISTS v_borough_summary AS
SELECT
    Borough,
    sum(record_count)     AS total_records,
    avg(avg_site_eui)     AS overall_avg_site_eui,
    sum(total_ghg)        AS total_ghg_emissions
FROM building_energy_borough_stats
GROUP BY Borough
ORDER BY total_records DESC;

-- Active alerts
CREATE VIEW IF NOT EXISTS v_performance_alerts AS
SELECT
    window_start,
    window_end,
    avg_site_eui,
    records_per_minute,
    total_ghg
FROM building_energy_kpis
WHERE performance_alert = 1
ORDER BY window_start DESC;
