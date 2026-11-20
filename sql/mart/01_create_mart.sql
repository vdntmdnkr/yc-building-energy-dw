-- =============================================================================
-- File: 01_create_mart.sql
-- Project: NYC Building Energy Data Warehouse (Local Law 84)
-- Description: Creates the BuildingPerformanceAnalyticsMart for downstream
--              ML (Regression, Decision Tree, Association Mining) and BI reporting.
--              CRITICAL ARCHITECTURAL REQUIREMENT:
--              "The mart should be generated from the curated warehouse/fact-dimension
--              structure wherever possible, not independently rebuilt from raw source."
-- =============================================================================

-- Drop existing mart table and view
DROP VIEW IF EXISTS vw_building_performance_mart CASCADE;
DROP TABLE IF EXISTS building_performance_analytics_mart CASCADE;

-- -----------------------------------------------------------------------------
-- 1. Materialized Analytical Mart Table
-- -----------------------------------------------------------------------------
CREATE TABLE building_performance_analytics_mart AS
SELECT
    -- Surrogate Keys & Identifiers
    f.FactKey,
    f.PropertyKey,
    p.PropertyID,
    p.PropertyName,

    -- Temporal Dimension
    y.ReportingYear,

    -- Geographic Dimension
    g.Borough,
    g.BBL,
    g.BIN,
    g.BoroughGroup,

    -- Property Type Dimension
    pt.PrimaryPropertyType,
    pt.PropertyTypeGroup,

    -- Property Characteristics & Performance Bands
    p.SizeBand,
    pb.EnergyIntensityBand,
    pb.GHGIntensityBand,
    pb.EnergyStarBand,

    -- Quantitative Measures
    f.GrossFloorArea,
    f.SiteEnergyUse,
    f.SiteEUI,
    f.SourceEUI,
    f.GHGEmissions,
    f.WaterUse,
    f.EnergyStarScore,

    -- Normalized & Derived Analytical Indicators
    CASE 
        WHEN f.GrossFloorArea > 0 THEN ROUND((f.GHGEmissions / f.GrossFloorArea)::numeric, 6)
        ELSE NULL 
    END AS GHGIntensity,

    CASE 
        WHEN f.GrossFloorArea > 0 AND f.WaterUse IS NOT NULL THEN ROUND((f.WaterUse / f.GrossFloorArea)::numeric, 6)
        ELSE NULL 
    END AS WaterIntensity,

    -- Target & Alert Flags
    f.IsHighEnergyBuilding,
    f.IsHighGHGBuilding

FROM FactBuildingBenchmark f
JOIN DimYear y ON f.YearKey = y.YearKey
JOIN DimProperty p ON f.PropertyKey = p.PropertyKey
JOIN DimGeography g ON f.GeographyKey = g.GeographyKey
JOIN DimPropertyType pt ON f.PropertyTypeKey = pt.PropertyTypeKey
JOIN DimPerformanceBand pb ON f.PerformanceKey = pb.PerformanceKey;

-- -----------------------------------------------------------------------------
-- 2. Indexes for High-Performance Analytical & ML Queries
-- -----------------------------------------------------------------------------
CREATE INDEX idx_mart_property_id ON building_performance_analytics_mart(PropertyID);
CREATE INDEX idx_mart_year ON building_performance_analytics_mart(ReportingYear);
CREATE INDEX idx_mart_borough ON building_performance_analytics_mart(Borough);
CREATE INDEX idx_mart_property_type ON building_performance_analytics_mart(PrimaryPropertyType);
CREATE INDEX idx_mart_type_group ON building_performance_analytics_mart(PropertyTypeGroup);
CREATE INDEX idx_mart_site_eui ON building_performance_analytics_mart(SiteEUI);
CREATE INDEX idx_mart_high_energy ON building_performance_analytics_mart(IsHighEnergyBuilding);

-- -----------------------------------------------------------------------------
-- 3. Dynamic View (Alternative non-materialized representation)
-- -----------------------------------------------------------------------------
CREATE VIEW vw_building_performance_mart AS
SELECT
    f.FactKey,
    f.PropertyKey,
    p.PropertyID,
    p.PropertyName,
    y.ReportingYear,
    g.Borough,
    g.BoroughGroup,
    pt.PrimaryPropertyType,
    pt.PropertyTypeGroup,
    p.SizeBand,
    pb.EnergyIntensityBand,
    pb.GHGIntensityBand,
    pb.EnergyStarBand,
    f.GrossFloorArea,
    f.SiteEnergyUse,
    f.SiteEUI,
    f.SourceEUI,
    f.GHGEmissions,
    f.WaterUse,
    f.EnergyStarScore,
    CASE WHEN f.GrossFloorArea > 0 THEN ROUND((f.GHGEmissions / f.GrossFloorArea)::numeric, 6) ELSE NULL END AS GHGIntensity,
    CASE WHEN f.GrossFloorArea > 0 AND f.WaterUse IS NOT NULL THEN ROUND((f.WaterUse / f.GrossFloorArea)::numeric, 6) ELSE NULL END AS WaterIntensity,
    f.IsHighEnergyBuilding,
    f.IsHighGHGBuilding
FROM FactBuildingBenchmark f
JOIN DimYear y ON f.YearKey = y.YearKey
JOIN DimProperty p ON f.PropertyKey = p.PropertyKey
JOIN DimGeography g ON f.GeographyKey = g.GeographyKey
JOIN DimPropertyType pt ON f.PropertyTypeKey = pt.PropertyTypeKey
JOIN DimPerformanceBand pb ON f.PerformanceKey = pb.PerformanceKey;
