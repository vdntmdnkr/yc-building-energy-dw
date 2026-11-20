-- =============================================================================
-- File: 05_indexing.sql
-- Project: NYC Building Energy Data Warehouse (Local Law 84)
-- Description: Additional index definitions beyond those in 01_create_schema.sql.
--              Includes cluster recommendation comments.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- FactBuildingBenchmark — FK indexes (idempotent: IF NOT EXISTS)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_fbb_yearkey
    ON FactBuildingBenchmark(YearKey);

CREATE INDEX IF NOT EXISTS idx_fbb_propertykey
    ON FactBuildingBenchmark(PropertyKey);

CREATE INDEX IF NOT EXISTS idx_fbb_geographykey
    ON FactBuildingBenchmark(GeographyKey);

CREATE INDEX IF NOT EXISTS idx_fbb_performancekey
    ON FactBuildingBenchmark(PerformanceKey);

CREATE INDEX IF NOT EXISTS idx_fbb_propertytypekey
    ON FactBuildingBenchmark(PropertyTypeKey);

-- ---------------------------------------------------------------------------
-- FactBuildingBenchmark — Measure / filter indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_fact_site_eui
    ON FactBuildingBenchmark(SiteEUI);
-- Purpose: Speeds up range queries and ORDER BY on SiteEUI (Q2, Q7, Q9).

CREATE INDEX IF NOT EXISTS idx_fact_ghg
    ON FactBuildingBenchmark(GHGEmissions);
-- Purpose: Speeds up GHG aggregation and ranking queries (Q4, Q10).

CREATE INDEX IF NOT EXISTS idx_fact_water_use
    ON FactBuildingBenchmark(WaterUse);
-- Purpose: Speeds up water intensity queries (Q8).

CREATE INDEX IF NOT EXISTS idx_fact_energy_star
    ON FactBuildingBenchmark(EnergyStarScore);
-- Purpose: Speeds up ENERGY STAR distribution queries (Q6).

CREATE INDEX IF NOT EXISTS idx_fact_flags
    ON FactBuildingBenchmark(IsHighEnergyBuilding, IsHighGHGBuilding);
-- Purpose: Fast bitmap scan for high-performer filter (Q7).

-- Composite index for the most common analytical join path:
-- YearKey + GeographyKey for borough×year aggregations (Q3, Q10)
CREATE INDEX IF NOT EXISTS idx_fbb_year_geo
    ON FactBuildingBenchmark(YearKey, GeographyKey);

-- Composite index for property-type × year (Q2 with year filter)
CREATE INDEX IF NOT EXISTS idx_fbb_year_proptype
    ON FactBuildingBenchmark(YearKey, PropertyTypeKey);

-- ---------------------------------------------------------------------------
-- DimProperty indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_dim_property_type
    ON DimProperty(PrimaryPropertyType);
-- Purpose: Join/filter on property type text in ad-hoc queries.

CREATE INDEX IF NOT EXISTS idx_dim_property_id
    ON DimProperty(PropertyID);
-- Purpose: Incremental load lookups by PropertyID.

CREATE INDEX IF NOT EXISTS idx_dim_property_sizeband
    ON DimProperty(SizeBand);
-- Purpose: Filter and GROUP BY SizeBand (Q5).

-- ---------------------------------------------------------------------------
-- DimGeography indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_dim_geo_borough
    ON DimGeography(Borough);
-- Purpose: Borough grouping and filter — most common geographic dimension join.

CREATE INDEX IF NOT EXISTS idx_dim_geo_bbl
    ON DimGeography(BBL);
-- Purpose: Specific building lookup by BBL (tax lot identifier).

-- ---------------------------------------------------------------------------
-- DimPropertyType indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_dim_proptype_group
    ON DimPropertyType(PropertyTypeGroup);
-- Purpose: GROUP BY PropertyTypeGroup without reading PrimaryPropertyType.

-- ---------------------------------------------------------------------------
-- FactBoroughPropertyTypeAnnualPerformance — FK indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_fbptap_yearkey
    ON FactBoroughPropertyTypeAnnualPerformance(YearKey);

CREATE INDEX IF NOT EXISTS idx_fbptap_geographykey
    ON FactBoroughPropertyTypeAnnualPerformance(GeographyKey);

CREATE INDEX IF NOT EXISTS idx_fbptap_propertytypekey
    ON FactBoroughPropertyTypeAnnualPerformance(PropertyTypeKey);

-- ---------------------------------------------------------------------------
-- CLUSTER recommendation
-- ---------------------------------------------------------------------------
-- After the full ETL, clustering FactBuildingBenchmark on the YearKey index
-- physically orders rows on disk by year, which dramatically speeds up
-- year-based range scans (Q1, Q10) by reducing random I/O.
--
-- Run once after initial full load (requires an ACCESS EXCLUSIVE lock):
--
--   CLUSTER FactBuildingBenchmark USING idx_fbb_yearkey;
--   ANALYZE FactBuildingBenchmark;
--
-- Note: CLUSTER is a one-time operation; new rows inserted after clustering
-- will NOT be in order. Re-run after large bulk loads or on a maintenance
-- schedule (e.g., weekly off-peak window).
--
-- For the aggregate fact table, cluster by (YearKey, GeographyKey):
--
--   CLUSTER FactBoroughPropertyTypeAnnualPerformance USING idx_fbptap_yearkey;
--   ANALYZE FactBoroughPropertyTypeAnnualPerformance;
--
-- ---------------------------------------------------------------------------
-- ANALYZE to update planner statistics after index creation
-- ---------------------------------------------------------------------------
ANALYZE FactBuildingBenchmark;
ANALYZE FactBoroughPropertyTypeAnnualPerformance;
ANALYZE DimProperty;
ANALYZE DimGeography;
ANALYZE DimPropertyType;
ANALYZE DimPerformanceBand;
ANALYZE DimYear;
