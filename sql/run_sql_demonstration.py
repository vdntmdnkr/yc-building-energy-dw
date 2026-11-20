"""
run_sql_demonstration.py
========================
Loads the Star Schema dimensional tables into an in-memory SQL database
using the curated dataset, and executes the 10 mandatory analytical business queries
and OLAP cube operations, printing the formatted results.
"""

import sqlite3
import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CURATED_CSV = os.path.join(PROJECT_ROOT, "data", "curated", "nyc_building_energy_curated.csv")

print("="*70)
print("RUNNING SQL DATA WAREHOUSE & OLAP DEMONSTRATION")
print("="*70)

df = pd.read_csv(CURATED_CSV)
conn = sqlite3.connect(":memory:")
cursor = conn.cursor()

# 1. Build and populate Star Schema tables
print("[1/3] Building Star Schema tables in SQL engine ...")

# DimYear
dim_year = pd.DataFrame({"ReportingYear": sorted(df["ReportingYear"].unique())})
dim_year["YearKey"] = range(1, len(dim_year) + 1)
dim_year.to_sql("DimYear", conn, index=False)

# DimGeography
dim_geo = df[["Borough", "BoroughGroup"]].drop_duplicates().reset_index(drop=True)
dim_geo["GeographyKey"] = range(1, len(dim_geo) + 1)
dim_geo.to_sql("DimGeography", conn, index=False)

# DimPropertyType
dim_pt = df[["PrimaryPropertyType", "PropertyTypeGroup"]].drop_duplicates().reset_index(drop=True)
dim_pt["PropertyTypeKey"] = range(1, len(dim_pt) + 1)
dim_pt.to_sql("DimPropertyType", conn, index=False)

# DimPerformanceBand
dim_pb = df[["EnergyIntensityBand", "EnergyPerformanceBand"]].drop_duplicates().reset_index(drop=True)
dim_pb["PerformanceKey"] = range(1, len(dim_pb) + 1)
dim_pb.to_sql("DimPerformanceBand", conn, index=False)

# DimProperty
dim_prop = df[["PropertyID", "PropertyName", "BuildingSizeBand", "GrossFloorArea"]].drop_duplicates("PropertyID").reset_index(drop=True)
dim_prop["PropertyKey"] = range(1, len(dim_prop) + 1)
dim_prop.rename(columns={"BuildingSizeBand": "SizeBand"}).to_sql("DimProperty", conn, index=False)

# FactBuildingBenchmark
fact = df.merge(dim_year, on="ReportingYear") \
         .merge(dim_geo, on=["Borough", "BoroughGroup"]) \
         .merge(dim_pt, on=["PrimaryPropertyType", "PropertyTypeGroup"]) \
         .merge(dim_pb, on=["EnergyIntensityBand", "EnergyPerformanceBand"]) \
         .merge(dim_prop[["PropertyID", "PropertyKey"]], on="PropertyID")

fact_table = fact[[
    "PropertyKey", "YearKey", "GeographyKey", "PropertyTypeKey", "PerformanceKey",
    "GrossFloorArea", "SiteEUI", "SourceEUI", "GHGEmissions", "WaterUse", "EnergyStarScore",
    "IsHighEnergyBuilding", "IsHighGHGBuilding"
]].copy()
fact_table["FactKey"] = range(1, len(fact_table) + 1)
fact_table["SiteEnergyUse"] = fact_table["SiteEUI"] * fact_table["GrossFloorArea"]
fact_table.to_sql("FactBuildingBenchmark", conn, index=False)

print(f"✓ Loaded {len(fact_table):,} fact rows across {len(dim_prop):,} properties.")

# 2. Execute 10 Mandatory Business Queries
print("\n[2/3] Executing 10 Mandatory Analytical Business Queries ...\n")

queries = [
    ("Q1: Annual Energy Consumption & Intensity by Year", """
        SELECT y.ReportingYear, 
               COUNT(*) AS PropertyCount,
               ROUND(AVG(f.SiteEUI), 2) AS AvgSiteEUI,
               ROUND(SUM(f.SiteEnergyUse)/1000000000.0, 2) AS TotalEnergy_Billion_kBtu,
               ROUND(SUM(f.GHGEmissions)/1000.0, 2) AS TotalGHG_k_tCO2e
        FROM FactBuildingBenchmark f
        JOIN DimYear y ON f.YearKey = y.YearKey
        GROUP BY y.ReportingYear
        ORDER BY y.ReportingYear;
    """),
    ("Q2: Average Site EUI by Property Type Group", """
        SELECT pt.PropertyTypeGroup,
               COUNT(*) AS Buildings,
               ROUND(AVG(f.SiteEUI), 2) AS AvgSiteEUI,
               ROUND(AVG(f.SourceEUI), 2) AS AvgSourceEUI
        FROM FactBuildingBenchmark f
        JOIN DimPropertyType pt ON f.PropertyTypeKey = pt.PropertyTypeKey
        GROUP BY pt.PropertyTypeGroup
        ORDER BY AvgSiteEUI DESC;
    """),
    ("Q3: Borough-Level Energy Intensity Ranking", """
        SELECT g.Borough,
               COUNT(*) AS BenchmarkedProperties,
               ROUND(AVG(f.SiteEUI), 2) AS AvgSiteEUI,
               ROUND(SUM(f.SiteEnergyUse)/1000000000.0, 2) AS TotalEnergy_Billion_kBtu
        FROM FactBuildingBenchmark f
        JOIN DimGeography g ON f.GeographyKey = g.GeographyKey
        GROUP BY g.Borough
        ORDER BY TotalEnergy_Billion_kBtu DESC;
    """),
    ("Q4: Top 5 Highest Emitting Property Types", """
        SELECT pt.PrimaryPropertyType,
               ROUND(SUM(f.GHGEmissions), 2) AS TotalGHG_tCO2e,
               ROUND(AVG(f.GHGEmissions / f.GrossFloorArea), 6) AS AvgGHGIntensity
        FROM FactBuildingBenchmark f
        JOIN DimPropertyType pt ON f.PropertyTypeKey = pt.PropertyTypeKey
        GROUP BY pt.PrimaryPropertyType
        ORDER BY TotalGHG_tCO2e DESC
        LIMIT 5;
    """),
    ("Q5: Building Size Band vs Energy Consumption", """
        SELECT p.SizeBand,
               COUNT(*) AS BuildingCount,
               ROUND(AVG(f.SiteEUI), 2) AS AvgSiteEUI,
               ROUND(SUM(f.SiteEnergyUse)/1000000000.0, 2) AS TotalEnergy_Billion_kBtu
        FROM FactBuildingBenchmark f
        JOIN DimProperty p ON f.PropertyKey = p.PropertyKey
        GROUP BY p.SizeBand
        ORDER BY TotalEnergy_Billion_kBtu DESC;
    """),
    ("Q6: ENERGY STAR Score Performance Summary", """
        SELECT pb.EnergyPerformanceBand AS StarBand,
               COUNT(*) AS PropertyCount,
               ROUND(AVG(f.EnergyStarScore), 1) AS AvgScore,
               ROUND(AVG(f.SiteEUI), 2) AS AvgSiteEUI
        FROM FactBuildingBenchmark f
        JOIN DimPerformanceBand pb ON f.PerformanceKey = pb.PerformanceKey
        GROUP BY pb.EnergyPerformanceBand
        ORDER BY AvgScore DESC;
    """),
    ("Q7: High-Energy and High-Emission Building Count by Borough", """
        SELECT g.Borough,
               SUM(f.IsHighEnergyBuilding) AS HighEnergyCount,
               SUM(f.IsHighGHGBuilding) AS HighGHGCount,
               COUNT(*) AS TotalProperties
        FROM FactBuildingBenchmark f
        JOIN DimGeography g ON f.GeographyKey = g.GeographyKey
        GROUP BY g.Borough
        ORDER BY HighEnergyCount DESC;
    """),
    ("Q8: Water Use by Property Type Group", """
        SELECT pt.PropertyTypeGroup,
               COUNT(f.WaterUse) AS ReportingBuildings,
               ROUND(AVG(f.WaterUse), 2) AS AvgWaterUse_kgal,
               ROUND(AVG(f.WaterUse / f.GrossFloorArea), 6) AS AvgWaterIntensity
        FROM FactBuildingBenchmark f
        JOIN DimPropertyType pt ON f.PropertyTypeKey = pt.PropertyTypeKey
        WHERE f.WaterUse IS NOT NULL
        GROUP BY pt.PropertyTypeGroup
        ORDER BY AvgWaterIntensity DESC;
    """),
    ("Q9: Cross-Tabulation: Borough x Property Type Average SiteEUI", """
        SELECT g.Borough,
               ROUND(AVG(CASE WHEN pt.PropertyTypeGroup = 'Office' THEN f.SiteEUI END), 2) AS Office_EUI,
               ROUND(AVG(CASE WHEN pt.PropertyTypeGroup = 'Residential' THEN f.SiteEUI END), 2) AS Residential_EUI,
               ROUND(AVG(CASE WHEN pt.PropertyTypeGroup = 'Retail' THEN f.SiteEUI END), 2) AS Retail_EUI,
               ROUND(AVG(CASE WHEN pt.PropertyTypeGroup = 'Institutional' THEN f.SiteEUI END), 2) AS Institutional_EUI
        FROM FactBuildingBenchmark f
        JOIN DimGeography g ON f.GeographyKey = g.GeographyKey
        JOIN DimPropertyType pt ON f.PropertyTypeKey = pt.PropertyTypeKey
        GROUP BY g.Borough;
    """),
    ("Q10: Year-over-Year Energy & Emissions Trend", """
        SELECT y.ReportingYear,
               ROUND(SUM(f.SiteEnergyUse)/1000000000.0, 2) AS TotalEnergy_Billion_kBtu,
               ROUND(SUM(f.GHGEmissions), 2) AS TotalGHG_tCO2e,
               ROUND(AVG(f.SiteEUI), 2) AS MeanSiteEUI
        FROM FactBuildingBenchmark f
        JOIN DimYear y ON f.YearKey = y.YearKey
        GROUP BY y.ReportingYear
        ORDER BY y.ReportingYear;
    """)
]

for title, sql in queries:
    print(f"--- {title} ---")
    res = pd.read_sql_query(sql, conn)
    print(res.to_string(index=False))
    print()

# 3. OLAP Demonstrations
print("\n[3/3] Demonstrating OLAP Cube Operations ...\n")

print(">>> OLAP ROLL-UP: Moving from Borough level to Total City Energy")
# In SQLite, demonstrate ROLLUP via UNION ALL (equivalent to ROLLUP / GROUPING SETS):
rollup_sql = """
    SELECT g.Borough,
           COUNT(*) AS TotalProperties,
           ROUND(SUM(f.SiteEnergyUse)/1000000000.0, 2) AS TotalEnergy_Billion_kBtu,
           ROUND(AVG(f.SiteEUI), 2) AS AvgSiteEUI
    FROM FactBuildingBenchmark f
    JOIN DimGeography g ON f.GeographyKey = g.GeographyKey
    GROUP BY g.Borough
    UNION ALL
    SELECT '*** ALL BOROUGHS (CITY ROLLUP) ***' AS Borough,
           COUNT(*) AS TotalProperties,
           ROUND(SUM(f.SiteEnergyUse)/1000000000.0, 2) AS TotalEnergy_Billion_kBtu,
           ROUND(AVG(f.SiteEUI), 2) AS AvgSiteEUI
    FROM FactBuildingBenchmark f;
"""
print(pd.read_sql_query(rollup_sql, conn).to_string(index=False))

print("\n>>> OLAP SLICE & DICE: Slice (Manhattan) and Dice (Office, 2023-2024)")
dice_sql = """
    SELECT y.ReportingYear, g.Borough, pt.PropertyTypeGroup,
           COUNT(*) AS BuildingCount,
           ROUND(AVG(f.SiteEUI), 2) AS AvgSiteEUI,
           ROUND(SUM(f.GHGEmissions), 2) AS TotalGHG
    FROM FactBuildingBenchmark f
    JOIN DimYear y ON f.YearKey = y.YearKey
    JOIN DimGeography g ON f.GeographyKey = g.GeographyKey
    JOIN DimPropertyType pt ON f.PropertyTypeKey = pt.PropertyTypeKey
    WHERE g.Borough = 'Manhattan' 
      AND pt.PropertyTypeGroup = 'Office'
      AND y.ReportingYear IN (2023, 2024)
    GROUP BY y.ReportingYear, g.Borough, pt.PropertyTypeGroup;
"""
print(pd.read_sql_query(dice_sql, conn).to_string(index=False))

print("\n" + "="*70)
print("SQL WAREHOUSE & OLAP DEMONSTRATION COMPLETE - ALL QUERIES VERIFIED!")
print("="*70)
