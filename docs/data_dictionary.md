# Data Dictionary
## NYC Building Energy Benchmarking (Local Law 84) — Data Warehouse Project

> [!NOTE]
> This dictionary covers all fields used in the data warehouse: original source columns from the NYC LL84 dataset, derived/computed attributes from the curation pipeline, and schema definitions for all fact tables, dimension tables, and the analytical mart.

---

## 1. Original Source Fields

These fields are ingested directly from the NYC Local Law 84 (LL84) Energy Benchmarking public dataset as downloaded from NYC Open Data (`5zyy-y8am`). No transformation is applied at this stage; they appear exactly as published.

| Field Name | Source Column Name | Data Type | Description | Valid Range / Values | Notes |
|---|---|---|---|---|---|
| PropertyID | `property_id` | VARCHAR | Unique property benchmark identifier assigned by NYC. Used as the primary business key for a building across reporting years. | Positive integers (stored as string) | NYC Department of Buildings (DOB) identifier. Should be stable across years for the same property. |
| PropertyName | `property_name` | VARCHAR | Building or property name as self-reported by the owner during benchmarking submission. | Free text (any printable string) | May be blank or NULL. Not used for joining — use PropertyID. |
| Borough | `borough` | VARCHAR | NYC borough in which the property is located. | `Manhattan`, `Brooklyn`, `Queens`, `Bronx`, `Staten Island` | Raw data may contain numeric codes (1–5) or abbreviations. Standardized to full borough names during curation. |
| BBL | `bbl_10_digits_` | VARCHAR | Borough-Block-Lot identifier — a 10-digit composite geographic identifier used by NYC Finance. | 10-digit numeric string (e.g., `1000477501`) | Useful for spatial joins with MapPLUTO or other NYC geographic datasets. Not used as a DW key. |
| BIN | `bin` | VARCHAR | Building Identification Number issued by NYC Department of Buildings. | 7-digit numeric string | Identifies a specific structure; one property may have multiple BINs (multi-building campuses). |
| PrimaryPropertyType | `primary_property_type_self_selected` | VARCHAR | The main use type of the property as self-reported by the owner using ENERGY STAR Portfolio Manager categories. | ENERGY STAR property type list (e.g., `Office`, `Multifamily Housing`, `K-12 School`, `Hotel`, `Retail Store`) | Self-reported — may contain inconsistencies. Grouped into broader categories via `PropertyTypeGroup` during curation. |
| GrossFloorArea | `gross_floor_area_buildings_sq_ft` | NUMERIC | Total enclosed floor area of the building(s) on the property, in square feet. | > 0 | Excludes parking areas. Required field: rows with missing or zero GFA are excluded during curation. |
| SiteEUI | `site_eui_kbtu_ft²` | NUMERIC | Site Energy Use Intensity — total energy consumed at the property boundary per square foot per year, measured in kBtu/sq ft/year. | Typically 1–1,000 kBtu/sq ft/yr | ENERGY STAR primary efficiency metric. Extreme values (> 99th percentile) are capped during curation. |
| SourceEUI | `source_eui_kbtu_ft²` | NUMERIC | Source Energy Use Intensity — total primary energy required to deliver energy to the site (includes upstream generation and transmission losses), per sq ft/year. | Typically 1–2,000 kBtu/sq ft/yr | Higher than SiteEUI because it accounts for utility-side losses. Used in regression analysis. |
| GHGEmissions | `total_ghg_emissions_metric_tons_co2e` | NUMERIC | Total greenhouse gas emissions (Scope 1 direct + Scope 2 indirect) from the property's energy use in metric tons of CO₂-equivalent per year. | ≥ 0 | Includes both on-site combustion (Scope 1) and purchased electricity/steam (Scope 2). Zero is valid for all-electric buildings with renewable supply. |
| WaterUse | `water_use_kgal` | NUMERIC | Total annual water consumption for the property, measured in kilo-gallons (thousands of gallons). | ≥ 0 | May be absent (NULL) for properties that did not report water data. Retained as optional field. |
| EnergyStarScore | `energy_star_score` | NUMERIC | ENERGY STAR score from 1 (worst) to 100 (best), benchmarking energy efficiency relative to similar buildings nationally. | 1–100 (integer), or NULL | Available only for ENERGY STAR-eligible property types. NULL is valid and retained; not an error. |
| ReportingYear | `reporting_year` | INT | Calendar year for which the building's energy data is being reported/disclosed. | 2022, 2023, 2024 | Required filter: rows with ReportingYear < 2022 are excluded. Used for temporal analysis and trend tracking. |

---

## 2. Derived Attributes

These attributes are **computed by the curation pipeline** (`A2_data_curation.ipynb`). They do **not** appear in the original source dataset and are added to `nyc_building_energy_curated.csv` and all downstream tables.

| Field Name | Formula / Derivation | Thresholds / Mapping | Justification | Source Fields Used |
|---|---|---|---|---|
| BuildingSizeBand | Categorize `GrossFloorArea` into three ordinal bands | `Small`: < 50,000 sq ft; `Medium`: 50,000–200,000 sq ft; `Large`: > 200,000 sq ft | Aligns with ENERGY STAR building size classification used in national benchmarking analysis. Enables group-level policy targeting. | GrossFloorArea |
| EnergyIntensityBand | Categorize `SiteEUI` into four ordinal bands | `Low`: < 50 kBtu/sq ft; `Medium`: 50–100; `High`: 100–200; `Very High`: > 200 kBtu/sq ft | Thresholds derived from NYC Local Law 97 (LL97) carbon penalty benchmarks, which are linked to energy intensity levels. | SiteEUI |
| GHGIntensity | `GHGEmissions / GrossFloorArea` | Expressed in tCO₂e per sq ft/year | Normalizes GHG emissions by building size to allow fair cross-building comparison regardless of building scale. | GHGEmissions, GrossFloorArea |
| WaterIntensity | `WaterUse / GrossFloorArea` | Expressed in kgal per sq ft/year | Normalizes water consumption by building size. NULL when WaterUse is NULL. | WaterUse, GrossFloorArea |
| EnergyPerformanceBand | Categorize `EnergyStarScore` into four qualitative bands | `Excellent`: ≥ 75; `Good`: 50–74; `Fair`: 25–49; `Poor`: < 25; `Unknown`: NULL score | Mirrors ENERGY STAR certification threshold (≥ 75 = eligible for label). Provides intuitive performance classification for stakeholder communication. | EnergyStarScore |
| IsHighEnergyBuilding | Binary flag: `1` if `SiteEUI` > 75th percentile of training population, else `0` | Threshold value documented in `data/staging/cleaning_log.json` at curation time | Binary classification target for supervised learning (regression, clustering). Identifies buildings in the top quartile of energy intensity. | SiteEUI |
| IsHighGHGBuilding | Binary flag: `1` if `GHGIntensity` > 75th percentile of training population, else `0` | Threshold value documented in `data/staging/cleaning_log.json` at curation time | Binary flag identifying high-emission properties for GHG reduction targeting. Distinct from IsHighEnergyBuilding (uses intensity, not raw EUI). | GHGIntensity |
| PropertyTypeGroup | Map `PrimaryPropertyType` to a broad use group | `Office`; `Residential`; `Retail`; `Industrial`; `Institutional`; `Other` | Aggregates the many ENERGY STAR property type strings into policy-meaningful categories for visualization, cross-tabulation, and association mining. | PrimaryPropertyType |
| BoroughGroup | Same value as `Borough` (after standardization) | `Manhattan`, `Brooklyn`, `Queens`, `Bronx`, `Staten Island` | Required by project specification for group-level analysis. Functionally redundant with Borough but maintained as a separate attribute for mart schema consistency. | Borough |

> [!NOTE]
> Percentile thresholds for `IsHighEnergyBuilding` and `IsHighGHGBuilding` are computed on the **post-curation training population** (all records after cleaning) and logged to `data/staging/cleaning_log.json` by `A2_data_curation.ipynb`. These values must be recomputed if the dataset changes.

---

## 3. Fact Tables Schema

### 3.1 FactBuildingBenchmark

**Grain:** One row per (PropertyID × ReportingYear). This is the core transactional fact table recording each building's annual benchmarking submission.

| Column | Data Type | Description | FK Reference |
|---|---|---|---|
| benchmark_sk | SERIAL (PK) | Surrogate key | — |
| property_sk | INT | Foreign key to DimProperty | DimProperty.property_sk |
| location_sk | INT | Foreign key to DimLocation | DimLocation.location_sk |
| property_type_sk | INT | Foreign key to DimPropertyType | DimPropertyType.property_type_sk |
| date_sk | INT | Foreign key to DimDate | DimDate.date_sk |
| site_eui | NUMERIC(10,2) | Site EUI (kBtu/sq ft/yr) | — |
| source_eui | NUMERIC(10,2) | Source EUI (kBtu/sq ft/yr) | — |
| ghg_emissions | NUMERIC(12,4) | Total GHG (metric tons CO₂e) | — |
| ghg_intensity | NUMERIC(12,6) | GHG / GFA (tCO₂e/sq ft) | — |
| water_use_kgal | NUMERIC(12,2) | Water use (kgal) — nullable | — |
| water_intensity | NUMERIC(12,6) | Water / GFA — nullable | — |
| energy_star_score | NUMERIC(5,1) | ENERGY STAR score — nullable | — |
| gross_floor_area | NUMERIC(12,2) | GFA (sq ft) | — |
| is_high_energy_building | SMALLINT | Binary flag (0/1) | — |
| is_high_ghg_building | SMALLINT | Binary flag (0/1) | — |

**Indexes:** `(property_sk, date_sk)`, `(location_sk)`, `(property_type_sk)`

---

### 3.2 FactBoroughPropertyTypeAnnualPerformance

**Grain:** One row per (Borough × PropertyTypeGroup × ReportingYear). Pre-aggregated summary fact table supporting borough/type-level dashboards and cross-tabulation queries.

| Column | Data Type | Description | FK Reference |
|---|---|---|---|
| agg_sk | SERIAL (PK) | Surrogate key | — |
| location_sk | INT | FK to DimLocation (borough level) | DimLocation.location_sk |
| property_type_sk | INT | FK to DimPropertyType | DimPropertyType.property_type_sk |
| date_sk | INT | FK to DimDate | DimDate.date_sk |
| building_count | INT | Number of buildings in group | — |
| avg_site_eui | NUMERIC(10,2) | Mean SiteEUI for group | — |
| median_site_eui | NUMERIC(10,2) | Median SiteEUI for group | — |
| avg_ghg_intensity | NUMERIC(12,6) | Mean GHGIntensity for group | — |
| total_ghg_emissions | NUMERIC(14,4) | Sum of GHG for group (tCO₂e) | — |
| avg_energy_star_score | NUMERIC(5,1) | Mean ENERGY STAR score (nullable) | — |
| pct_high_energy | NUMERIC(5,2) | % buildings with IsHighEnergyBuilding=1 | — |
| pct_high_ghg | NUMERIC(5,2) | % buildings with IsHighGHGBuilding=1 | — |

---

## 4. Dimension Tables Schema

### 4.1 DimProperty

**Role:** Slowly Changing Dimension (Type 1 — overwrite). Describes each unique property.

| Column | Data Type | Description |
|---|---|---|
| property_sk | SERIAL (PK) | Surrogate key |
| property_id | VARCHAR(20) | Natural key (PropertyID from source) |
| property_name | VARCHAR(500) | Building name (may be NULL) |
| bbl | VARCHAR(10) | Borough-Block-Lot (10 digits) |
| bin | VARCHAR(7) | Building Identification Number |
| gross_floor_area | NUMERIC(12,2) | Most recent GFA |
| building_size_band | VARCHAR(10) | Small / Medium / Large |

---

### 4.2 DimLocation

**Role:** Geographic dimension at borough level. Supports geographic analysis and borough-level roll-ups.

| Column | Data Type | Description |
|---|---|---|
| location_sk | SERIAL (PK) | Surrogate key |
| borough | VARCHAR(50) | Borough name (standardized) |
| borough_group | VARCHAR(50) | Same as borough (spec requirement) |
| borough_code | CHAR(1) | Numeric code (1=Manhattan … 5=Staten Island) |

---

### 4.3 DimPropertyType

**Role:** Property use-type dimension. Supports property-type-level analysis and grouping.

| Column | Data Type | Description |
|---|---|---|
| property_type_sk | SERIAL (PK) | Surrogate key |
| primary_property_type | VARCHAR(200) | ENERGY STAR type string (source value) |
| property_type_group | VARCHAR(50) | Broad group (Office/Residential/Retail/Industrial/Institutional/Other) |
| is_energy_star_eligible | BOOLEAN | Whether ENERGY STAR score is published for this type |

---

### 4.4 DimDate

**Role:** Date/time dimension. Supports temporal analysis and year-over-year trend queries.

| Column | Data Type | Description |
|---|---|---|
| date_sk | INT (PK) | Surrogate key (YYYYMMDD integer) |
| reporting_year | INT | Calendar year (2022, 2023, 2024) |
| year_label | VARCHAR(10) | Display label (e.g., "FY 2023") |
| is_latest_year | BOOLEAN | TRUE for the most recent reporting year in the dataset |

---

### 4.5 DimEnergyPerformanceBand

**Role:** Conformed performance classification dimension. Used for ENERGY STAR score band lookups.

| Column | Data Type | Description |
|---|---|---|
| performance_band_sk | SERIAL (PK) | Surrogate key |
| performance_band | VARCHAR(20) | Label: Excellent / Good / Fair / Poor / Unknown |
| score_min | NUMERIC(5,1) | Lower bound of ENERGY STAR score for this band |
| score_max | NUMERIC(5,1) | Upper bound of ENERGY STAR score for this band |
| sort_order | INT | Display order (1=Excellent … 5=Unknown) |

---

## 5. Analytical Mart Schema

### BuildingPerformanceAnalyticsMart

**Location:** `data/mart/building_performance_mart.csv` (also loaded as a PostgreSQL view/table)

**Grain:** One row per (PropertyID × ReportingYear). Denormalized wide table joining all fact and dimension data for ML, EDA, and reporting use.

| Column | Data Type | Derivation Source |
|---|---|---|
| benchmark_sk | INT | FactBuildingBenchmark PK |
| property_id | VARCHAR | DimProperty (source natural key) |
| property_name | VARCHAR | DimProperty |
| borough | VARCHAR | DimLocation |
| borough_group | VARCHAR | DimLocation (= borough) |
| bbl | VARCHAR | DimProperty |
| bin | VARCHAR | DimProperty |
| primary_property_type | VARCHAR | DimPropertyType |
| property_type_group | VARCHAR | DimPropertyType |
| reporting_year | INT | DimDate |
| gross_floor_area | NUMERIC | FactBuildingBenchmark |
| building_size_band | VARCHAR | DimProperty (derived from GFA) |
| site_eui | NUMERIC | FactBuildingBenchmark |
| source_eui | NUMERIC | FactBuildingBenchmark |
| energy_intensity_band | VARCHAR | Derived: categorize site_eui |
| ghg_emissions | NUMERIC | FactBuildingBenchmark |
| ghg_intensity | NUMERIC | FactBuildingBenchmark |
| water_use_kgal | NUMERIC | FactBuildingBenchmark (nullable) |
| water_intensity | NUMERIC | FactBuildingBenchmark (nullable) |
| energy_star_score | NUMERIC | FactBuildingBenchmark (nullable) |
| energy_performance_band | VARCHAR | Derived: categorize energy_star_score |
| is_high_energy_building | SMALLINT | FactBuildingBenchmark |
| is_high_ghg_building | SMALLINT | FactBuildingBenchmark |

---

## 6. External Enrichment Sources

**None.** All derived attributes are computed exclusively from the NYC Local Law 84 source dataset fields alone. No external datasets (e.g., weather normalization, census data, property tax records) are joined in this version of the data warehouse. Future versions may incorporate NYC MapPLUTO for parcel geometry or NOAA climate data for weather normalization.

---

*Last updated: November 2026 | Project: TY B.Tech Data Warehouse — NYC Building Energy (LL84)*
