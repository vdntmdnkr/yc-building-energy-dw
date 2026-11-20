-- =============================================================================
-- File: 01_citus_setup.sql
-- Project: NYC Building Energy Data Warehouse (Local Law 84)
-- Description: Citus distributed DW setup — extension, distribution strategy,
--              shard configuration, and reference tables.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Enable Citus Extension
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS citus;

-- ---------------------------------------------------------------------------
-- 2. Shard count configuration
-- ---------------------------------------------------------------------------
-- Recommended shard count = 32 for a single coordinator + small worker pool.
-- Rule of thumb: 2–4 shards per CPU core across all workers.
-- For a 2-worker, 4-core-each setup: 2 × 4 × 4 = 32 shards.
-- Adjust upward (64, 128) as the cluster grows.
--
-- This must be set BEFORE create_distributed_table calls.
ALTER SYSTEM SET citus.shard_count = 32;
SELECT pg_reload_conf();

-- ---------------------------------------------------------------------------
-- 3. Distribute the main fact table
-- ---------------------------------------------------------------------------
-- Distribution column: PropertyKey
--
-- Justification:
--   • HIGH CARDINALITY — PropertyKey is a SERIAL surrogate with one value per
--     unique building; a typical NYC LL84 dataset has 20,000–50,000 buildings,
--     giving a uniform hash distribution with negligible skew (unlike Borough
--     which has only 5 distinct values, causing hot shards).
--   • CO-LOCATION — DimProperty is distributed on PropertyKey (reference
--     table is replicated to all workers), so fact↔property joins are local
--     (no cross-shard shuffle for the most common property attribute lookup).
--   • JOIN PATTERNS — The two most expensive queries (Q2: EUI by property
--     type, Q7: high-energy building list) filter or aggregate by PropertyKey
--     or PropertyTypeKey — both resolved locally after a co-located join.
--   • ALTERNATIVE ANALYSIS:
--       - YearKey has only 3–5 distinct values → severe skew (most queries
--         span all years anyway — no filtering benefit).
--       - GeographyKey has 5 boroughs × BBL combinations; borough-level
--         queries still need cross-shard aggregation since buildings in one
--         borough can land on any shard unless routed by borough (only 5
--         values → terrible distribution).
--       - PropertyKey wins on all three criteria: cardinality, skew, and
--         join co-location.

SELECT create_distributed_table('FactBuildingBenchmark', 'PropertyKey');

-- Also distribute the aggregate fact — co-locate with borough/year pattern
-- Use GeographyKey here: aggregate fact is typically queried by borough,
-- and this table is small enough that skew is acceptable.
SELECT create_distributed_table(
    'FactBoroughPropertyTypeAnnualPerformance',
    'GeographyKey'
);

-- ---------------------------------------------------------------------------
-- 4. Reference tables (small dimensions — replicated to ALL workers)
-- ---------------------------------------------------------------------------
-- Reference tables avoid cross-shard joins for dimension lookups.
-- Every worker has a full local copy; fact→dim joins are always local.

SELECT create_reference_table('DimYear');
SELECT create_reference_table('DimProperty');
SELECT create_reference_table('DimGeography');
SELECT create_reference_table('DimPerformanceBand');
SELECT create_reference_table('DimPropertyType');

-- ---------------------------------------------------------------------------
-- 5. Shard replication and placement settings
-- ---------------------------------------------------------------------------
-- For development (single-node Citus): replication factor 1
ALTER SYSTEM SET citus.shard_replication_factor = 1;
SELECT pg_reload_conf();

-- ---------------------------------------------------------------------------
-- 6. Distribution key analysis summary (comment)
-- ---------------------------------------------------------------------------
/*
  DISTRIBUTION KEY DECISION MATRIX
  ─────────────────────────────────────────────────────────────────────────
  Candidate Key    │ Cardinality │ Skew Risk │ Join Co-location │ Decision
  ─────────────────┼─────────────┼───────────┼──────────────────┼─────────
  PropertyKey      │ 20K–50K     │ LOW       │ HIGH (DimProp)   │ ✅ CHOSEN
  GeographyKey     │ 5 boroughs  │ HIGH      │ MEDIUM           │ ❌
  YearKey          │ 3–5 values  │ VERY HIGH │ LOW              │ ❌
  PrimaryPropType  │ ~80 types   │ MEDIUM    │ LOW              │ ❌
  ─────────────────────────────────────────────────────────────────────────

  Co-location benefits with PropertyKey:
  • FactBuildingBenchmark JOIN DimProperty  → 100% local (reference table)
  • Multi-year property history queries     → all property rows on same shard
  • Aggregate queries still scatter-gather but only need partial aggregates

  Network overhead avoidance:
  • Reference tables (all dims) are replicated → no network for star joins
  • Only cross-shard communication: HAVING / ORDER BY / LIMIT on coordinator
*/
