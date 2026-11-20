-- =============================================================================
-- File: 02_export_mart.sql
-- Project: NYC Building Energy Data Warehouse (Local Law 84)
-- Description: Exports the BuildingPerformanceAnalyticsMart to CSV for downstream
--              use in Jupyter notebooks and Scikit-learn / mlxtend pipelines.
-- =============================================================================

\copy building_performance_analytics_mart TO '/tmp/building_performance_mart.csv' WITH CSV HEADER DELIMITER ',';

-- Summary validation
SELECT 
    COUNT(*) AS exported_row_count,
    COUNT(DISTINCT PropertyID) AS unique_properties,
    MIN(ReportingYear) AS min_year,
    MAX(ReportingYear) AS max_year,
    ROUND(AVG(SiteEUI), 2) AS avg_site_eui,
    ROUND(AVG(GHGEmissions), 2) AS avg_ghg_emissions
FROM building_performance_analytics_mart;
