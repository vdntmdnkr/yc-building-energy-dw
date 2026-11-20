-- =============================================================================
-- File: 04_analytical_queries.sql
-- Project: NYC Building Energy Data Warehouse (Local Law 84)
-- Description: 10 analytical queries matching the 10 mandatory business
--              analysis questions. Each wrapped with EXPLAIN ANALYZE.
-- =============================================================================

-- ============================================================
-- Q1. Annual building energy consumption and intensity by year
-- Business Q: How has citywide energy use and intensity trended
--             across all reporting years?
-- ============================================================
EXPLAIN ANALYZE
SELECT
    y.ReportingYear,
    COUNT(f.FactKey)                    AS TotalProperties,
    SUM(f.SiteEnergyUse)                AS TotalSiteEnergyUse_kBtu,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)   AS AvgSiteEUI,
    ROUND(AVG(f.SourceEUI)::NUMERIC, 2) AS AvgSourceEUI,
    SUM(f.GHGEmissions)                 AS TotalGHG_MetricTons,
    SUM(f.GrossFloorArea)               AS TotalFloorArea_sqft
FROM FactBuildingBenchmark f
JOIN DimYear y ON y.YearKey = f.YearKey
GROUP BY y.ReportingYear
ORDER BY y.ReportingYear;

-- ============================================================
-- Q2. Average SiteEUI by PrimaryPropertyType
-- Business Q: Which property types are the most/least energy
--             intensive per square foot?
-- ============================================================
EXPLAIN ANALYZE
SELECT
    pt.PrimaryPropertyType,
    pt.PropertyTypeGroup,
    COUNT(f.FactKey)                            AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI,
    ROUND(AVG(f.SourceEUI)::NUMERIC, 2)         AS AvgSourceEUI,
    ROUND(AVG(f.EnergyStarScore)::NUMERIC, 1)   AS AvgEnergyStarScore,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.SiteEUI)::NUMERIC, 2) AS MedianSiteEUI
FROM FactBuildingBenchmark f
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
WHERE f.SiteEUI IS NOT NULL
GROUP BY pt.PrimaryPropertyType, pt.PropertyTypeGroup
HAVING COUNT(f.FactKey) >= 10   -- filter low-sample types
ORDER BY AvgSiteEUI DESC;

-- ============================================================
-- Q3. Boroughs with highest average EUI
-- Business Q: Which borough has the highest energy intensity
--             and how does it compare over the years?
-- ============================================================
EXPLAIN ANALYZE
SELECT
    g.Borough,
    y.ReportingYear,
    COUNT(f.FactKey)                    AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)   AS AvgSiteEUI,
    ROUND(AVG(f.SourceEUI)::NUMERIC, 2) AS AvgSourceEUI,
    SUM(f.GHGEmissions)                 AS TotalGHG,
    RANK() OVER (
        PARTITION BY y.ReportingYear
        ORDER BY AVG(f.SiteEUI) DESC
    )                                   AS EUI_Rank
FROM FactBuildingBenchmark f
JOIN DimGeography g ON g.GeographyKey = f.GeographyKey
JOIN DimYear y      ON y.YearKey      = f.YearKey
WHERE f.SiteEUI IS NOT NULL
GROUP BY g.Borough, y.ReportingYear
ORDER BY y.ReportingYear, EUI_Rank;

-- ============================================================
-- Q4. GHG emissions by building type (top 10 property types)
-- Business Q: Which building types contribute most to
--             greenhouse gas emissions?
-- ============================================================
EXPLAIN ANALYZE
SELECT
    pt.PrimaryPropertyType,
    pt.PropertyTypeGroup,
    SUM(f.GHGEmissions)                             AS TotalGHG_MetricTons,
    AVG(f.GHGEmissions)                             AS AvgGHGPerBuilding,
    SUM(f.GrossFloorArea)                           AS TotalFloorArea,
    ROUND((SUM(f.GHGEmissions) /
           NULLIF(SUM(f.GrossFloorArea), 0))::NUMERIC * 1000, 4)
                                                    AS GHGIntensity_kgCO2e_per_sqft,
    COUNT(f.FactKey)                                AS BuildingCount
FROM FactBuildingBenchmark f
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
WHERE f.GHGEmissions IS NOT NULL
GROUP BY pt.PrimaryPropertyType, pt.PropertyTypeGroup
ORDER BY TotalGHG_MetricTons DESC
LIMIT 10;

-- ============================================================
-- Q5. Building size vs average energy consumption (by SizeBand)
-- Business Q: Do larger buildings consume proportionally more
--             energy, or does intensity decrease with size?
-- ============================================================
EXPLAIN ANALYZE
SELECT
    p.SizeBand,
    COUNT(f.FactKey)                            AS BuildingCount,
    ROUND(AVG(f.GrossFloorArea)::NUMERIC, 0)    AS AvgGrossFloorArea_sqft,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI,
    ROUND(AVG(f.SiteEnergyUse)::NUMERIC, 0)     AS AvgSiteEnergyUse_kBtu,
    ROUND(AVG(f.GHGEmissions)::NUMERIC, 2)      AS AvgGHGEmissions,
    ROUND(AVG(f.EnergyStarScore)::NUMERIC, 1)   AS AvgEnergyStarScore
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
-- Q6. ENERGY STAR score distribution statistics
-- Business Q: What is the overall ENERGY STAR score performance
--             of NYC buildings?
-- ============================================================
EXPLAIN ANALYZE
SELECT
    pb.EnergyStarBand,
    COUNT(f.FactKey)                                AS BuildingCount,
    ROUND(MIN(f.EnergyStarScore)::NUMERIC, 1)       AS MinScore,
    ROUND(MAX(f.EnergyStarScore)::NUMERIC, 1)       AS MaxScore,
    ROUND(AVG(f.EnergyStarScore)::NUMERIC, 1)       AS AvgScore,
    ROUND(STDDEV(f.EnergyStarScore)::NUMERIC, 2)    AS StdDev,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY f.EnergyStarScore)::NUMERIC, 1) AS Q1,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY f.EnergyStarScore)::NUMERIC, 1) AS Median,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY f.EnergyStarScore)::NUMERIC, 1) AS Q3
FROM FactBuildingBenchmark f
JOIN DimPerformanceBand pb ON pb.PerformanceKey = f.PerformanceKey
WHERE f.EnergyStarScore IS NOT NULL
GROUP BY pb.EnergyStarBand
ORDER BY AvgScore DESC;

-- ============================================================
-- Q7. High-energy and high-emission buildings (top 20)
-- Business Q: Which specific buildings are the worst performers
--             and where are they located?
-- ============================================================
EXPLAIN ANALYZE
SELECT
    p.PropertyName,
    p.PropertyID,
    g.Borough,
    pt.PrimaryPropertyType,
    y.ReportingYear,
    f.SiteEUI,
    f.GHGEmissions,
    f.EnergyStarScore,
    f.GrossFloorArea,
    f.IsHighEnergyBuilding,
    f.IsHighGHGBuilding,
    DENSE_RANK() OVER (ORDER BY f.SiteEUI DESC)      AS EUI_Rank,
    DENSE_RANK() OVER (ORDER BY f.GHGEmissions DESC) AS GHG_Rank
FROM FactBuildingBenchmark f
JOIN DimProperty     p  ON p.PropertyKey    = f.PropertyKey
JOIN DimGeography    g  ON g.GeographyKey   = f.GeographyKey
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
JOIN DimYear         y  ON y.YearKey        = f.YearKey
WHERE f.IsHighEnergyBuilding = 1
   OR f.IsHighGHGBuilding    = 1
ORDER BY f.SiteEUI DESC, f.GHGEmissions DESC
LIMIT 20;

-- ============================================================
-- Q8. Water use patterns by borough and building type
-- Business Q: How does water consumption vary by location
--             and building purpose?
-- ============================================================
EXPLAIN ANALYZE
SELECT
    g.Borough,
    pt.PropertyTypeGroup,
    COUNT(f.FactKey)                                AS BuildingCount,
    ROUND(SUM(f.WaterUse)::NUMERIC, 0)              AS TotalWaterUse_kGal,
    ROUND(AVG(f.WaterUse)::NUMERIC, 2)              AS AvgWaterUse_kGal,
    ROUND(AVG(f.WaterUse / NULLIF(f.GrossFloorArea, 0))::NUMERIC * 1000, 4)
                                                    AS AvgWaterIntensity_gal_per_sqft
FROM FactBuildingBenchmark f
JOIN DimGeography    g  ON g.GeographyKey   = f.GeographyKey
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
WHERE f.WaterUse IS NOT NULL
  AND f.GrossFloorArea > 0
GROUP BY g.Borough, pt.PropertyTypeGroup
ORDER BY g.Borough, TotalWaterUse_kGal DESC;

-- ============================================================
-- Q9. Cross-tabulation: Borough × PropertyTypeGroup average SiteEUI
-- Business Q: Which borough–building-type combinations have the
--             highest energy intensity?
-- ============================================================
EXPLAIN ANALYZE
SELECT
    g.Borough,
    pt.PropertyTypeGroup,
    COUNT(f.FactKey)                            AS BuildingCount,
    ROUND(AVG(f.SiteEUI)::NUMERIC, 2)           AS AvgSiteEUI,
    ROUND(AVG(f.GHGEmissions)::NUMERIC, 2)      AS AvgGHG,
    ROUND(AVG(f.EnergyStarScore)::NUMERIC, 1)   AS AvgEnergyStarScore
FROM FactBuildingBenchmark f
JOIN DimGeography    g  ON g.GeographyKey     = f.GeographyKey
JOIN DimPropertyType pt ON pt.PropertyTypeKey = f.PropertyTypeKey
WHERE f.SiteEUI IS NOT NULL
GROUP BY g.Borough, pt.PropertyTypeGroup
ORDER BY g.Borough, AvgSiteEUI DESC;

-- ============================================================
-- Q10. Year-over-year GHG change by borough
-- Business Q: Is GHG emission improving (decreasing) year-over-
--             year in each borough — are targets being met?
-- ============================================================
EXPLAIN ANALYZE
WITH annual AS (
    SELECT
        g.Borough,
        y.ReportingYear,
        SUM(f.GHGEmissions)                     AS TotalGHG,
        COUNT(f.FactKey)                         AS BuildingCount,
        ROUND(AVG(f.SiteEUI)::NUMERIC, 2)        AS AvgSiteEUI
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
    AvgSiteEUI,
    LAG(TotalGHG) OVER (PARTITION BY Borough ORDER BY ReportingYear) AS PrevYearGHG,
    TotalGHG - LAG(TotalGHG) OVER (PARTITION BY Borough ORDER BY ReportingYear)
                                                                      AS GHG_Change,
    ROUND(
        100.0 * (TotalGHG - LAG(TotalGHG) OVER (PARTITION BY Borough ORDER BY ReportingYear))
              / NULLIF(LAG(TotalGHG) OVER (PARTITION BY Borough ORDER BY ReportingYear), 0),
        2
    )                                                                 AS GHG_PctChange
FROM annual
ORDER BY Borough, ReportingYear;
