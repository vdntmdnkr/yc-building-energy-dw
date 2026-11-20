"""
01_data_profiling.py
====================
Standalone data-profiling script for the NYC Building Energy dataset.

For every column it reports:
  - dtype, null count, null %, unique count, sample values
  - Numeric: min, max, mean, median, std, zeros, negatives, outliers (> 3 × IQR)
  - String:  empty-string count, length stats, top 5 values

Also checks:
  - Exact duplicates
  - Logical duplicates on (PropertyID, ReportingYear)

Output:
  - Printed summary to stdout
  - ../data/staging/profiling_report.json

Usage:
    python 01_data_profiling.py [--input PATH_TO_CSV]

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
STAGING_DIR = os.path.join(PROJECT_ROOT, "data", "staging")
OUTPUT_JSON = os.path.join(STAGING_DIR, "profiling_report.json")


# ---------------------------------------------------------------------------
# Profiling helpers
# ---------------------------------------------------------------------------

def iqr_outliers(series: pd.Series) -> int:
    """Return count of values beyond 3 × IQR from Q1/Q3."""
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 3 * iqr
    upper = q3 + 3 * iqr
    return int(((series < lower) | (series > upper)).sum())


def profile_numeric(series: pd.Series) -> dict:
    s = series.dropna()
    if s.empty:
        return {}
    return {
        "min": float(s.min()),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "std": float(s.std()),
        "zeros": int((s == 0).sum()),
        "negatives": int((s < 0).sum()),
        "outliers_3iqr": iqr_outliers(s),
        "p25": float(s.quantile(0.25)),
        "p75": float(s.quantile(0.75)),
        "p99": float(s.quantile(0.99)),
    }


def profile_string(series: pd.Series) -> dict:
    s = series.dropna().astype(str)
    lengths = s.str.len()
    top_values = series.value_counts(dropna=False).head(5)
    return {
        "empty_string_count": int((s == "").sum()),
        "length_min": int(lengths.min()) if not lengths.empty else None,
        "length_max": int(lengths.max()) if not lengths.empty else None,
        "length_mean": float(lengths.mean()) if not lengths.empty else None,
        "top_values": {str(k): int(v) for k, v in top_values.items()},
    }


def profile_column(col: str, series: pd.Series) -> dict:
    total = len(series)
    null_count = int(series.isna().sum())

    # Sample non-null values (up to 5)
    sample_vals = series.dropna().head(5).tolist()
    # Make JSON-serialisable
    sample_vals = [
        v.item() if hasattr(v, "item") else v for v in sample_vals
    ]

    result: dict = {
        "column": col,
        "dtype": str(series.dtype),
        "total_count": total,
        "null_count": null_count,
        "null_pct": round(null_count / total * 100, 2) if total else 0,
        "unique_count": int(series.nunique(dropna=True)),
        "sample_values": sample_vals,
    }

    # Numeric profiling
    if pd.api.types.is_numeric_dtype(series):
        result["numeric"] = profile_numeric(series)

    # String / object profiling
    elif series.dtype == object or pd.api.types.is_string_dtype(series):
        result["string"] = profile_string(series)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Profile the NYC Building Energy raw CSV dataset."
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help=f"Path to raw CSV (default: {DEFAULT_INPUT})",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        print("Run 00_download_dataset.py first to download the data.")
        sys.exit(1)

    os.makedirs(STAGING_DIR, exist_ok=True)

    print(f"Loading dataset: {args.input} …")
    df = pd.read_csv(args.input, low_memory=False)
    print(f"Loaded {len(df):,} rows × {len(df.columns)} columns\n")

    # ------------------------------------------------------------------
    # 1. Per-column profiling
    # ------------------------------------------------------------------
    print("=" * 70)
    print("COLUMN PROFILES")
    print("=" * 70)

    column_profiles = []
    for col in df.columns:
        profile = profile_column(col, df[col])
        column_profiles.append(profile)

        # Print summary line
        null_info = f"nulls={profile['null_count']:,} ({profile['null_pct']}%)"
        uniq_info = f"unique={profile['unique_count']:,}"
        print(f"  {col:<55} dtype={profile['dtype']:<12} {null_info:<30} {uniq_info}")
        if "numeric" in profile and profile["numeric"]:
            n = profile["numeric"]
            print(
                f"    → min={n['min']:.3g}  max={n['max']:.3g}  "
                f"mean={n['mean']:.3g}  median={n['median']:.3g}  "
                f"std={n['std']:.3g}  zeros={n['zeros']}  "
                f"neg={n['negatives']}  outliers(3IQR)={n['outliers_3iqr']}"
            )
        if "string" in profile:
            s = profile["string"]
            print(
                f"    → empty_str={s['empty_string_count']}  "
                f"len_min={s['length_min']}  len_max={s['length_max']}  "
                f"top: {list(s['top_values'].keys())[:3]}"
            )

    # ------------------------------------------------------------------
    # 2. Duplicate analysis
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("DUPLICATE ANALYSIS")
    print("=" * 70)

    exact_dupes = int(df.duplicated().sum())
    print(f"  Exact duplicates:    {exact_dupes:,}")

    # Logical duplicates on (PropertyID, ReportingYear)
    id_col = next(
        (c for c in df.columns if c.lower().replace(" ", "_") in
         ("property_id", "propertyid", "bbl_10_digits_", "bbl")),
        None,
    )
    year_col = next(
        (c for c in df.columns if "year" in c.lower()),
        None,
    )
    logical_dupes = None
    if id_col and year_col:
        logical_dupes = int(df.duplicated(subset=[id_col, year_col]).sum())
        print(f"  Logical duplicates ({id_col}, {year_col}): {logical_dupes:,}")
    else:
        print(f"  Logical duplicates: columns 'PropertyID' and/or 'ReportingYear' not found by name.")

    # ------------------------------------------------------------------
    # 3. Overall quality score (simple heuristic)
    # ------------------------------------------------------------------
    total_cells = df.size
    missing_cells = int(df.isna().sum().sum())
    completeness_pct = round((1 - missing_cells / total_cells) * 100, 2) if total_cells else 0

    print("\n" + "=" * 70)
    print("OVERALL DATA QUALITY")
    print("=" * 70)
    print(f"  Shape:               {df.shape}")
    print(f"  Total cells:         {total_cells:,}")
    print(f"  Missing cells:       {missing_cells:,}")
    print(f"  Completeness:        {completeness_pct}%")
    print(f"  Exact duplicates:    {exact_dupes:,}")
    if logical_dupes is not None:
        print(f"  Logical duplicates:  {logical_dupes:,}")

    # ------------------------------------------------------------------
    # 4. Save JSON report
    # ------------------------------------------------------------------
    report = {
        "profiling_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_file": args.input,
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "overall": {
            "total_cells": total_cells,
            "missing_cells": missing_cells,
            "completeness_pct": completeness_pct,
            "exact_duplicates": exact_dupes,
            "logical_duplicates": logical_dupes,
            "id_column_used": id_col,
            "year_column_used": year_col,
        },
        "columns": column_profiles,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nProfiling report saved → {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
