-- =============================================================================
-- File: 03_incremental_load.sql
-- Project: NYC Building Energy Data Warehouse (Local Law 84)
-- Description: Incremental ETL — load / refresh a single reporting year.
--              New dimension members are inserted; fact rows for the year
--              are replaced. All work done in a single transaction.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- fn_incremental_load(p_reporting_year INT)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_incremental_load(p_reporting_year INT)
RETURNS TABLE(
    step            TEXT,
    rows_affected   INT
) AS $$
DECLARE
    v_year_key      INT;
    v_new_dim_yr    INT := 0;
    v_new_props     INT := 0;
    v_new_geos      INT := 0;
    v_new_pb        INT := 0;
    v_new_pt        INT := 0;
    v_fact_deleted  INT := 0;
    v_fact_inserted INT := 0;
    v_staging_count INT;
    v_valid_count   INT;
BEGIN
    RAISE NOTICE 'Incremental load starting for year %', p_reporting_year;

    -- ------------------------------------------------------------------
    -- Step 0: Validate staging has data for this year
    -- ------------------------------------------------------------------
    SELECT COUNT(*)
      INTO v_staging_count
      FROM staging_building_energy
     WHERE safe_numeric("ReportingYear")::INT = p_reporting_year;

    IF v_staging_count = 0 THEN
        RAISE EXCEPTION 'No staging data found for ReportingYear = %. Aborting.', p_reporting_year;
    END IF;
    RAISE NOTICE 'Step 0 – Staging row count for %: %', p_reporting_year, v_staging_count;

    -- ------------------------------------------------------------------
    -- Step 1: DimYear — insert if not present
    -- ------------------------------------------------------------------
    INSERT INTO DimYear (ReportingYear)
    VALUES (p_reporting_year)
    ON CONFLICT (ReportingYear) DO NOTHING;

    GET DIAGNOSTICS v_new_dim_yr = ROW_COUNT;

    SELECT YearKey INTO v_year_key
      FROM DimYear
     WHERE ReportingYear = p_reporting_year;

    RAISE NOTICE 'Step 1 – DimYear: % new rows (YearKey = %)', v_new_dim_yr, v_year_key;

    -- ------------------------------------------------------------------
    -- Step 2: DimProperty — insert new PropertyIDs
    -- ------------------------------------------------------------------
    WITH src AS (
        SELECT DISTINCT ON ("PropertyID")
            "PropertyID",
            "PropertyName",
            "PrimaryPropertyType",
            "BuildingSizeBand"              AS SizeBand,
            safe_numeric("GrossFloorArea")  AS GrossFloorArea
        FROM staging_building_energy
        WHERE safe_numeric("ReportingYear")::INT = p_reporting_year
          AND "PropertyID" IS NOT NULL
        ORDER BY "PropertyID"
    )
    INSERT INTO DimProperty (PropertyID, PropertyName, PrimaryPropertyType, SizeBand, GrossFloorArea)
    SELECT "PropertyID", "PropertyName", "PrimaryPropertyType", SizeBand, GrossFloorArea
    FROM src
    WHERE NOT EXISTS (
        SELECT 1 FROM DimProperty p WHERE p.PropertyID = src."PropertyID"
    );

    GET DIAGNOSTICS v_new_props = ROW_COUNT;
    RAISE NOTICE 'Step 2 – DimProperty: % new rows', v_new_props;

    -- ------------------------------------------------------------------
    -- Step 3: DimGeography — insert new Borough/BBL/BIN combos
    -- ------------------------------------------------------------------
    WITH src AS (
        SELECT DISTINCT
            "Borough",
            COALESCE("BBL", 'Unknown')  AS BBL,
            COALESCE("BIN", 'Unknown')  AS BIN,
            "BoroughGroup"
        FROM staging_building_energy
        WHERE safe_numeric("ReportingYear")::INT = p_reporting_year
          AND "Borough" IS NOT NULL
    )
    INSERT INTO DimGeography (Borough, BBL, BIN, BoroughGroup)
    SELECT Borough, BBL, BIN, BoroughGroup
    FROM src
    WHERE NOT EXISTS (
        SELECT 1 FROM DimGeography g
         WHERE g.Borough = src.Borough
           AND g.BBL     = src.BBL
           AND g.BIN     = src.BIN
    );

    GET DIAGNOSTICS v_new_geos = ROW_COUNT;
    RAISE NOTICE 'Step 3 – DimGeography: % new rows', v_new_geos;

    -- ------------------------------------------------------------------
    -- Step 4: DimPerformanceBand — insert new band combos
    -- ------------------------------------------------------------------
    WITH src AS (
        SELECT DISTINCT
            "EnergyIntensityBand",
            "GHGIntensityBand",
            "EnergyPerformanceBand" AS EnergyStarBand
        FROM staging_building_energy
        WHERE safe_numeric("ReportingYear")::INT = p_reporting_year
          AND "EnergyIntensityBand" IS NOT NULL
    )
    INSERT INTO DimPerformanceBand (EnergyIntensityBand, GHGIntensityBand, EnergyStarBand)
    SELECT EnergyIntensityBand, GHGIntensityBand, EnergyStarBand
    FROM src
    WHERE NOT EXISTS (
        SELECT 1 FROM DimPerformanceBand pb
         WHERE pb.EnergyIntensityBand = src.EnergyIntensityBand
           AND pb.GHGIntensityBand    = src.GHGIntensityBand
           AND pb.EnergyStarBand      = src.EnergyStarBand
    );

    GET DIAGNOSTICS v_new_pb = ROW_COUNT;
    RAISE NOTICE 'Step 4 – DimPerformanceBand: % new rows', v_new_pb;

    -- ------------------------------------------------------------------
    -- Step 5: DimPropertyType — insert / update property types
    -- ------------------------------------------------------------------
    WITH src AS (
        SELECT DISTINCT "PrimaryPropertyType", "PropertyTypeGroup"
        FROM staging_building_energy
        WHERE safe_numeric("ReportingYear")::INT = p_reporting_year
          AND "PrimaryPropertyType" IS NOT NULL
    )
    INSERT INTO DimPropertyType (PrimaryPropertyType, PropertyTypeGroup)
    SELECT "PrimaryPropertyType", "PropertyTypeGroup"
    FROM src
    ON CONFLICT (PrimaryPropertyType) DO UPDATE
        SET PropertyTypeGroup = EXCLUDED.PropertyTypeGroup;

    GET DIAGNOSTICS v_new_pt = ROW_COUNT;
    RAISE NOTICE 'Step 5 – DimPropertyType: % rows inserted/updated', v_new_pt;

    -- ------------------------------------------------------------------
    -- Step 6: Validation — ensure all staging rows can join to dims
    -- ------------------------------------------------------------------
    SELECT COUNT(*) INTO v_valid_count
    FROM staging_building_energy s
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
        ON pt.PrimaryPropertyType = s."PrimaryPropertyType"
    WHERE safe_numeric(s."ReportingYear")::INT = p_reporting_year;

    IF v_valid_count < v_staging_count * 0.95 THEN
        RAISE EXCEPTION
            'Validation failed: only % of % staging rows can join to dimensions (< 95%%). '
            'Check dimension load steps.',
            v_valid_count, v_staging_count;
    END IF;
    RAISE NOTICE 'Step 6 – Validation passed: %/% rows joinable', v_valid_count, v_staging_count;

    -- ------------------------------------------------------------------
    -- Step 7: Delete existing fact rows for this year, then reload
    -- ------------------------------------------------------------------
    DELETE FROM FactBuildingBenchmark WHERE YearKey = v_year_key;
    GET DIAGNOSTICS v_fact_deleted = ROW_COUNT;
    RAISE NOTICE 'Step 7 – Fact rows deleted for year %: %', p_reporting_year, v_fact_deleted;

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
        1,
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
        ON pt.PrimaryPropertyType = s."PrimaryPropertyType"
    WHERE safe_numeric(s."ReportingYear")::INT = p_reporting_year;

    GET DIAGNOSTICS v_fact_inserted = ROW_COUNT;
    RAISE NOTICE 'Step 7 – Fact rows inserted for year %: %', p_reporting_year, v_fact_inserted;

    -- ------------------------------------------------------------------
    -- Step 8: Refresh aggregate fact for this year
    -- ------------------------------------------------------------------
    DELETE FROM FactBoroughPropertyTypeAnnualPerformance WHERE YearKey = v_year_key;

    INSERT INTO FactBoroughPropertyTypeAnnualPerformance (
        YearKey, GeographyKey, PropertyTypeKey,
        PropertyCount, TotalFloorArea, TotalEnergyUse,
        AverageSiteEUI, TotalGHG, AverageEnergyStarScore
    )
    SELECT
        f.YearKey, f.GeographyKey, f.PropertyTypeKey,
        COUNT(*)            AS PropertyCount,
        SUM(f.GrossFloorArea),
        SUM(f.SiteEnergyUse),
        AVG(f.SiteEUI),
        SUM(f.GHGEmissions),
        AVG(f.EnergyStarScore)
    FROM FactBuildingBenchmark f
    WHERE f.YearKey = v_year_key
    GROUP BY f.YearKey, f.GeographyKey, f.PropertyTypeKey;

    RAISE NOTICE 'Incremental load for year % completed successfully.', p_reporting_year;

    -- Return summary
    RETURN QUERY VALUES
        ('dim_year_new',        v_new_dim_yr),
        ('dim_property_new',    v_new_props),
        ('dim_geography_new',   v_new_geos),
        ('dim_perf_band_new',   v_new_pb),
        ('dim_prop_type_new',   v_new_pt),
        ('fact_rows_deleted',   v_fact_deleted),
        ('fact_rows_inserted',  v_fact_inserted);
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Example invocation:
-- ---------------------------------------------------------------------------
-- SELECT * FROM fn_incremental_load(2024);
