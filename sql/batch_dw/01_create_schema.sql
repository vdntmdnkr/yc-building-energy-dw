-- =============================================================================
-- File: 01_create_schema.sql
-- Project: NYC Building Energy Data Warehouse (Local Law 84)
-- Description: Complete PostgreSQL schema — staging table, dimension tables,
--              and fact tables with FK constraints and indexes.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 0. Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS tablefunc;  -- for crosstab() OLAP queries

-- ---------------------------------------------------------------------------
-- 1. Staging Table
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS staging_building_energy CASCADE;

CREATE TABLE staging_building_energy (
    staging_id          SERIAL PRIMARY KEY,

    -- Identity
    "PropertyID"                TEXT,
    "PropertyName"              TEXT,
    "ReportingYear"             TEXT,

    -- Location
    "Borough"                   TEXT,
    "BBL"                       TEXT,
    "BIN"                       TEXT,
    "Address"                   TEXT,
    "ZipCode"                   TEXT,
    "Latitude"                  TEXT,
    "Longitude"                 TEXT,

    -- Property characteristics
    "PrimaryPropertyType"       TEXT,
    "GrossFloorArea"            TEXT,   -- kSqFt stored as text before parsing
    "NumberOfBuildings"         TEXT,

    -- Energy metrics
    "SiteEnergyUse"             TEXT,   -- kBtu
    "SiteEUI"                   TEXT,   -- kBtu/sqft
    "SourceEUI"                 TEXT,   -- kBtu/sqft
    "WeatherNormalizedSiteEUI"  TEXT,
    "WeatherNormalizedSourceEUI" TEXT,
    "NaturalGasUse"             TEXT,
    "ElectricityUse"            TEXT,
    "SteamUse"                  TEXT,
    "FuelOilUse"                TEXT,
    "DieselUse"                 TEXT,

    -- GHG
    "GHGEmissions"              TEXT,   -- Metric Tons CO2e
    "GHGIntensity"              TEXT,   -- kgCO2e/sqft

    -- Water
    "WaterUse"                  TEXT,   -- kGal
    "WaterIntensity"            TEXT,   -- gal/sqft

    -- ENERGY STAR
    "EnergyStarScore"           TEXT,

    -- Derived / engineered (populated by curation notebook, carried into staging)
    "BuildingSizeBand"          TEXT,
    "EnergyIntensityBand"       TEXT,
    "EnergyPerformanceBand"     TEXT,
    "GHGIntensityBand"          TEXT,
    "WaterIntensityBand"        TEXT,
    "PropertyTypeGroup"         TEXT,
    "BoroughGroup"              TEXT,
    "IsHighEnergyBuilding"      TEXT,
    "IsHighGHGBuilding"         TEXT,

    load_timestamp              TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 2. Dimension Tables
-- ---------------------------------------------------------------------------

-- DimYear
DROP TABLE IF EXISTS DimYear CASCADE;
CREATE TABLE DimYear (
    YearKey         SERIAL      PRIMARY KEY,
    ReportingYear   INT         NOT NULL UNIQUE
);

-- DimProperty
DROP TABLE IF EXISTS DimProperty CASCADE;
CREATE TABLE DimProperty (
    PropertyKey         SERIAL      PRIMARY KEY,
    PropertyID          VARCHAR(50),
    PropertyName        VARCHAR(500),
    PrimaryPropertyType VARCHAR(200),
    SizeBand            VARCHAR(50),    -- Small / Medium / Large
    GrossFloorArea      NUMERIC(15,2)
);

-- DimGeography
DROP TABLE IF EXISTS DimGeography CASCADE;
CREATE TABLE DimGeography (
    GeographyKey    SERIAL      PRIMARY KEY,
    Borough         VARCHAR(100),
    BBL             VARCHAR(50),
    BIN             VARCHAR(50),
    BoroughGroup    VARCHAR(100)        -- same as Borough per spec
);

-- DimPerformanceBand
DROP TABLE IF EXISTS DimPerformanceBand CASCADE;
CREATE TABLE DimPerformanceBand (
    PerformanceKey      SERIAL      PRIMARY KEY,
    EnergyIntensityBand VARCHAR(50),    -- Low / Medium / High / Very High
    GHGIntensityBand    VARCHAR(50),    -- Low / Medium / High / Very High
    EnergyStarBand      VARCHAR(50)     -- Excellent / Good / Fair / Poor
);

-- DimPropertyType
DROP TABLE IF EXISTS DimPropertyType CASCADE;
CREATE TABLE DimPropertyType (
    PropertyTypeKey     SERIAL      PRIMARY KEY,
    PrimaryPropertyType VARCHAR(200) NOT NULL UNIQUE,
    PropertyTypeGroup   VARCHAR(100)    -- Office / Residential / Retail / Industrial / Institutional / Other
);

-- ---------------------------------------------------------------------------
-- 3. Fact Tables
-- ---------------------------------------------------------------------------

-- FactBuildingBenchmark  (grain: one row per property per year)
DROP TABLE IF EXISTS FactBuildingBenchmark CASCADE;
CREATE TABLE FactBuildingBenchmark (
    FactKey                 SERIAL      PRIMARY KEY,

    -- Foreign Keys
    YearKey                 INT         NOT NULL REFERENCES DimYear(YearKey),
    PropertyKey             INT         NOT NULL REFERENCES DimProperty(PropertyKey),
    GeographyKey            INT         NOT NULL REFERENCES DimGeography(GeographyKey),
    PerformanceKey          INT         NOT NULL REFERENCES DimPerformanceBand(PerformanceKey),
    PropertyTypeKey         INT         NOT NULL REFERENCES DimPropertyType(PropertyTypeKey),

    -- Degenerate / additive measures
    PropertyCount           INT         NOT NULL DEFAULT 1,
    GrossFloorArea          NUMERIC(15,2),
    SiteEnergyUse           NUMERIC(15,2),   -- kBtu
    SiteEUI                 NUMERIC(10,4),   -- kBtu/sqft
    SourceEUI               NUMERIC(10,4),
    GHGEmissions            NUMERIC(15,4),   -- Metric Tons CO2e
    WaterUse                NUMERIC(15,2),   -- kGal
    EnergyStarScore         NUMERIC(5,2),

    -- Flags
    IsHighEnergyBuilding    SMALLINT    CHECK (IsHighEnergyBuilding IN (0,1)),
    IsHighGHGBuilding       SMALLINT    CHECK (IsHighGHGBuilding    IN (0,1)),

    LoadTimestamp           TIMESTAMP   DEFAULT NOW()
);

-- FactBoroughPropertyTypeAnnualPerformance  (pre-aggregated fact)
DROP TABLE IF EXISTS FactBoroughPropertyTypeAnnualPerformance CASCADE;
CREATE TABLE FactBoroughPropertyTypeAnnualPerformance (
    FactKey                 SERIAL      PRIMARY KEY,

    -- Foreign Keys
    YearKey                 INT         NOT NULL REFERENCES DimYear(YearKey),
    GeographyKey            INT         NOT NULL REFERENCES DimGeography(GeographyKey),
    PropertyTypeKey         INT         NOT NULL REFERENCES DimPropertyType(PropertyTypeKey),

    -- Aggregate Measures
    PropertyCount           INT,
    TotalFloorArea          NUMERIC(18,2),
    TotalEnergyUse          NUMERIC(18,2),
    AverageSiteEUI          NUMERIC(10,4),
    TotalGHG                NUMERIC(15,4),
    AverageEnergyStarScore  NUMERIC(5,2)
);

-- ---------------------------------------------------------------------------
-- 4. Foreign-Key Indexes
-- ---------------------------------------------------------------------------
-- FactBuildingBenchmark FKs
CREATE INDEX idx_fbb_yearkey        ON FactBuildingBenchmark(YearKey);
CREATE INDEX idx_fbb_propertykey    ON FactBuildingBenchmark(PropertyKey);
CREATE INDEX idx_fbb_geographykey   ON FactBuildingBenchmark(GeographyKey);
CREATE INDEX idx_fbb_performancekey ON FactBuildingBenchmark(PerformanceKey);
CREATE INDEX idx_fbb_propertytypekey ON FactBuildingBenchmark(PropertyTypeKey);

-- FactBoroughPropertyTypeAnnualPerformance FKs
CREATE INDEX idx_fbptap_yearkey         ON FactBoroughPropertyTypeAnnualPerformance(YearKey);
CREATE INDEX idx_fbptap_geographykey    ON FactBoroughPropertyTypeAnnualPerformance(GeographyKey);
CREATE INDEX idx_fbptap_propertytypekey ON FactBoroughPropertyTypeAnnualPerformance(PropertyTypeKey);

-- Commonly queried columns
CREATE INDEX idx_fbb_site_eui       ON FactBuildingBenchmark(SiteEUI);
CREATE INDEX idx_fbb_ghg            ON FactBuildingBenchmark(GHGEmissions);
CREATE INDEX idx_fbb_energy_star    ON FactBuildingBenchmark(EnergyStarScore);
CREATE INDEX idx_fbb_flags          ON FactBuildingBenchmark(IsHighEnergyBuilding, IsHighGHGBuilding);

CREATE INDEX idx_dim_property_type  ON DimProperty(PrimaryPropertyType);
CREATE INDEX idx_dim_property_id    ON DimProperty(PropertyID);
CREATE INDEX idx_dim_geo_borough    ON DimGeography(Borough);
CREATE INDEX idx_dim_geo_bbl        ON DimGeography(BBL);

-- ---------------------------------------------------------------------------
-- 5. Comments
-- ---------------------------------------------------------------------------
COMMENT ON TABLE staging_building_energy IS
    'Raw ingest layer — all columns TEXT or broad type. Populated by COPY from curated CSV.';
COMMENT ON TABLE DimYear IS 'Slowly-changing dimension: calendar year of reporting.';
COMMENT ON TABLE DimProperty IS 'Property master dimension — SCD Type 1 (overwrite).';
COMMENT ON TABLE DimGeography IS 'Geographic dimension: Borough, BBL, BIN.';
COMMENT ON TABLE DimPerformanceBand IS 'Performance band classification for energy, GHG, ENERGY STAR.';
COMMENT ON TABLE DimPropertyType IS 'Property type with broader group mapping.';
COMMENT ON TABLE FactBuildingBenchmark IS 'Core fact table — one row per (property, year) benchmark submission.';
COMMENT ON TABLE FactBoroughPropertyTypeAnnualPerformance IS 'Pre-aggregated fact: Borough × PropertyTypeGroup × Year.';
