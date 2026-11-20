"""
02_data_curation.py
===================
Full data-cleaning and feature-engineering pipeline for the NYC Building
Energy dataset.

Every decision is logged to CLEANING_LOG (saved as cleaning_log.json).

Usage:
    python 02_data_curation.py [--input PATH] [--output PATH]

Requirements:
    pip install pandas numpy
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

try:
    import numpy as np
    import pandas as pd
except ImportError:
    print("ERROR: 'pandas' and 'numpy' are required.")
    print("Install:  pip install pandas numpy")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_INPUT = os.path.join(PROJECT_ROOT, "data", "raw", "nyc_building_energy.csv")
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "data", "curated", "nyc_building_energy_curated.csv")
STAGING_DIR = os.path.join(PROJECT_ROOT, "data", "staging")
CLEANING_LOG_PATH = os.path.join(STAGING_DIR, "cleaning_log.json")

# ---------------------------------------------------------------------------
# Cleaning log
# ---------------------------------------------------------------------------
CLEANING_LOG: list[dict] = []


def log_decision(field: str, issue: str, treatment: str, count: int | str, notes: str = ""):
    """Record a data-cleaning decision."""
    entry = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "field": field,
        "issue": issue,
        "treatment": treatment,
        "count_affected": count,
        "notes": notes,
    }
    CLEANING_LOG.append(entry)
    print(f"  [LOG] {field}: {issue} → {treatment}  (affected={count})"
          + (f"  [{notes}]" if notes else ""))


# ---------------------------------------------------------------------------
# Column rename mapping
# Handles the many spelling variants NYC Open Data uses across years.
# ---------------------------------------------------------------------------

# Maps (possible raw name fragments, case-insensitive) → canonical name
RENAME_MAP = {
    # PropertyID
    "property_id": "PropertyID",
    "propertyid": "PropertyID",
    "property id": "PropertyID",
    # PropertyName
    "property_name": "PropertyName",
    "propertyname": "PropertyName",
    "property name": "PropertyName",
    # Borough
    "borough": "Borough",
    # PrimaryPropertyType
    "primary_property_type_self_selected": "PrimaryPropertyType",
    "primarypropertytype": "PrimaryPropertyType",
    "primary_property_type": "PrimaryPropertyType",
    "primary property type - self selected": "PrimaryPropertyType",
    # GrossFloorArea
    "gross_floor_area_buildings_sq_ft": "GrossFloorArea",
    "gross_floor_area": "GrossFloorArea",
    "gross floor area - buildings (sq ft)": "GrossFloorArea",
    "grossfloorarea": "GrossFloorArea",
    # SiteEUI
    "site_eui_kbtu_ft": "SiteEUI",
    "site_eui": "SiteEUI",
    "site eui (kbtu/ft²)": "SiteEUI",
    "siteeui": "SiteEUI",
    # SourceEUI
    "source_eui_kbtu_ft": "SourceEUI",
    "source_eui": "SourceEUI",
    "source eui (kbtu/ft²)": "SourceEUI",
    "sourceeui": "SourceEUI",
    # GHGEmissions
    "total_ghg_emissions_metric_tons_co2e": "GHGEmissions",
    "ghg_emissions_metric_tons_co2e": "GHGEmissions",
    "total ghg emissions (metric tons co2e)": "GHGEmissions",
    "ghgemissions": "GHGEmissions",
    # WaterUse
    "water_use_kgal": "WaterUse",
    "water_use": "WaterUse",
    "water use (kgal)": "WaterUse",
    "wateruse": "WaterUse",
    # EnergyStarScore
    "energy_star_score": "EnergyStarScore",
    "energystarscore": "EnergyStarScore",
    "energy star score": "EnergyStarScore",
    # ReportingYear
    "reporting_year": "ReportingYear",
    "reportingyear": "ReportingYear",
    "reporting year": "ReportingYear",
    # BBL
    "bbl_10_digits_": "BBL",
    "bbl": "BBL",
    # BIN
    "bin": "BIN",
}

# Borough code → full name
BOROUGH_MAP = {
    "MN": "Manhattan",
    "BK": "Brooklyn",
    "QN": "Queens",
    "BX": "Bronx",
    "SI": "Staten Island",
    "MANHATTAN": "Manhattan",
    "BROOKLYN": "Brooklyn",
    "QUEENS": "Queens",
    "BRONX": "Bronx",
    "STATEN ISLAND": "Staten Island",
}

# PrimaryPropertyType → PropertyTypeGroup
PROPERTY_TYPE_GROUP_MAP = {
    # Office
    "Office": "Office",
    "Financial Office": "Office",
    "Medical Office": "Office",
    # Residential
    "Multifamily Housing": "Residential",
    "Residence Hall/Dormitory": "Residential",
    "Residential Care Facility": "Residential",
    "Senior Care Community": "Residential",
    # Retail
    "Retail Store": "Retail",
    "Supermarket/Grocery Store": "Retail",
    "Food Sales": "Retail",
    "Restaurant": "Retail",
    "Food Service": "Retail",
    "Fast Food Restaurant": "Retail",
    "Bar/Nightclub": "Retail",
    # Industrial
    "Warehouse/Storage": "Industrial",
    "Distribution Center": "Industrial",
    "Manufacturing/Industrial Plant": "Industrial",
    "Laboratory": "Industrial",
    "Data Center": "Industrial",
    # Institutional
    "K-12 School": "Institutional",
    "College/University": "Institutional",
    "Hospital (General Medical & Surgical)": "Institutional",
    "Medical Office": "Institutional",
    "Library": "Institutional",
    "Museum": "Institutional",
    "Religious Worship": "Institutional",
    "Police Station": "Institutional",
    "Fire Station": "Institutional",
    "Court": "Institutional",
    "Prison/Incarceration": "Institutional",
    "Social/Meeting Hall": "Institutional",
    "Recreation": "Institutional",
    "Fitness Center/Health Club/Gym": "Institutional",
    "Hotel": "Institutional",
    "Other - Education": "Institutional",
    "Other - Public Services": "Institutional",
    "Other - Health Care": "Institutional",
    "Outpatient Rehabilitation/Physical Therapy": "Institutional",
    "Urgent Care/Clinic/Other Outpatient": "Institutional",
    "Worship Facility": "Institutional",
    "Performing Arts": "Institutional",
    "Movie Theater": "Institutional",
    "Stadium (Open)": "Institutional",
    "Stadium (Closed)": "Institutional",
    "Swimming Pool": "Institutional",
    "Ice/Curling Rink": "Institutional",
    "Automobile Dealership": "Industrial",
    "Parking": "Industrial",
    "Self-Storage Facility": "Industrial",
    "Mixed Use Property": "Other",
    "Other": "Other",
}


def map_property_type_group(pt: str) -> str:
    """Return the broad group for a property type string."""
    if pd.isna(pt):
        return "Other"
    # Exact match first
    if pt in PROPERTY_TYPE_GROUP_MAP:
        return PROPERTY_TYPE_GROUP_MAP[pt]
    # Fuzzy: check if any key is a substring
    pt_lower = pt.lower()
    for key, group in PROPERTY_TYPE_GROUP_MAP.items():
        if key.lower() in pt_lower:
            return group
    return "Other"


# ---------------------------------------------------------------------------
# Main cleaning pipeline
# ---------------------------------------------------------------------------

def run_pipeline(input_path: str, output_path: str) -> pd.DataFrame:
    """Execute the full cleaning and feature-engineering pipeline."""

    # ---- Step 1: Load raw CSV ----
    print("\n[1] Loading raw CSV …")
    df = pd.read_csv(input_path, low_memory=False)
    initial_shape = df.shape
    print(f"    Initial shape: {initial_shape[0]:,} rows × {initial_shape[1]} columns")
    log_decision("ALL", "initial load", "read CSV", f"{initial_shape[0]} rows × {initial_shape[1]} cols")

    # ---- Step 2: Rename columns ----
    print("\n[2] Renaming columns to standard names …")
    rename_actual: dict[str, str] = {}
    for raw_col in df.columns:
        # Try exact lowercase match first, then strip special chars
        key = raw_col.lower().strip()
        # Remove superscript chars (² etc.) which appear in EUI column names
        key_clean = key.replace("²", "").replace("²", "").replace("2", "").strip()
        if key in RENAME_MAP:
            rename_actual[raw_col] = RENAME_MAP[key]
        elif key_clean in RENAME_MAP:
            rename_actual[raw_col] = RENAME_MAP[key_clean]
        else:
            # Partial match: check if any RENAME_MAP key is a prefix/suffix
            for map_key, canonical in RENAME_MAP.items():
                if map_key in key or key in map_key:
                    rename_actual[raw_col] = canonical
                    break

    df.rename(columns=rename_actual, inplace=True)
    renamed_cols = {k: v for k, v in rename_actual.items() if k != v}
    print(f"    Renamed {len(renamed_cols)} columns: {renamed_cols}")
    log_decision("columns", "non-standard names", "renamed to canonical", len(renamed_cols),
                 notes=str(renamed_cols))

    # ---- Step 3: Convert numeric columns ----
    print("\n[3] Converting columns to numeric (coerce errors → NaN) …")
    NUMERIC_COLS = ["GrossFloorArea", "SiteEUI", "SourceEUI", "GHGEmissions",
                    "WaterUse", "EnergyStarScore"]
    for col in NUMERIC_COLS:
        if col in df.columns:
            before_nulls = df[col].isna().sum()
            df[col] = pd.to_numeric(df[col], errors="coerce")
            after_nulls = df[col].isna().sum()
            new_nulls = after_nulls - before_nulls
            if new_nulls > 0:
                log_decision(col, "non-numeric values", "coerced to NaN", new_nulls)
        else:
            print(f"    WARNING: Expected column '{col}' not found in dataset.")

    # ---- Step 4: Filter ReportingYear >= 2022 ----
    print("\n[4] Filtering ReportingYear >= 2022 …")
    if "ReportingYear" in df.columns:
        df["ReportingYear"] = pd.to_numeric(df["ReportingYear"], errors="coerce")
        before = len(df)
        df = df[df["ReportingYear"] >= 2022].copy()
        dropped = before - len(df)
        log_decision("ReportingYear", "year < 2022", "excluded rows", dropped)
        print(f"    Removed {dropped:,} rows with ReportingYear < 2022.  Remaining: {len(df):,}")
    else:
        print("    WARNING: 'ReportingYear' column not found — skipping year filter.")

    # ---- Step 5: Drop exact duplicates ----
    print("\n[5] Dropping exact duplicate rows …")
    before = len(df)
    df.drop_duplicates(inplace=True)
    dropped = before - len(df)
    log_decision("ALL", "exact duplicate rows", "dropped (keep first)", dropped)
    print(f"    Dropped {dropped:,} exact duplicates.  Remaining: {len(df):,}")

    # ---- Step 6: Drop logical duplicates (PropertyID, ReportingYear) ----
    print("\n[6] Dropping logical duplicates (PropertyID, ReportingYear) …")
    if "PropertyID" in df.columns and "ReportingYear" in df.columns:
        before = len(df)
        df.drop_duplicates(subset=["PropertyID", "ReportingYear"], keep="first", inplace=True)
        dropped = before - len(df)
        log_decision(
            "(PropertyID, ReportingYear)", "logical duplicate records",
            "dropped keeping first occurrence", dropped
        )
        print(f"    Dropped {dropped:,} logical duplicates.  Remaining: {len(df):,}")
    else:
        print("    WARNING: 'PropertyID' or 'ReportingYear' column not found — skipping logical dedup.")

    # ---- Step 7: Exclude rows with missing GrossFloorArea ----
    print("\n[7] Excluding rows with missing GrossFloorArea …")
    if "GrossFloorArea" in df.columns:
        before = len(df)
        df = df[df["GrossFloorArea"].notna() & (df["GrossFloorArea"] > 0)].copy()
        dropped = before - len(df)
        log_decision("GrossFloorArea", "null or zero GFA", "excluded rows", dropped,
                     notes="GFA is required for intensity calculations")
        print(f"    Excluded {dropped:,} rows missing GrossFloorArea.  Remaining: {len(df):,}")
    else:
        print("    WARNING: 'GrossFloorArea' not found.")

    # ---- Step 8: Exclude rows where BOTH SiteEUI and SourceEUI are NaN ----
    print("\n[8] Excluding rows where SiteEUI AND SourceEUI are both NaN …")
    if "SiteEUI" in df.columns and "SourceEUI" in df.columns:
        before = len(df)
        both_missing = df["SiteEUI"].isna() & df["SourceEUI"].isna()
        df = df[~both_missing].copy()
        dropped = before - len(df)
        log_decision(
            "(SiteEUI, SourceEUI)", "both energy measures missing",
            "excluded rows", dropped,
            notes="Cannot compute energy intensity without at least one EUI value"
        )
        print(f"    Excluded {dropped:,} rows missing both EUI fields.  Remaining: {len(df):,}")
    else:
        print("    WARNING: SiteEUI/SourceEUI columns not found — skipping step 8.")

    # ---- Step 9: Cap SiteEUI at 99th percentile ----
    print("\n[9] Capping SiteEUI at 99th percentile …")
    if "SiteEUI" in df.columns:
        p99 = df["SiteEUI"].quantile(0.99)
        capped = int((df["SiteEUI"] > p99).sum())
        df["SiteEUI"] = df["SiteEUI"].clip(upper=p99)
        log_decision("SiteEUI", f"values > 99th percentile ({p99:.2f})", f"capped at {p99:.2f}", capped)
        print(f"    99th percentile = {p99:.2f}.  Capped {capped:,} rows.")

    # ---- Step 10: Standardize Borough ----
    print("\n[10] Standardizing Borough values …")
    if "Borough" in df.columns:
        df["Borough"] = df["Borough"].astype(str).str.strip().str.upper()
        mapped = df["Borough"].map(BOROUGH_MAP)
        unmapped_mask = mapped.isna()
        # For already-correct title-case values not caught by upper() mapping
        # fall back to title case of the original
        df["Borough"] = mapped.where(~unmapped_mask, df["Borough"].str.title())
        mapped_count = int((~unmapped_mask).sum())
        log_decision("Borough", "code/non-standard values",
                     "mapped codes to full names; title-cased others", mapped_count)
        print(f"    Mapped/standardized {mapped_count:,} borough values.")
        print(f"    Unique boroughs: {sorted(df['Borough'].dropna().unique())}")

    # ---- Step 11: Derive BuildingSizeBand ----
    print("\n[11] Deriving BuildingSizeBand …")
    if "GrossFloorArea" in df.columns:
        def size_band(gfa):
            if pd.isna(gfa):
                return None
            if gfa < 50_000:
                return "Small"
            elif gfa <= 200_000:
                return "Medium"
            else:
                return "Large"
        df["BuildingSizeBand"] = df["GrossFloorArea"].apply(size_band)
        log_decision("BuildingSizeBand", "derived", "Small<50K, Medium 50K-200K, Large>200K",
                     df["BuildingSizeBand"].notna().sum())
        print(f"    Distribution: {df['BuildingSizeBand'].value_counts().to_dict()}")

    # ---- Step 12: Derive EnergyIntensityBand ----
    print("\n[12] Deriving EnergyIntensityBand …")
    if "SiteEUI" in df.columns:
        def eui_band(eui):
            if pd.isna(eui):
                return None
            if eui < 50:
                return "Low"
            elif eui < 100:
                return "Medium"
            elif eui < 200:
                return "High"
            else:
                return "VeryHigh"
        df["EnergyIntensityBand"] = df["SiteEUI"].apply(eui_band)
        log_decision("EnergyIntensityBand", "derived",
                     "Low<50, Medium 50-100, High 100-200, VeryHigh>200",
                     df["EnergyIntensityBand"].notna().sum())
        print(f"    Distribution: {df['EnergyIntensityBand'].value_counts().to_dict()}")

    # ---- Step 13: Derive GHGIntensity ----
    print("\n[13] Deriving GHGIntensity = GHGEmissions / GrossFloorArea …")
    if "GHGEmissions" in df.columns and "GrossFloorArea" in df.columns:
        df["GHGIntensity"] = df["GHGEmissions"] / df["GrossFloorArea"]
        valid = df["GHGIntensity"].notna().sum()
        log_decision("GHGIntensity", "derived",
                     "GHGEmissions / GrossFloorArea (tCO2e per sqft)", valid)
        print(f"    Non-null GHGIntensity values: {valid:,}")

    # ---- Step 14: Derive WaterIntensity ----
    print("\n[14] Deriving WaterIntensity = WaterUse / GrossFloorArea …")
    if "WaterUse" in df.columns and "GrossFloorArea" in df.columns:
        df["WaterIntensity"] = df["WaterUse"] / df["GrossFloorArea"]
        valid = df["WaterIntensity"].notna().sum()
        log_decision("WaterIntensity", "derived",
                     "WaterUse / GrossFloorArea (kgal per sqft)", valid)
        print(f"    Non-null WaterIntensity values: {valid:,}")

    # ---- Step 15: Derive EnergyPerformanceBand ----
    print("\n[15] Deriving EnergyPerformanceBand from EnergyStarScore …")
    if "EnergyStarScore" in df.columns:
        def perf_band(score):
            if pd.isna(score):
                return "Unknown"
            if score >= 75:
                return "Excellent"
            elif score >= 50:
                return "Good"
            elif score >= 25:
                return "Fair"
            else:
                return "Poor"
        df["EnergyPerformanceBand"] = df["EnergyStarScore"].apply(perf_band)
        log_decision("EnergyPerformanceBand", "derived",
                     "Excellent>=75, Good 50-74, Fair 25-49, Poor<25, Unknown=NaN",
                     df["EnergyPerformanceBand"].notna().sum())
        print(f"    Distribution: {df['EnergyPerformanceBand'].value_counts().to_dict()}")

    # ---- Step 16: Derive IsHighEnergyBuilding ----
    print("\n[16] Deriving IsHighEnergyBuilding (SiteEUI > 75th percentile) …")
    if "SiteEUI" in df.columns:
        threshold_eui = df["SiteEUI"].quantile(0.75)
        df["IsHighEnergyBuilding"] = (df["SiteEUI"] > threshold_eui).astype(int)
        high_count = df["IsHighEnergyBuilding"].sum()
        log_decision("IsHighEnergyBuilding", "derived",
                     f"1 if SiteEUI > {threshold_eui:.2f} (75th pct), else 0",
                     int(high_count),
                     notes=f"SiteEUI 75th-pct threshold = {threshold_eui:.2f}")
        print(f"    Threshold (75th pct): {threshold_eui:.2f} kBtu/ft².  "
              f"High-energy buildings: {high_count:,}")

    # ---- Step 17: Derive IsHighGHGBuilding ----
    print("\n[17] Deriving IsHighGHGBuilding (GHGIntensity > 75th percentile) …")
    if "GHGIntensity" in df.columns:
        threshold_ghg = df["GHGIntensity"].quantile(0.75)
        df["IsHighGHGBuilding"] = (df["GHGIntensity"] > threshold_ghg).astype(int)
        high_count = df["IsHighGHGBuilding"].sum()
        log_decision("IsHighGHGBuilding", "derived",
                     f"1 if GHGIntensity > {threshold_ghg:.6f} (75th pct), else 0",
                     int(high_count),
                     notes=f"GHGIntensity 75th-pct threshold = {threshold_ghg:.6f}")
        print(f"    Threshold (75th pct): {threshold_ghg:.6f}.  "
              f"High-GHG buildings: {high_count:,}")

    # ---- Step 18: Derive PropertyTypeGroup ----
    print("\n[18] Deriving PropertyTypeGroup from PrimaryPropertyType …")
    if "PrimaryPropertyType" in df.columns:
        df["PropertyTypeGroup"] = df["PrimaryPropertyType"].apply(map_property_type_group)
        log_decision("PropertyTypeGroup", "derived",
                     "mapped PrimaryPropertyType to: Office, Residential, Retail, "
                     "Industrial, Institutional, Other",
                     df["PropertyTypeGroup"].notna().sum())
        print(f"    Distribution: {df['PropertyTypeGroup'].value_counts().to_dict()}")

    # ---- Step 19: Derive BoroughGroup ----
    print("\n[19] Deriving BoroughGroup (same as Borough per spec) …")
    if "Borough" in df.columns:
        df["BoroughGroup"] = df["Borough"]
        log_decision("BoroughGroup", "derived", "copy of Borough column",
                     df["BoroughGroup"].notna().sum(),
                     notes="Required by spec; redundant alias of Borough")

    # ---- Step 20: Reconciliation ----
    print("\n[20] Reconciliation …")
    final_shape = df.shape
    print(f"    Initial rows:  {initial_shape[0]:,}")
    print(f"    Final rows:    {final_shape[0]:,}")
    print(f"    Rows removed:  {initial_shape[0] - final_shape[0]:,}")
    print(f"    Final columns: {final_shape[1]}")
    for col in ["GHGEmissions", "SiteEUI", "GrossFloorArea"]:
        if col in df.columns:
            total = df[col].sum()
            print(f"    Total {col}: {total:,.2f}")

    return df


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Clean and feature-engineer the NYC Building Energy dataset."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT,
                        help=f"Path to raw CSV (default: {DEFAULT_INPUT})")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help=f"Path for curated CSV output (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        print("Run 00_download_dataset.py first.")
        sys.exit(1)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    os.makedirs(STAGING_DIR, exist_ok=True)

    # Run pipeline
    df = run_pipeline(args.input, args.output)

    # ---- Step 21: Save curated CSV ----
    print(f"\n[21] Saving curated CSV → {args.output}")
    df.to_csv(args.output, index=False)
    print(f"     Saved {len(df):,} rows × {len(df.columns)} columns")
    log_decision("ALL", "curation complete", f"saved to {args.output}",
                 f"{len(df)} rows × {len(df.columns)} cols")

    # ---- Step 22: Save cleaning log ----
    print(f"\n[22] Saving cleaning log → {CLEANING_LOG_PATH}")
    with open(CLEANING_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(CLEANING_LOG, f, indent=2, default=str)
    print(f"     {len(CLEANING_LOG)} decisions logged.")

    print("\n✓ Data curation complete.")


if __name__ == "__main__":
    main()
