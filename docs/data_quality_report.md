# Data Quality Report
## NYC Building Energy Benchmarking (Local Law 84) — Data Warehouse Project

> [!IMPORTANT]
> This report documents all data quality issues identified during profiling (`A1_data_profiling.ipynb`), the cleaning decisions applied during curation (`A2_data_curation.ipynb`), and the reconciliation of row counts from raw ingestion through to the dimensional warehouse. Placeholder values (marked `[FILL]`) must be replaced after executing the notebooks on the actual dataset.

---

## 1. Executive Summary

The NYC Local Law 84 (LL84) Energy Benchmarking dataset was downloaded from NYC Open Data and profiled across approximately `[FILL: row count]` raw records spanning reporting years 2022–2024. Data quality issues were found in several key fields — most notably missing values in energy intensity metrics and GHG emissions, a small proportion of exact and logical duplicates, and a tail of extreme SiteEUI outliers. All cleaning decisions follow a **conservative exclusion strategy**: records are excluded only when a critical measurement field (GrossFloorArea or SiteEUI) is missing; optional fields (EnergyStarScore, WaterUse) are retained with NULL values. After curation, `[FILL: post-curation count]` records remain and are loaded into the dimensional warehouse.

---

## 2. Dataset Overview

| Item | Value |
|---|---|
| **Source** | NYC Open Data — Energy and Water Data Disclosure for Local Law 84 (dataset `5zyy-y8am`) |
| **Download Date** | `[FILL: YYYY-MM-DD]` |
| **Raw Row Count** | `[FILL]` rows |
| **Reporting Years Present** | `[FILL]` (expected: 2022, 2023, 2024) |
| **Columns in Raw Dataset** | `[FILL]` |
| **File Size (CSV)** | `[FILL] MB` |
| **Primary Key Used** | `property_id` × `reporting_year` |

---

## 3. Quality Assessment Table

| Quality Problem | Affected Field(s) | Count | % of Total | Treatment | Justification |
|---|---|---|---|---|---|
| **Missing GrossFloorArea** | `GrossFloorArea` | `[FILL]` | `[FILL]%` | **Exclude row** | GFA is the denominator for all intensity metrics (EUI, GHG intensity, water intensity). A record without GFA cannot produce normalized measures and must be excluded. |
| **Missing SiteEUI and/or SourceEUI** | `SiteEUI`, `SourceEUI` | `[FILL]` | `[FILL]%` | **Exclude row if > 50% of energy fields are missing** | SiteEUI is the primary energy performance metric and the ML target. Records with both SiteEUI and SourceEUI missing provide no energy information. Rows missing only SourceEUI are retained with NULL. |
| **Exact Duplicate Records** | All fields | `[FILL]` | `[FILL]%` | **Drop all but first occurrence** | Exact duplicates (all column values identical) are data entry artifacts. First occurrence kept; duplicates dropped. Count logged to `cleaning_log.json`. |
| **Logical Duplicate Records** | `PropertyID`, `ReportingYear` | `[FILL]` | `[FILL]%` | **Keep record with more complete energy fields; drop other(s)** | Same (PropertyID, ReportingYear) pair with differing values (amended submissions). The more complete record (fewer NULLs in energy columns) is retained. Tie-broken by keeping the last-uploaded row. |
| **Invalid Numeric Values** (zero or negative) | `GrossFloorArea`, `SiteEUI`, `GHGEmissions` | `[FILL]` | `[FILL]%` | **Treat as missing; apply same exclusion logic as above** | GFA ≤ 0 is physically impossible. SiteEUI ≤ 0 is implausible (all buildings consume some energy). GHGEmissions < 0 is invalid. These are treated identically to missing values. |
| **Extreme SiteEUI Outliers** (> 99th percentile) | `SiteEUI` | `[FILL]` | `[FILL]%` | **Cap at 99th percentile value** | Extreme SiteEUI values (e.g., > 1,000 kBtu/sq ft) are likely data entry errors or unusually specialized facilities. Capping (Winsorizing) at the 99th percentile preserves the record and reduces distortion in regression models and EUI band classification. The cap threshold is logged to `cleaning_log.json`. |
| **Invalid Borough Codes** | `Borough` | `[FILL]` | `[FILL]%` | **Map to standard borough name; NULL if unmappable** | Raw data may contain numeric codes (1–5), abbreviations, or inconsistent strings. Standard mapping applied: 1→Manhattan, 2→Bronx, 3→Brooklyn, 4→Queens, 5→Staten Island. Unmappable values set to NULL and flagged. |
| **Missing EnergyStarScore** | `EnergyStarScore` | `[FILL]` | `[FILL]%` | **Retain as NULL (optional field)** | EnergyStarScore is only published for ENERGY STAR-eligible property types. Missing score for an ineligible property type is expected and not an error. The `EnergyPerformanceBand` is set to `Unknown` for NULL scores. |

---

## 4. Pre-Curation vs Post-Curation Row Counts

| Stage | Row Count | Notes |
|---|---|---|
| Raw CSV loaded | `[FILL]` | Total rows as downloaded from NYC Open Data |
| After ReportingYear filter (≥ 2022) | `[FILL]` | Excludes pre-2022 records |
| After exact duplicate removal | `[FILL]` | Exact duplicates dropped |
| After logical duplicate resolution | `[FILL]` | Same (PropertyID, Year) conflicts resolved |
| After missing GFA exclusion | `[FILL]` | Rows with NULL or zero GFA excluded |
| After missing SiteEUI exclusion | `[FILL]` | Rows where > 50% of energy fields are NULL excluded |
| After invalid numeric value exclusion | `[FILL]` | Zero/negative GFA, SiteEUI, GHGEmissions removed |
| After SiteEUI outlier capping | `[FILL]` | No rows dropped; outlier values capped in-place |
| After Borough standardization | `[FILL]` | No rows dropped; NULL set for unmappable codes |
| **Final curated dataset** | **`[FILL]`** | Written to `data/curated/nyc_building_energy_curated.csv` |
| Loaded into FactBuildingBenchmark | `[FILL]` | Should match final curated count ± 0 |
| **Reconciliation delta** | **`[FILL]`** | Must be 0; investigate if non-zero |

---

## 5. Per-Attribute Quality Notes

| Field | Completeness % | Issues Found | Treatment Applied |
|---|---|---|---|
| `PropertyID` | `[FILL]%` | Occasional NULL (orphan submissions) | Rows with NULL PropertyID excluded — cannot be keyed in DW |
| `PropertyName` | `[FILL]%` | Frequent NULLs / blank strings | Retained as NULL — not a key field |
| `Borough` | `[FILL]%` | Numeric codes, abbreviations, inconsistent casing | Standardized to full borough name; NULL if unmappable |
| `BBL` | `[FILL]%` | Some invalid lengths (< 10 digits) | Retained as-is; not used for joining — cosmetic only |
| `BIN` | `[FILL]%` | Some missing, some with extra digits | Retained as-is; not used as DW key |
| `PrimaryPropertyType` | `[FILL]%` | Dozens of ENERGY STAR strings; minor typos | Grouped into PropertyTypeGroup via lookup table; typos normalized |
| `GrossFloorArea` | `[FILL]%` | Missing, zero, negative | Missing/zero/negative → exclusion |
| `SiteEUI` | `[FILL]%` | Missing; extreme high values (> 99th pct) | Missing: exclusion; extreme: capped at 99th pct |
| `SourceEUI` | `[FILL]%` | Missing (less critical than SiteEUI) | NULL retained if SiteEUI present; exclusion only if both missing |
| `GHGEmissions` | `[FILL]%` | Missing; occasional negatives | Negatives treated as invalid → NULL; NULLs retained |
| `WaterUse` | `[FILL]%` | High proportion missing (expected) | Retained as NULL — optional field |
| `EnergyStarScore` | `[FILL]%` | Missing for ineligible types (expected) | Retained as NULL; EnergyPerformanceBand = Unknown |
| `ReportingYear` | `[FILL]%` | Pre-2022 records present | Filter: exclude ReportingYear < 2022 |

---

## 6. Cleaning Decisions Log

All cleaning decisions — including exact threshold values, counts of affected rows, percentile cut-off values, and borough code mappings — are programmatically logged to:

```
data/staging/cleaning_log.json
```

This file is generated by `notebooks/A2_data_curation.ipynb` at run time. It contains:

- **Decision ID:** Unique identifier for each cleaning rule
- **Field:** Column(s) affected
- **Rule:** Description of the cleaning logic applied
- **Rows Affected:** Count of records modified or dropped
- **Threshold Value:** Computed value (e.g., 99th percentile SiteEUI, 75th percentile for binary flags)
- **Timestamp:** When the cleaning was applied

> [!TIP]
> Reference `cleaning_log.json` to verify that `IsHighEnergyBuilding` and `IsHighGHGBuilding` thresholds are consistent when re-running notebooks on updated datasets.

---

## 7. Reconciliation: Staging → Fact Table

The row count is reconciled at two checkpoints to ensure no silent data loss:

| Checkpoint | Expected | Actual | Status |
|---|---|---|---|
| Curated CSV → Staging table load | `[FILL]` | `[FILL]` | `[FILL: PASS / FAIL]` |
| Staging table → FactBuildingBenchmark load | `[FILL]` | `[FILL]` | `[FILL: PASS / FAIL]` |
| FactBuildingBenchmark → BuildingPerformanceAnalyticsMart | `[FILL]` | `[FILL]` | `[FILL: PASS / FAIL]` |

Reconciliation is validated in `A2_data_curation.ipynb` by comparing `len(df_raw)`, `len(df_curated)`, and the result of `SELECT COUNT(*) FROM fact_building_benchmark`.

---

## 8. Limitations and Assumptions

1. **Self-reported data:** All energy, water, and property-type fields are self-reported by building owners. Errors, omissions, or strategic reporting cannot be fully corrected by automated cleaning.

2. **No weather normalization:** Site EUI and Source EUI are not weather-normalized in this analysis. Year-to-year comparisons may reflect climate variation rather than efficiency changes.

3. **Outlier capping vs. exclusion:** The decision to cap SiteEUI at the 99th percentile (rather than excluding extreme records) preserves sample size but may understate true consumption for genuinely high-intensity facilities (e.g., data centers, hospitals).

4. **75th percentile thresholds for binary flags:** `IsHighEnergyBuilding` and `IsHighGHGBuilding` flags are computed on the post-curation training population. If the dataset is refreshed with new reporting years, these thresholds must be recomputed and the flags regenerated.

5. **EnergyStarScore availability:** ENERGY STAR scores are not available for all property types. Analyses using EnergyStarScore or EnergyPerformanceBand are therefore restricted to a subset of the population; results may not generalize to ineligible property types.

6. **ReportingYear filter:** Records before 2022 are excluded per project specification. This excludes the COVID-era years (2020–2021) which showed anomalously low energy use; the filtered dataset may not fully capture the post-pandemic recovery trend.

7. **Multi-building campuses:** Properties with multiple BINs are reported as a single LL84 submission. GFA and emissions are totals across all buildings on the property; per-building analysis is not possible from this dataset alone.

---

*Last updated: November 2026 | Project: TY B.Tech Data Warehouse — NYC Building Energy (LL84)*
