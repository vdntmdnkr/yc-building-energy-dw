-- =============================================================================
-- File: 03_performance_comparison.sql
-- Project: NYC Building Energy Data Warehouse (Local Law 84)
-- Description: Performance comparison framework — centralized PostgreSQL vs.
--              Citus distributed. Captures execution time at multiple data
--              volumes and stores results in a comparison table.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Results table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS perf_comparison (
    id                  SERIAL PRIMARY KEY,
    query_name          VARCHAR(100)    NOT NULL,
    row_volume          INT             NOT NULL,   -- e.g. 100000, 500000, 1000000
    centralized_ms      NUMERIC(10,2),              -- PostgreSQL execution time (ms)
    distributed_ms      NUMERIC(10,2),              -- Citus execution time (ms)
    speedup_factor      NUMERIC(6,2)
        GENERATED ALWAYS AS (
            CASE WHEN distributed_ms > 0
                 THEN centralized_ms / distributed_ms
                 ELSE NULL END
        ) STORED,
    notes               TEXT,
    recorded_at         TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE perf_comparison IS
    'Manual-fill comparison table: run EXPLAIN ANALYZE on both centralized and '
    'distributed instances, record planning+execution ms, and INSERT rows here.';

-- ---------------------------------------------------------------------------
-- 2. Sample INSERT template (fill after running queries)
-- ---------------------------------------------------------------------------
/*
INSERT INTO perf_comparison (query_name, row_volume, centralized_ms, distributed_ms, notes)
VALUES
    ('Q_borough_eui',       100000,  NULL, NULL, 'DQ2 — borough EUI aggregation'),
    ('Q_borough_eui',       500000,  NULL, NULL, 'DQ2 — borough EUI aggregation'),
    ('Q_borough_eui',       1000000, NULL, NULL, 'DQ2 — borough EUI aggregation'),
    ('Q_proptype_energy',   100000,  NULL, NULL, 'DQ1 — property-type avg SiteEUI'),
    ('Q_proptype_energy',   500000,  NULL, NULL, 'DQ1 — property-type avg SiteEUI'),
    ('Q_proptype_energy',   1000000, NULL, NULL, 'DQ1 — property-type avg SiteEUI'),
    ('Q_ghg_yoy',           100000,  NULL, NULL, 'DQ3 — YoY GHG change'),
    ('Q_ghg_yoy',           500000,  NULL, NULL, 'DQ3 — YoY GHG change'),
    ('Q_ghg_yoy',           1000000, NULL, NULL, 'DQ3 — YoY GHG change'),
    ('Q_size_bands',        100000,  NULL, NULL, 'DQ4 — size band aggregation'),
    ('Q_size_bands',        500000,  NULL, NULL, 'DQ4 — size band aggregation'),
    ('Q_size_bands',        1000000, NULL, NULL, 'DQ4 — size band aggregation'),
    ('Q_borough_x_proptype',100000,  NULL, NULL, 'DQ5 — cross-tab aggregation'),
    ('Q_borough_x_proptype',500000,  NULL, NULL, 'DQ5 — cross-tab aggregation'),
    ('Q_borough_x_proptype',1000000, NULL, NULL, 'DQ5 — cross-tab aggregation');
*/

-- ---------------------------------------------------------------------------
-- 3a. EXPLAIN ANALYZE blocks — 100K rows
--     Run these on BOTH centralized and Citus instances.
--     Record "Execution Time: X ms" from the output into perf_comparison.
-- ---------------------------------------------------------------------------

-- ---- Query: borough EUI (DQ2) @ 100K rows ----
-- [CENTRALIZED] Run on port 5432:
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    g.Borough,
    y.ReportingYear,
    COUNT(f.FactKey)                    AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)   AS AvgSiteEUI,
    SUM(f.GHGEmissions)                 AS TotalGHG
FROM FactBuildingBenchmark f
JOIN DimGeography g ON g.GeographyKey = f.GeographyKey
JOIN DimYear      y ON y.YearKey      = f.YearKey
GROUP BY g.Borough, y.ReportingYear
ORDER BY y.ReportingYear, AVG(f.SiteEUI) DESC;

-- [DISTRIBUTED] Run on port 5433 (Citus):
-- Identical query — Citus planner adds Task Tracker / Router nodes.
-- Look for: "Custom Scan (Citus Adaptive)" in plan.

-- ---- Query: property-type EUI (DQ1) @ 100K rows ----
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    pt.PrimaryPropertyType,
    COUNT(f.FactKey)                    AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)   AS AvgSiteEUI
FROM FactBuildingBenchmark f
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
GROUP BY pt.PrimaryPropertyType
ORDER BY AvgSiteEUI DESC;

-- ---------------------------------------------------------------------------
-- 3b. EXPLAIN ANALYZE blocks — 500K rows
-- ---------------------------------------------------------------------------
-- (Use the same queries as above with a larger dataset loaded into staging/fact)

-- ---------------------------------------------------------------------------
-- 3c. EXPLAIN ANALYZE blocks — 1M rows
-- ---------------------------------------------------------------------------
-- (Use the same queries as above with a larger dataset)

-- ---------------------------------------------------------------------------
-- 4. Result summary query
-- ---------------------------------------------------------------------------
SELECT
    query_name,
    row_volume,
    centralized_ms,
    distributed_ms,
    speedup_factor,
    notes
FROM perf_comparison
ORDER BY query_name, row_volume;

-- ---------------------------------------------------------------------------
-- 5. What to look for in EXPLAIN (ANALYZE, BUFFERS) output
-- ---------------------------------------------------------------------------
/*
  KEY METRICS TO COMPARE
  ══════════════════════════════════════════════════════════════════════════
  1. EXECUTION TIME (ms)
     - Centralized: single "Execution Time: X ms" at bottom
     - Citus: sum of all shard task times ≠ wall time due to parallelism;
       look at "Planning Time" + "Execution Time" on coordinator

  2. NETWORK OVERHEAD (Citus-specific)
     - Look for "Distributed Subplan" nodes → these cross the network
     - Reference table joins appear as "Custom Scan (CitusScan)" with
       "strategy: router" = no network; local scan on each worker
     - "strategy: real-time" = parallel scatter-gather with network round-trip

  3. BUFFER USAGE (BUFFERS option)
     - "shared hit=N" : pages served from buffer cache (fast)
     - "shared read=N" : pages read from disk (slow)
     - Lower shared read in Citus means better cache use per shard

  4. SHARD BALANCE
     - Citus EXPLAIN shows per-shard task plans.
     - If one shard has 10× the rows of others → shard skew.
     - Skew from PropertyKey is minimal (high cardinality, uniform hash).
     - Skew from Borough (5 values) would cause heavy imbalance — this is
       why we chose PropertyKey over GeographyKey as the distribution column.

  5. COORDINATOR BOTTLENECK
     - Window functions (LAG in DQ3) always run on coordinator after
       shard-level aggregation. For YoY GHG, the coordinator receives
       at most Borough × Year rows (~30 rows) — negligible overhead.

  6. SPEEDUP INTERPRETATION
     - speedup_factor < 1: Citus is SLOWER — network overhead dominates
       (expected at 100K rows; Citus overhead ~5–20ms per query).
     - speedup_factor ≈ 1: break-even (typically ~300K–500K rows for
       this schema).
     - speedup_factor > 1: Citus wins — parallelism outweighs overhead
       (expected at 1M+ rows with 4+ workers).

  EXPECTED OUTCOMES (reference targets)
  ──────────────────────────────────────────────────────────────────────────
  Volume     │ Centralized (ms) │ Citus (ms) │ Speedup
  100K rows  │       25–80      │   30–120   │  ~0.7–1.0  (overhead phase)
  500K rows  │      120–400     │    80–200  │  ~1.5–2.0  (break-even zone)
  1M rows    │      250–900     │   100–300  │  ~2.5–4.0  (Citus wins)
  ──────────────────────────────────────────────────────────────────────────
*/
