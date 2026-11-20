-- =============================================================================
-- File: 02_distributed_queries.sql
-- Project: NYC Building Energy Data Warehouse (Local Law 84)
-- Description: 5 analytical queries optimised for Citus distributed execution.
--              Each prefixed with \timing on for psql execution timing.
--              Reference tables (all dims) are replicated → joins are local.
-- =============================================================================

\timing on

-- ============================================================
-- DQ1. Energy consumption by property type (distributed)
-- Equivalent to Batch Q2 — SiteEUI by PrimaryPropertyType
-- Expected output: ~80 rows, one per property type, ordered
--                 by descending average SiteEUI.
-- Citus notes: PropertyKey is the dist key; DimPropertyType is
--              a reference table (local join). Each shard computes
--              a partial AVG/COUNT; coordinator merges.
-- ============================================================
\echo 'DQ1: Energy by property type'
EXPLAIN (ANALYZE, VERBOSE, COSTS)
SELECT
    pt.PrimaryPropertyType,
    pt.PropertyTypeGroup,
    COUNT(f.FactKey)                            AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI,
    ROUND(AVG(f.SourceEUI)::NUMERIC, 2)         AS AvgSourceEUI,
    ROUND(SUM(f.SiteEnergyUse)::NUMERIC, 0)     AS TotalEnergyUse_kBtu,
    ROUND(AVG(f.EnergyStarScore)::NUMERIC, 1)   AS AvgEnergyStarScore
FROM FactBuildingBenchmark f
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
WHERE f.SiteEUI IS NOT NULL
GROUP BY pt.PrimaryPropertyType, pt.PropertyTypeGroup
HAVING COUNT(f.FactKey) >= 10
ORDER BY AvgSiteEUI DESC;

-- ============================================================
-- DQ2. EUI by borough across all years (distributed)
-- Equivalent to Batch Q3 — Borough energy intensity
-- Expected output: 5 boroughs × N years matrix.
-- Citus notes: DimGeography is a reference table; shard-local
--              grouping by GeographyKey then merge at coordinator.
-- ============================================================
\echo 'DQ2: EUI by borough'
EXPLAIN (ANALYZE, VERBOSE, COSTS)
SELECT
    g.Borough,
    y.ReportingYear,
    COUNT(f.FactKey)                    AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)   AS AvgSiteEUI,
    SUM(f.GHGEmissions)                 AS TotalGHG,
    SUM(f.GrossFloorArea)               AS TotalFloorArea
FROM FactBuildingBenchmark f
JOIN DimGeography g ON g.GeographyKey = f.GeographyKey
JOIN DimYear      y ON y.YearKey      = f.YearKey
WHERE f.SiteEUI IS NOT NULL
GROUP BY g.Borough, y.ReportingYear
ORDER BY y.ReportingYear, AVG(f.SiteEUI) DESC;

-- ============================================================
-- DQ3. Yearly GHG analysis (distributed)
-- Equivalent to Batch Q10 — Year-over-year GHG change
-- Expected output: Borough × Year with YoY delta, ordered by
--                 Borough and year.
-- Citus notes: Window functions (LAG) run on coordinator after
--              shard-level GROUP BY push-down. Partial aggregates
--              collected, then LAG applied centrally.
-- ============================================================
\echo 'DQ3: Yearly GHG analysis with YoY change'
EXPLAIN (ANALYZE, VERBOSE, COSTS)
WITH annual AS (
    SELECT
        g.Borough,
        y.ReportingYear,
        SUM(f.GHGEmissions) AS TotalGHG,
        COUNT(f.FactKey)    AS BuildingCount
    FROM FactBuildingBenchmark f
    JOIN DimGeography g ON g.GeographyKey = f.GeographyKey
    JOIN DimYear      y ON y.YearKey      = f.YearKey
    WHERE f.GHGEmissions IS NOT NULL
    GROUP BY g.Borough, y.ReportingYear
)
SELECT
    Borough,
    ReportingYear,
    TotalGHG,
    BuildingCount,
    LAG(TotalGHG) OVER (PARTITION BY Borough ORDER BY ReportingYear)    AS PrevYearGHG,
    TotalGHG
        - LAG(TotalGHG) OVER (PARTITION BY Borough ORDER BY ReportingYear)
                                                                         AS GHG_Change,
    ROUND(
        100.0 * (TotalGHG - LAG(TotalGHG) OVER (PARTITION BY Borough ORDER BY ReportingYear))
              / NULLIF(LAG(TotalGHG) OVER (PARTITION BY Borough ORDER BY ReportingYear), 0),
        2
    )                                                                    AS GHG_PctChange
FROM annual
ORDER BY Borough, ReportingYear;

-- ============================================================
-- DQ4. Building size bands energy analysis (distributed)
-- Equivalent to Batch Q5 — SizeBand vs avg energy
-- Expected output: 3 rows (Small / Medium / Large) with metrics.
-- Citus notes: DimProperty is a reference table → SizeBand filter
--              and join is local; GROUP BY on shard, merge at coord.
-- ============================================================
\echo 'DQ4: Building size bands energy analysis'
EXPLAIN (ANALYZE, VERBOSE, COSTS)
SELECT
    p.SizeBand,
    COUNT(f.FactKey)                            AS BuildingCount,
    ROUND(AVG(f.GrossFloorArea)::NUMERIC, 0)    AS AvgGrossFloorArea,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI,
    ROUND(AVG(f.SiteEnergyUse)::NUMERIC, 0)     AS AvgSiteEnergyUse,
    ROUND(AVG(f.GHGEmissions)::NUMERIC, 2)      AS AvgGHGEmissions,
    ROUND(AVG(f.EnergyStarScore)::NUMERIC, 1)   AS AvgEnergyStarScore,
    SUM(f.GHGEmissions)                         AS TotalGHG
FROM FactBuildingBenchmark f
JOIN DimProperty p ON p.PropertyKey = f.PropertyKey
WHERE p.SizeBand IS NOT NULL
GROUP BY p.SizeBand
ORDER BY
    CASE p.SizeBand
        WHEN 'Small'  THEN 1
        WHEN 'Medium' THEN 2
        WHEN 'Large'  THEN 3
        ELSE 4
    END;

-- ============================================================
-- DQ5. Borough × PropertyTypeGroup aggregation (distributed)
-- Equivalent to Batch Q9 — cross-tabulation
-- Expected output: 5 boroughs × 6 property groups = ~30 rows.
-- Citus notes: Both dimension tables are reference tables → all
--              joins are shard-local. Coordinator only does
--              final ORDER BY. Best-case distributed query.
-- ============================================================
\echo 'DQ5: Borough x PropertyTypeGroup aggregation'
EXPLAIN (ANALYZE, VERBOSE, COSTS)
SELECT
    g.Borough,
    pt.PropertyTypeGroup,
    COUNT(f.FactKey)                            AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI,
    ROUND(AVG(f.GHGEmissions)::NUMERIC, 2)      AS AvgGHG,
    ROUND(SUM(f.GHGEmissions)::NUMERIC, 0)      AS TotalGHG,
    ROUND(SUM(f.GrossFloorArea)::NUMERIC, 0)    AS TotalFloorArea,
    ROUND(AVG(f.EnergyStarScore)::NUMERIC, 1)   AS AvgEnergyStarScore,
    ROUND(AVG(f.WaterUse)::NUMERIC, 2)          AS AvgWaterUse
FROM FactBuildingBenchmark f
JOIN DimGeography    g  ON g.GeographyKey     = f.GeographyKey
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
WHERE f.SiteEUI IS NOT NULL
GROUP BY g.Borough, pt.PropertyTypeGroup
ORDER BY g.Borough, AvgSiteEUI DESC;

\timing off
