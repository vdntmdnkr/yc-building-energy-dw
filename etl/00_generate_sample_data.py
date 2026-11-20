"""
00_generate_sample_data.py
==========================
Generates a realistic synthetic sample dataset of NYC Building Energy
and Water Data Disclosure for Local Law 84 (reporting years 2022-2024).

This allows the entire project (profiling, curation, batch ETL, distributed DW,
streaming, OLAP, regression, association mining, decision trees) to run
offline immediately without network dependency or Socrata API token.
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
OUTPUT_CSV = os.path.join(RAW_DIR, "nyc_building_energy.csv")
METADATA_JSON = os.path.join(RAW_DIR, "download_metadata.json")

os.makedirs(RAW_DIR, exist_ok=True)

np.random.seed(42)
random.seed(42)

N_PROPERTIES = 2500  # Will expand across 3 reporting years = ~7500 rows
YEARS = [2022, 2023, 2024]

BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
BOROUGH_WEIGHTS = [0.55, 0.20, 0.15, 0.08, 0.02]

PROPERTY_TYPES = [
    "Multifamily Housing", "Office", "Hotel", "Non-Refrigerated Warehouse",
    "Retail Store", "K-12 School", "College/University", "Hospital (General Medical & Surgical)",
    "Senior Living Community", "Supermarket/Grocery Store", "Worship Facility", "Mixed Use Property"
]
TYPE_WEIGHTS = [0.50, 0.20, 0.06, 0.05, 0.05, 0.04, 0.03, 0.02, 0.02, 0.01, 0.01, 0.01]

# Base properties
properties = []
for i in range(1, N_PROPERTIES + 1):
    pid = 1000000 + i
    borough = random.choices(BOROUGHS, weights=BOROUGH_WEIGHTS)[0]
    ptype = random.choices(PROPERTY_TYPES, weights=TYPE_WEIGHTS)[0]
    pname = f"{borough} {ptype} {i}"
    
    # Area: log-normal distribution around 100,000 sq ft
    gfa = int(np.random.lognormal(mean=11.2, sigma=0.8))
    gfa = max(25000, min(gfa, 3500000))  # LL84 covered buildings >= 25,000 sq ft
    
    bbl = f"{random.randint(1,5)}{random.randint(10000, 99999):05d}{random.randint(1, 9999):04d}"
    bin_num = f"{random.randint(1000000, 5999999)}"
    
    # Base energy intensity by property type
    base_eui = {
        "Multifamily Housing": 75, "Office": 85, "Hotel": 110,
        "Non-Refrigerated Warehouse": 35, "Retail Store": 90, "K-12 School": 60,
        "College/University": 105, "Hospital (General Medical & Surgical)": 240,
        "Senior Living Community": 95, "Supermarket/Grocery Store": 220,
        "Worship Facility": 45, "Mixed Use Property": 80
    }.get(ptype, 75)
    
    properties.append({
        "PropertyID": pid,
        "PropertyName": pname,
        "Borough": borough,
        "PrimaryPropertyType": ptype,
        "BaseGFA": gfa,
        "BBL": bbl,
        "BIN": bin_num,
        "BaseEUI": base_eui
    })

records = []
for p in properties:
    for yr in YEARS:
        # Slight yearly efficiency trend (-1.5% per year) + random variation
        year_factor = 1.0 - (yr - 2022) * 0.015
        eui_noise = np.random.normal(loc=0, scale=0.18 * p["BaseEUI"])
        site_eui = max(10.0, p["BaseEUI"] * year_factor + eui_noise)
        
        # Source EUI typically 1.5 - 2.8 times Site EUI (electric mix)
        source_eui = site_eui * np.random.uniform(1.8, 2.5)
        
        # Energy use = SiteEUI * GrossFloorArea (kBtu)
        gfa = p["BaseGFA"]
        site_energy = site_eui * gfa
        
        # GHG emissions in metric tons CO2e (typically ~0.005 to 0.01 tCO2e/sqft depending on fuels)
        ghg_factor = np.random.uniform(0.004, 0.009)
        ghg = (site_energy / 1000.0) * np.random.uniform(0.05, 0.08)
        
        # Water use in kgal
        water_use = (gfa / 1000.0) * np.random.uniform(15.0, 60.0) if random.random() > 0.15 else np.nan
        
        # Energy Star Score (1-100) — inversely correlated with SiteEUI
        # Higher score = lower EUI
        score = int(np.clip(100 - (site_eui / 150.0) * 60 + np.random.normal(0, 12), 1, 100))
        if p["PrimaryPropertyType"] in ["Non-Refrigerated Warehouse", "Worship Facility", "Mixed Use Property"]:
            if random.random() > 0.3:
                score = np.nan  # Some property types not eligible for Energy Star
                
        # Inject realistic data quality nuances for Curation Pipeline:
        # 1. A few missing GFAs (<0.5%)
        cur_gfa = gfa
        if random.random() < 0.005:
            cur_gfa = np.nan
            
        # 2. A few extreme EUI outliers (e.g. data entry error like 5000 EUI)
        if random.random() < 0.008:
            site_eui = site_eui * 15.0
            
        # 3. Occasional missing energy values
        if random.random() < 0.01:
            site_eui = np.nan
            source_eui = np.nan

        records.append({
            "property_id": str(p["PropertyID"]),
            "property_name": p["PropertyName"],
            "borough": p["Borough"],
            "primary_property_type_self_selected": p["PrimaryPropertyType"],
            "gross_floor_area_buildings_sq_ft": cur_gfa,
            "site_eui_kbtu_ft²": round(site_eui, 2) if not np.isnan(site_eui) else np.nan,
            "source_eui_kbtu_ft²": round(source_eui, 2) if not np.isnan(source_eui) else np.nan,
            "total_ghg_emissions_metric_tons_co2e": round(ghg, 2),
            "water_use_kgal": round(water_use, 2) if not np.isnan(water_use) else np.nan,
            "energy_star_score": score if not np.isnan(score) else np.nan,
            "reporting_year": yr,
            "bbl_10_digits_": p["BBL"],
            "bin": p["BIN"]
        })

df = pd.DataFrame(records)

# Add a few exact duplicate rows (for quality profiling & cleaning testing)
duplicates = df.sample(n=15, random_state=123)
df = pd.concat([df, duplicates], ignore_index=True)

# Add borough code variation (e.g., 'MN' for Manhattan, 'BK' for Brooklyn in a few rows)
code_map = {"Manhattan": "MN", "Brooklyn": "BK", "Queens": "QN", "Bronx": "BX", "Staten Island": "SI"}
sample_idx = df.sample(n=30, random_state=456).index
df.loc[sample_idx, "borough"] = df.loc[sample_idx, "borough"].map(lambda b: code_map.get(b, b))

df.to_csv(OUTPUT_CSV, index=False)
print(f"Generated realistic NYC Local Law 84 dataset at: {OUTPUT_CSV}")
print(f"Total Rows: {len(df)}, Total Columns: {len(df.columns)}")
print(f"Reporting Years: {sorted(df['reporting_year'].dropna().unique())}")

metadata = {
    "source": "NYC Building Energy and Water Data Disclosure (Local Law 84) - Sample / Real Distribution",
    "generation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "official_url": "https://data.cityofnewyork.us/Environment/NYC-Building-Energy-and-Water-Data-Disclosure-for-/5zyy-y8am/about_data",
    "row_count": len(df),
    "columns": list(df.columns),
    "reporting_years": [int(y) for y in sorted(df['reporting_year'].dropna().unique())]
}
with open(METADATA_JSON, "w") as f:
    json.dump(metadata, f, indent=2)
