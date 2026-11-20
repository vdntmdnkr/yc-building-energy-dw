-- =============================================================================
-- File: 01_olap_queries.sql
-- Project: NYC Building Energy Data Warehouse (Local Law 84)
-- Description: Mandatory OLAP operations — Roll-up, Drill-down, Slice, Dice,
--              Pivot (crosstab), CUBE, and GROUPING SETS.
--              Requires: CREATE EXTENSION tablefunc (done in 01_create_schema).
-- =============================================================================

-- ============================================================
-- OLAP 1: ROLL-UP — Borough → City level energy totals by year
-- ─────────────────────────────────────────────────────────────
-- Business Question: What is the total citywide energy consumption
--   and GHG for each year, rolled up from individual borough data?
-- Dimensions:  Borough (granular) → City (aggregate)
-- Measure:     TotalSiteEnergyUse, TotalGHG, AvgSiteEUI
-- OLAP Op:     ROLL-UP (finer granularity → coarser granularity)
-- Expected Output: Both borough-level rows AND a city-level summary
--   row (Borough = 'City Total') per year.
-- ============================================================
SELECT
    y.ReportingYear,
    COALESCE(g.Borough, 'City Total')           AS Borough,  -- NULL → rolled up
    COUNT(f.FactKey)                            AS BuildingCount,
    SUM(f.SiteEnergyUse)                        AS TotalSiteEnergyUse_kBtu,
    SUM(f.GHGEmissions)                         AS TotalGHG_MetricTons,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI,
    ROUND(SUM(f.GrossFloorArea)::NUMERIC, 0)    AS TotalFloorArea_sqft
FROM FactBuildingBenchmark f
JOIN DimYear      y ON y.YearKey      = f.YearKey
JOIN DimGeography g ON g.GeographyKey = f.GeographyKey
GROUP BY ROLLUP(y.ReportingYear, g.Borough)
ORDER BY y.ReportingYear NULLS LAST, g.Borough NULLS LAST;

-- ============================================================
-- OLAP 2: DRILL-DOWN — City → Borough → Property level
-- ─────────────────────────────────────────────────────────────
-- Business Question: Starting from the citywide GHG total, can we
--   drill down into each borough, and further into individual properties?
-- Dimensions:  Year, Borough, PropertyName
-- Measure:     SiteEUI, GHGEmissions
-- OLAP Op:     DRILL-DOWN (coarser → finer granularity)
-- Expected Output: Multiple levels: aggregate → borough → property,
--   selectable by joining on the city/borough/property hierarchy.
-- ============================================================

-- Level 1: City total (broadest)
SELECT
    y.ReportingYear,
    'City'                                      AS Level,
    'All Boroughs'                              AS GroupLabel,
    COUNT(*)                                    AS Buildings,
    SUM(f.GHGEmissions)                         AS TotalGHG,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI
FROM FactBuildingBenchmark f
JOIN DimYear y ON y.YearKey = f.YearKey
GROUP BY y.ReportingYear

UNION ALL

-- Level 2: Borough detail
SELECT
    y.ReportingYear,
    'Borough',
    g.Borough,
    COUNT(*),
    SUM(f.GHGEmissions),
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)
FROM FactBuildingBenchmark f
JOIN DimYear      y ON y.YearKey      = f.YearKey
JOIN DimGeography g ON g.GeographyKey = f.GeographyKey
GROUP BY y.ReportingYear, g.Borough

UNION ALL

-- Level 3: Individual property (finest grain)
SELECT
    y.ReportingYear,
    'Property',
    p.PropertyName,
    1,
    f.GHGEmissions,
    f.SiteEUI
FROM FactBuildingBenchmark f
JOIN DimYear     y ON y.YearKey     = f.YearKey
JOIN DimProperty p ON p.PropertyKey = f.PropertyKey

ORDER BY ReportingYear, Level DESC, TotalGHG DESC;

-- ============================================================
-- OLAP 3: SLICE — Filter to Manhattan across all years
-- ─────────────────────────────────────────────────────────────
-- Business Question: Show all energy and emissions metrics for
--   Manhattan buildings only across all reporting years.
-- Dimensions:  Year, PropertyType (retained; Borough fixed to Manhattan)
-- Measure:     SiteEUI, GHGEmissions, EnergyStarScore, WaterUse
-- OLAP Op:     SLICE (fix one dimension value, retain all others)
-- Expected Output: Table with ReportingYear × PropertyType for Manhattan.
-- ============================================================
SELECT
    y.ReportingYear,
    pt.PrimaryPropertyType,
    pt.PropertyTypeGroup,
    COUNT(f.FactKey)                            AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI,
    SUM(f.GHGEmissions)                         AS TotalGHG,
    ROUND(AVG(f.EnergyStarScore)::NUMERIC, 1)   AS AvgEnergyStarScore,
    SUM(f.WaterUse)                             AS TotalWaterUse_kGal
FROM FactBuildingBenchmark f
JOIN DimYear         y  ON y.YearKey          = f.YearKey
JOIN DimGeography    g  ON g.GeographyKey     = f.GeographyKey
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
WHERE g.Borough = 'Manhattan'           -- SLICE: single borough fixed
ORDER BY y.ReportingYear, AvgSiteEUI DESC;

-- ============================================================
-- OLAP 4: DICE — Manhattan + Office type, years 2022–2024
-- ─────────────────────────────────────────────────────────────
-- Business Question: For Manhattan office buildings between 2022
--   and 2024, what are energy and GHG performance trends?
-- Dimensions:  Year ∈ {2022,2023,2024}, Borough = Manhattan,
--              PropertyTypeGroup = Office
-- Measure:     SiteEUI, GHGEmissions, EnergyStarScore
-- OLAP Op:     DICE (multiple dimension filters simultaneously)
-- Expected Output: Up to 3 rows (one per year), fine-grained slice.
-- ============================================================
SELECT
    y.ReportingYear,
    g.Borough,
    pt.PropertyTypeGroup,
    COUNT(f.FactKey)                            AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI,
    ROUND(AVG(f.SourceEUI)::NUMERIC, 2)         AS AvgSourceEUI,
    SUM(f.GHGEmissions)                         AS TotalGHG,
    ROUND(AVG(f.EnergyStarScore)::NUMERIC, 1)   AS AvgEnergyStarScore
FROM FactBuildingBenchmark f
JOIN DimYear         y  ON y.YearKey          = f.YearKey
JOIN DimGeography    g  ON g.GeographyKey     = f.GeographyKey
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
WHERE g.Borough            = 'Manhattan'                -- DICE filter 1
  AND pt.PropertyTypeGroup = 'Office'                   -- DICE filter 2
  AND y.ReportingYear      BETWEEN 2022 AND 2024        -- DICE filter 3
GROUP BY y.ReportingYear, g.Borough, pt.PropertyTypeGroup
ORDER BY y.ReportingYear;

-- ============================================================
-- OLAP 5: PIVOT — SiteEUI by Borough (rows) × Year (columns)
-- ─────────────────────────────────────────────────────────────
-- Business Question: Display average SiteEUI as a matrix where
--   each row is a Borough and each column is a ReportingYear.
-- Dimensions:  Borough (rows), ReportingYear (columns)
-- Measure:     AVG(SiteEUI)
-- OLAP Op:     PIVOT (cross-tabulation using crosstab())
-- Requires:    CREATE EXTENSION tablefunc (done in schema file)
-- Expected Output: 5 rows (boroughs) × N year columns.
-- ============================================================
-- Step 1: Use crosstab() for static pivot (adjust year list as needed)
SELECT *
FROM crosstab(
    -- Source query: must return (row_name, category, value) ordered correctly
    $$
    SELECT
        g.Borough,
        y.ReportingYear::TEXT,
        ROUND(AVG(f.SiteEUI)::NUMERIC, 2)
    FROM FactBuildingBenchmark f
    JOIN DimGeography g ON g.GeographyKey = f.GeographyKey
    JOIN DimYear      y ON y.YearKey      = f.YearKey
    WHERE f.SiteEUI IS NOT NULL
    GROUP BY g.Borough, y.ReportingYear
    ORDER BY 1, 2
    $$,
    -- Category list (column headers)
    $$ SELECT DISTINCT ReportingYear::TEXT FROM DimYear ORDER BY 1 $$
)
AS pivot_result (
    Borough TEXT,
    "2022"  NUMERIC,
    "2023"  NUMERIC,
    "2024"  NUMERIC
    -- Add more years here as data grows, e.g. "2025" NUMERIC
);

-- ============================================================
-- OLAP 6: SQL CUBE — All combinations of Year × Borough × PropertyTypeGroup
-- ─────────────────────────────────────────────────────────────
-- Business Question: Provide a complete multi-dimensional summary
--   of avg SiteEUI and total GHG for every combination of grouping
--   levels: year+borough+type, year+borough, year+type, year alone,
--   borough alone, type alone, and grand total.
-- Dimensions:  ReportingYear, Borough, PropertyTypeGroup
-- Measures:    AVG(SiteEUI), SUM(GHGEmissions), COUNT(buildings)
-- OLAP Op:     CUBE (2^3 = 8 grouping combinations)
-- Expected Output: Many rows; NULL in a dimension = rolled up at that level.
-- ============================================================
SELECT
    y.ReportingYear,
    g.Borough,
    pt.PropertyTypeGroup,
    COUNT(f.FactKey)                            AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI,
    SUM(f.GHGEmissions)                         AS TotalGHG,
    -- GROUPING() = 0 means dimension is included; 1 means rolled up
    GROUPING(y.ReportingYear)                   AS IsYearRolledUp,
    GROUPING(g.Borough)                         AS IsBoroughRolledUp,
    GROUPING(pt.PropertyTypeGroup)              AS IsTypeRolledUp
FROM FactBuildingBenchmark f
JOIN DimYear         y  ON y.YearKey          = f.YearKey
JOIN DimGeography    g  ON g.GeographyKey     = f.GeographyKey
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
GROUP BY CUBE(y.ReportingYear, g.Borough, pt.PropertyTypeGroup)
ORDER BY
    y.ReportingYear  NULLS LAST,
    g.Borough        NULLS LAST,
    pt.PropertyTypeGroup NULLS LAST;

-- ============================================================
-- OLAP 7: GROUPING SETS — Equivalent of selective ROLLUP/CUBE
-- ─────────────────────────────────────────────────────────────
-- Business Question: Produce specific aggregation levels needed
--   for dashboards: (Year, Borough), (Year, PropertyTypeGroup),
--   and (Borough, PropertyTypeGroup) simultaneously in one query.
-- Dimensions:  Year, Borough, PropertyTypeGroup (selective combos)
-- Measure:     AVG(SiteEUI), SUM(GHGEmissions)
-- OLAP Op:     GROUPING SETS (explicit subset of CUBE combinations)
-- Expected Output: 3 aggregation levels in a single result set.
-- ============================================================
SELECT
    y.ReportingYear,
    g.Borough,
    pt.PropertyTypeGroup,
    COUNT(f.FactKey)                            AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI,
    SUM(f.GHGEmissions)                         AS TotalGHG,
    CASE
        WHEN GROUPING(y.ReportingYear, g.Borough)         = 0 THEN 'Year × Borough'
        WHEN GROUPING(y.ReportingYear, pt.PropertyTypeGroup) = 0 THEN 'Year × PropertyType'
        WHEN GROUPING(g.Borough, pt.PropertyTypeGroup)    = 0 THEN 'Borough × PropertyType'
        ELSE 'Unknown'
    END                                         AS AggregationLevel
FROM FactBuildingBenchmark f
JOIN DimYear         y  ON y.YearKey          = f.YearKey
JOIN DimGeography    g  ON g.GeographyKey     = f.GeographyKey
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
GROUP BY GROUPING SETS (
    (y.ReportingYear, g.Borough),               -- Year × Borough
    (y.ReportingYear, pt.PropertyTypeGroup),    -- Year × PropertyType
    (g.Borough,       pt.PropertyTypeGroup)     -- Borough × PropertyType
)
ORDER BY AggregationLevel, y.ReportingYear NULLS LAST, g.Borough NULLS LAST;
