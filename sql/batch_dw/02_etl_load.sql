-- =============================================================================
-- File: 02_etl_load.sql
-- Project: NYC Building Energy Data Warehouse (Local Law 84)
-- Description: ETL stored procedures/functions for full batch load.
--              Assumes staging_building_energy is already populated.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Helper: safe numeric cast
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION safe_numeric(p_text TEXT)
RETURNS NUMERIC AS $$
BEGIN
    IF p_text IS NULL OR TRIM(p_text) = '' OR TRIM(p_text) = 'N/A' OR TRIM(p_text) = 'Not Available' THEN
        RETURN NULL;
    END IF;
    RETURN p_text::NUMERIC;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ---------------------------------------------------------------------------
-- 1. fn_load_dim_year
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_load_dim_year()
RETURNS TABLE(rows_inserted INT) AS $$
DECLARE
    v_inserted INT;
BEGIN
    WITH src AS (
        SELECT DISTINCT safe_numeric("ReportingYear")::INT AS yr
        FROM staging_building_energy
        WHERE "ReportingYear" IS NOT NULL
    )
    INSERT INTO DimYear (ReportingYear)
    SELECT yr
    FROM src
    WHERE yr IS NOT NULL
    ON CONFLICT (ReportingYear) DO NOTHING;

    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RAISE NOTICE 'fn_load_dim_year: % rows inserted', v_inserted;
    RETURN QUERY SELECT v_inserted;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 2. fn_load_dim_property
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_load_dim_property()
RETURNS TABLE(rows_upserted INT) AS $$
DECLARE
    v_upserted INT := 0;
BEGIN
    -- Insert new PropertyIDs; update if name/type/size changed (SCD Type 1)
    WITH src AS (
        SELECT DISTINCT ON ("PropertyID")
            "PropertyID",
            "PropertyName",
            "PrimaryPropertyType",
            "BuildingSizeBand"              AS SizeBand,
            safe_numeric("GrossFloorArea")  AS GrossFloorArea
        FROM staging_building_energy
        WHERE "PropertyID" IS NOT NULL
        ORDER BY "PropertyID", "ReportingYear" DESC
    )
    INSERT INTO DimProperty (PropertyID, PropertyName, PrimaryPropertyType, SizeBand, GrossFloorArea)
    SELECT "PropertyID", "PropertyName", "PrimaryPropertyType", SizeBand, GrossFloorArea
    FROM src
    ON CONFLICT DO NOTHING;   -- No natural UNIQUE key; handled via PropertyID lookup in fact load

    GET DIAGNOSTICS v_upserted = ROW_COUNT;
    RAISE NOTICE 'fn_load_dim_property: % rows inserted', v_upserted;
    RETURN QUERY SELECT v_upserted;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 3. fn_load_dim_geography
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_load_dim_geography()
RETURNS TABLE(rows_upserted INT) AS $$
DECLARE
    v_upserted INT;
BEGIN
    WITH src AS (
        SELECT DISTINCT
            "Borough",
            COALESCE("BBL", 'Unknown')  AS BBL,
            COALESCE("BIN", 'Unknown')  AS BIN,
            "BoroughGroup"
        FROM staging_building_energy
        WHERE "Borough" IS NOT NULL
    )
    INSERT INTO DimGeography (Borough, BBL, BIN, BoroughGroup)
    SELECT Borough, BBL, BIN, BoroughGroup
    FROM src
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS v_upserted = ROW_COUNT;
    RAISE NOTICE 'fn_load_dim_geography: % rows inserted', v_upserted;
    RETURN QUERY SELECT v_upserted;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 4. fn_load_dim_performance_band
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_load_dim_performance_band()
RETURNS TABLE(rows_upserted INT) AS $$
DECLARE
    v_upserted INT;
BEGIN
    WITH src AS (
        SELECT DISTINCT
            "EnergyIntensityBand",
            "GHGIntensityBand",
            "EnergyPerformanceBand"     AS EnergyStarBand
        FROM staging_building_energy
        WHERE "EnergyIntensityBand" IS NOT NULL
    )
    INSERT INTO DimPerformanceBand (EnergyIntensityBand, GHGIntensityBand, EnergyStarBand)
    SELECT EnergyIntensityBand, GHGIntensityBand, EnergyStarBand
    FROM src
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS v_upserted = ROW_COUNT;
    RAISE NOTICE 'fn_load_dim_performance_band: % rows inserted', v_upserted;
    RETURN QUERY SELECT v_upserted;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 5. fn_load_dim_property_type
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_load_dim_property_type()
RETURNS TABLE(rows_upserted INT) AS $$
DECLARE
    v_upserted INT;
BEGIN
    -- Map PrimaryPropertyType → PropertyTypeGroup
    WITH src AS (
        SELECT DISTINCT
            "PrimaryPropertyType",
            "PropertyTypeGroup"
        FROM staging_building_energy
        WHERE "PrimaryPropertyType" IS NOT NULL
    )
    INSERT INTO DimPropertyType (PrimaryPropertyType, PropertyTypeGroup)
    SELECT "PrimaryPropertyType", "PropertyTypeGroup"
    FROM src
    ON CONFLICT (PrimaryPropertyType) DO UPDATE
        SET PropertyTypeGroup = EXCLUDED.PropertyTypeGroup;

    GET DIAGNOSTICS v_upserted = ROW_COUNT;
    RAISE NOTICE 'fn_load_dim_property_type: % rows inserted/updated', v_upserted;
    RETURN QUERY SELECT v_upserted;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 6. fn_load_fact_building_benchmark
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_load_fact_building_benchmark()
RETURNS TABLE(rows_inserted INT) AS $$
DECLARE
    v_inserted INT;
BEGIN
    INSERT INTO FactBuildingBenchmark (
        YearKey, PropertyKey, GeographyKey, PerformanceKey, PropertyTypeKey,
        PropertyCount, GrossFloorArea,
        SiteEnergyUse, SiteEUI, SourceEUI,
        GHGEmissions, WaterUse, EnergyStarScore,
        IsHighEnergyBuilding, IsHighGHGBuilding
    )
    SELECT
        y.YearKey,
        p.PropertyKey,
        g.GeographyKey,
        pb.PerformanceKey,
        pt.PropertyTypeKey,
        1                                           AS PropertyCount,
        safe_numeric(s."GrossFloorArea"),
        safe_numeric(s."SiteEnergyUse"),
        safe_numeric(s."SiteEUI"),
        safe_numeric(s."SourceEUI"),
        safe_numeric(s."GHGEmissions"),
        safe_numeric(s."WaterUse"),
        safe_numeric(s."EnergyStarScore"),
        CASE WHEN s."IsHighEnergyBuilding" = '1' THEN 1 ELSE 0 END,
        CASE WHEN s."IsHighGHGBuilding"    = '1' THEN 1 ELSE 0 END
    FROM staging_building_energy s
    -- Join dimensions
    JOIN DimYear y
        ON y.ReportingYear = safe_numeric(s."ReportingYear")::INT
    JOIN DimProperty p
        ON p.PropertyID = s."PropertyID"
    JOIN DimGeography g
        ON g.Borough = s."Borough"
       AND g.BBL     = COALESCE(s."BBL", 'Unknown')
       AND g.BIN     = COALESCE(s."BIN", 'Unknown')
    JOIN DimPerformanceBand pb
        ON pb.EnergyIntensityBand = s."EnergyIntensityBand"
       AND pb.GHGIntensityBand    = s."GHGIntensityBand"
       AND pb.EnergyStarBand      = s."EnergyPerformanceBand"
    JOIN DimPropertyType pt
        ON pt.PrimaryPropertyType = s."PrimaryPropertyType";

    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RAISE NOTICE 'fn_load_fact_building_benchmark: % rows inserted', v_inserted;
    RETURN QUERY SELECT v_inserted;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 7. fn_load_fact_borough_aggregate
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_load_fact_borough_aggregate()
RETURNS TABLE(rows_inserted INT) AS $$
DECLARE
    v_inserted INT;
BEGIN
    -- Truncate and reload (full refresh pattern for aggregate fact)
    TRUNCATE TABLE FactBoroughPropertyTypeAnnualPerformance;

    INSERT INTO FactBoroughPropertyTypeAnnualPerformance (
        YearKey, GeographyKey, PropertyTypeKey,
        PropertyCount, TotalFloorArea, TotalEnergyUse,
        AverageSiteEUI, TotalGHG, AverageEnergyStarScore
    )
    SELECT
        f.YearKey,
        f.GeographyKey,
        f.PropertyTypeKey,
        COUNT(*)                        AS PropertyCount,
        SUM(f.GrossFloorArea)           AS TotalFloorArea,
        SUM(f.SiteEnergyUse)            AS TotalEnergyUse,
        AVG(f.SiteEUI)                  AS AverageSiteEUI,
        SUM(f.GHGEmissions)             AS TotalGHG,
        AVG(f.EnergyStarScore)          AS AverageEnergyStarScore
    FROM FactBuildingBenchmark f
    GROUP BY f.YearKey, f.GeographyKey, f.PropertyTypeKey;

    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RAISE NOTICE 'fn_load_fact_borough_aggregate: % aggregate rows inserted', v_inserted;
    RETURN QUERY SELECT v_inserted;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 8. fn_run_full_etl  — orchestrator
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_run_full_etl()
RETURNS VOID AS $$
BEGIN
    RAISE NOTICE '=== Full ETL Started at % ===', NOW();

    PERFORM fn_load_dim_year();
    PERFORM fn_load_dim_property();
    PERFORM fn_load_dim_geography();
    PERFORM fn_load_dim_performance_band();
    PERFORM fn_load_dim_property_type();

    -- Clear fact before full reload
    TRUNCATE TABLE FactBuildingBenchmark RESTART IDENTITY CASCADE;
    PERFORM fn_load_fact_building_benchmark();
    PERFORM fn_load_fact_borough_aggregate();

    RAISE NOTICE '=== Full ETL Completed at % ===', NOW();
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 9. Reconciliation Query
--    Compare staging count vs. fact count per year
-- ---------------------------------------------------------------------------
-- Run after ETL to verify row counts match expectations.
/*
SELECT
    y.ReportingYear,
    stg.staging_count,
    fbb.fact_count,
    stg.staging_count - fbb.fact_count AS unmatched
FROM DimYear y
LEFT JOIN (
    SELECT safe_numeric("ReportingYear")::INT AS yr, COUNT(*) AS staging_count
    FROM staging_building_energy
    GROUP BY yr
) stg ON stg.yr = y.ReportingYear
LEFT JOIN (
    SELECT YearKey, COUNT(*) AS fact_count
    FROM FactBuildingBenchmark
    GROUP BY YearKey
) fbb ON fbb.YearKey = y.YearKey
ORDER BY y.ReportingYear;
*/
