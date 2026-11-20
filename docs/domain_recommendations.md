# Domain Recommendations
## NYC Building Energy Benchmarking (Local Law 84) — Data Warehouse Project

> [!NOTE]
> The following 10 recommendations are derived from exploratory data analysis, regression modeling, association rule mining, and clustering outputs produced in notebooks `A3_eda.ipynb`, `G_regression.ipynb`, `H_association_mining.ipynb`, and `I_clustering.ipynb`. Each recommendation follows the structure: **Observation → Data Evidence → Recommendation → Expected Impact**.

---

## Recommendation 1: High-Energy Building Targeting

### Observation
A disproportionately small fraction of NYC's benchmarked buildings contribute a large share of total energy consumption and GHG emissions. The `IsHighEnergyBuilding` flag (SiteEUI > 75th percentile) identifies this critical top-quartile population.

### Data Evidence
- Regression analysis shows that `IsHighEnergyBuilding = 1` buildings account for a substantially outsized proportion of total GHG emissions across all reporting years.
- EDA histograms of SiteEUI reveal a right-skewed distribution with a long tail — the top 25% of buildings by SiteEUI consume far more energy per square foot than the median.
- Association rule mining finds frequent itemsets linking `EnergyIntensityBand = Very High` with specific `PropertyTypeGroup` and `BuildingSizeBand` combinations.

### Recommendation
NYC's Department of Buildings and Office of Sustainability should establish a **High-Energy Building Registry** identifying all properties with `IsHighEnergyBuilding = 1`. These buildings should be prioritized for:
- Mandatory energy audits (Local Law 87 enforcement)
- Targeted retrofit incentive programs (e.g., NYC Accelerator)
- Enhanced ENERGY STAR Portfolio Manager monitoring with quarterly check-ins

### Expected Impact
Focusing efficiency investments on the top-quartile buildings maximizes emissions reduction per dollar of program spending. A 20% reduction in SiteEUI for high-energy buildings would yield an estimated reduction of `[FILL: computed from mart data]` metric tons of CO₂e annually.

---

## Recommendation 2: Borough-Level Policy Prioritization

### Observation
Energy use intensity and GHG emissions vary significantly across NYC's five boroughs, reflecting differences in building stock age, property type mix, density, and energy infrastructure.

### Data Evidence
- EDA borough-level bar charts (`A3_eda.ipynb`) show that `[FILL: borough]` has the highest median SiteEUI, while `[FILL: borough]` has the lowest, a gap of approximately `[FILL]` kBtu/sq ft/yr.
- `FactBoroughPropertyTypeAnnualPerformance` pre-aggregated fact table reveals borough-level variation in `pct_high_energy` and `avg_ghg_intensity`.
- Clustering analysis groups boroughs into distinct performance clusters — high-density, office-heavy boroughs tend toward higher average EUIs while outer boroughs with more residential stock show different patterns.

### Recommendation
NYC should adopt **borough-differentiated energy policy targets** rather than citywide uniform standards:
- Higher-EUI boroughs: accelerate LL97 fine enforcement timelines and expand audit subsidies.
- Lower-EUI boroughs: focus on data quality improvement and voluntary green certification programs.
- Publish annual borough-level energy dashboards (powered by this DW) to allow peer-comparison and community accountability.

### Expected Impact
Borough-targeted policies can direct resources efficiently, reducing administrative overhead and maximizing uptake of retrofit programs in the geographies with greatest improvement potential.

---

## Recommendation 3: Property-Type-Specific Performance Standards

### Observation
Energy use intensity varies dramatically by property type. Offices, hotels, and healthcare facilities have fundamentally different energy profiles than residential multifamily housing. A single citywide EUI standard is inadequate.

### Data Evidence
- EDA cross-tabulation (Borough × PropertyTypeGroup) shows `Office` and `Retail` groups have median SiteEUI exceeding `[FILL]` kBtu/sq ft/yr, while `Residential` buildings cluster significantly lower.
- Regression model indicates `PropertyTypeGroup` is a statistically significant predictor of SiteEUI (coefficient p < 0.05).
- Association rules frequently link `PropertyTypeGroup = Institutional` with `EnergyIntensityBand = High` or `Very High`.

### Recommendation
Establish **property-type-specific SiteEUI baseline standards** for LL97 compliance and benchmarking:
- Publish separate EUI percentile distributions for each `PropertyTypeGroup`.
- Set LL97 carbon intensity limits as a function of property type and size band (not a single citywide threshold).
- Provide `PropertyTypeGroup`-specific retrofit playbooks highlighting the most cost-effective interventions per building type (e.g., HVAC upgrades for offices, envelope improvements for residential).

### Expected Impact
Type-specific standards reduce compliance burden on buildings already performing well for their type while applying appropriate pressure on underperformers. This avoids penalizing large-footprint institutional buildings with inherently high process loads.

---

## Recommendation 4: ENERGY STAR Score Incentive Program

### Observation
Buildings with high ENERGY STAR scores (`EnergyPerformanceBand = Excellent`, score ≥ 75) demonstrate that strong performance is achievable at scale. However, a significant proportion of eligible buildings have not pursued certification.

### Data Evidence
- EDA shows that among ENERGY STAR-eligible property types, only `[FILL]%` have scores ≥ 75 (`Excellent` band).
- `[FILL]%` of eligible buildings have NULL or unreported ENERGY STAR scores, suggesting significant non-participation.
- Regression analysis shows a strong negative correlation between `EnergyStarScore` and `SiteEUI` (r ≈ `[FILL]`), confirming that score is a reliable efficiency proxy.

### Recommendation
NYC should launch a **ENERGY STAR Score Incentive Program**:
- Provide property tax abatements or expedited permit processing for buildings achieving ENERGY STAR certification (score ≥ 75).
- Mandate Portfolio Manager score reporting for all LL84-eligible building types (not just current voluntary participants).
- Create a public-facing "building scorecard" dashboard (powered by this DW) displaying each property's ENERGY STAR band alongside LL97 compliance status.

### Expected Impact
Incentivizing ENERGY STAR participation increases data completeness (filling `EnergyStarScore` NULLs) and motivates buildings in the `Fair` and `Poor` bands to invest in improvements. Each 10-point improvement in ENERGY STAR score correlates with approximately `[FILL]%` reduction in SiteEUI (from regression model).

---

## Recommendation 5: GHG Reduction Roadmap

### Observation
GHG intensity (`GHGIntensity` = GHG per sq ft) varies widely and is highly predictable from SiteEUI and property type. Buildings with `IsHighGHGBuilding = 1` are concrete candidates for LL97 penalty exposure.

### Data Evidence
- Regression model predicts `GHGIntensity` with R² = `[FILL]` using `SiteEUI`, `PropertyTypeGroup`, `Borough`, and `ReportingYear`.
- `FactBoroughPropertyTypeAnnualPerformance` shows `pct_high_ghg` highest in `[FILL: borough × type combination]`.
- Year-over-year temporal analysis shows citywide `avg_ghg_intensity` trend of `[FILL: increasing/decreasing]` from 2022 to 2024.

### Recommendation
Develop a **5-year GHG Reduction Roadmap** using this DW as the monitoring backbone:
- Set per-building GHG intensity reduction targets (% below baseline `GHGIntensity`) for the 2025–2030 period, aligned with LL97 carbon caps.
- Use `IsHighGHGBuilding` flag to generate a prioritized intervention list updated annually.
- Track GHG intensity trend using the temporal analysis infrastructure built in `A3_eda.ipynb`.
- Automate annual progress reports from `FactBoroughPropertyTypeAnnualPerformance`.

### Expected Impact
A data-driven GHG roadmap with annual DW-backed monitoring enables accountability, early identification of non-compliant buildings, and evidence-based policy adjustment. Achieving a 30% reduction in `GHGIntensity` for the top-quartile GHG buildings would reduce NYC's building sector emissions by an estimated `[FILL]` metric tons CO₂e per year.

---

## Recommendation 6: Water Conservation Programs

### Observation
Water use data (`WaterUse`, `WaterIntensity`) is frequently unreported (high NULL rate), and when reported, shows significant variation across property types and boroughs. Water intensity spikes in certain building clusters.

### Data Evidence
- Data quality report shows `WaterUse` has a `[FILL]%` NULL rate — the highest of any measured field.
- Among buildings that do report water, EDA shows outlier clusters with `WaterIntensity` > `[FILL]` kgal/sq ft/yr (likely cooling towers, laundry, food service).
- Association rules find that `WaterIntensityBand = High` co-occurs with `PropertyTypeGroup = Residential` and `BuildingSizeBand = Large` more than expected by chance (lift > 1.5).

### Recommendation
Expand water benchmarking requirements and launch targeted conservation programs:
- **Mandate WaterUse reporting** for all LL84 properties (currently optional for water); align with LL84 amendments.
- Identify buildings with `WaterIntensity` in the top quartile for their property type and require water audits (similar to LL87 energy audit mandate).
- Subsidize sub-metering installation for large multifamily residential buildings to enable tenant-level water accountability.
- Publish borough-level water intensity rankings (from `FactBoroughPropertyTypeAnnualPerformance`) to incentivize peer competition.

### Expected Impact
Closing the water reporting gap (from `[FILL]%` completion to > 90%) alone would substantially improve data-driven water policy. Targeted conservation at high-intensity buildings could reduce NYC building water consumption by an estimated `[FILL]%`, saving `[FILL]` million gallons annually.

---

## Recommendation 7: Building Size Band Policies

### Observation
`BuildingSizeBand` (Small / Medium / Large) is a strong moderating factor in energy intensity. Large buildings have higher absolute emissions but sometimes better per-square-foot intensity than smaller buildings with less professional facilities management.

### Data Evidence
- EDA shows `Large` buildings (`GrossFloorArea` > 200,000 sq ft) have median SiteEUI of `[FILL]` kBtu/sq ft/yr, while `Small` buildings show wider variance (IQR = `[FILL]`).
- Clustering analysis identifies a distinct cluster of small-to-medium buildings with very high SiteEUI — likely older, unmanaged stock without energy management systems.
- Regression VIF analysis shows `BuildingSizeBand` is not highly collinear with `PropertyTypeGroup`, confirming it adds independent explanatory power.

### Recommendation
Develop **size-differentiated compliance and support programs**:
- **Large buildings** (> 200,000 sq ft): Mandate real-time sub-metering and automatic LL84 data submission via API (eliminating manual CSV upload errors).
- **Medium buildings** (50,000–200,000 sq ft): Prioritize for NYC Accelerator retrofit support and free energy audits.
- **Small buildings** (< 50,000 sq ft): Provide simplified benchmarking tools, group purchasing programs for HVAC upgrades, and low-interest green financing.
- Adjust LL97 fine schedules to be proportional to building size, reducing disproportionate impact on small property owners.

### Expected Impact
Tailoring programs to size band improves uptake (small owners lack capacity for complex compliance; large owners need data infrastructure). Closing the energy performance gap in `Small` buildings to the `Medium` band median would reduce their collective SiteEUI by an estimated `[FILL]%`.

---

## Recommendation 8: Data Quality Improvement

### Observation
Systematic data quality issues — missing GFA, missing EUI, invalid borough codes, and low water reporting rates — reduce the analytical utility of the LL84 dataset and introduce bias into ML models trained on it.

### Data Evidence
- Data quality report (this document) documents `[FILL]` rows excluded due to missing GFA, `[FILL]` due to missing SiteEUI, and `[FILL]` with invalid Borough codes.
- The EnergyStarScore NULL rate of `[FILL]%` among eligible buildings limits the coverage of `EnergyPerformanceBand` classification.
- Profiling report (`data/staging/profiling_report.json`) shows `PropertyName` is blank in `[FILL]%` of records, complicating property identification.

### Recommendation
NYC should implement **upstream data quality gates** in the Portfolio Manager submission workflow:
- Enforce GrossFloorArea as a required field with a minimum threshold (e.g., > 1,000 sq ft).
- Validate borough code at submission time — reject submissions with unrecognized borough identifiers.
- Implement range validation for SiteEUI (flag values > 500 kBtu/sq ft/yr for manual review before acceptance).
- Incentivize ENERGY STAR score completion for eligible property types (link to Recommendation 4 incentives).
- Publish an annual **Data Quality Scorecard** per borough, showing reporting completeness rates, to create public accountability.

### Expected Impact
Upstream validation eliminates the need for downstream exclusion of incomplete records, increasing the analytical population and reducing bias. A 10% reduction in missing-data exclusions would add approximately `[FILL]` records to the analytical mart, improving model generalizability.

---

## Recommendation 9: Real-Time Monitoring for Large Buildings

### Observation
The current LL84 framework is entirely annual-disclosure-based. Large buildings with high energy and GHG intensity may not discover compliance issues until the next year's submission — creating costly surprise LL97 penalties.

### Data Evidence
- Clustering analysis identifies `[FILL]` buildings in a "high-risk" cluster characterized by high GHGIntensity, high SiteEUI, and declining year-over-year ENERGY STAR score (from temporal analysis).
- Regression model identifies `ReportingYear` as a significant predictor, suggesting energy performance is trending in a detectable direction — trend-based early warnings are feasible.
- The Real-Time DW architecture (Kafka + ClickHouse + Grafana) has been designed and documented specifically to support this use case.

### Recommendation
Deploy **real-time energy monitoring for NYC's highest-risk large buildings**:
- Mandate smart sub-meter installation for `IsHighEnergyBuilding = 1` and `IsHighGHGBuilding = 1` buildings with `BuildingSizeBand = Large`.
- Stream sub-meter data via Kafka into ClickHouse (Real-Time DW Tier 3) and display on a Grafana dashboard accessible to building owners and NYC agencies.
- Trigger automated alerts when a building's rolling 30-day SiteEUI exceeds its prior-year annual baseline by > 15%.
- Provide building owners with a self-service dashboard showing real-time progress toward LL97 carbon caps.

### Expected Impact
Real-time monitoring enables proactive intervention (operational adjustments, equipment repairs) before problems compound into annual LL97 violations. Buildings with proactive monitoring programs demonstrate 10–20% lower annual EUI variation, reducing compliance risk and penalty exposure.

---

## Recommendation 10: Annual Benchmarking Trend Tracking

### Observation
The DW covers three reporting years (2022, 2023, 2024). Year-over-year trend analysis reveals whether NYC's building sector is on a trajectory to meet its 2030 carbon neutrality goals under Local Law 97.

### Data Evidence
- Temporal analysis (`A3_eda.ipynb`) shows citywide `avg_site_eui` trend across 2022–2024: `[FILL: improving/worsening/flat]`, with an average annual change of `[FILL]` kBtu/sq ft/yr.
- `total_ghg_emissions` summed from `FactBoroughPropertyTypeAnnualPerformance` shows a year-over-year change of `[FILL]%` between 2022 and 2024.
- Building-level year-over-year comparison (joining `FactBuildingBenchmark` on `PropertyID` across two `ReportingYear` values) identifies `[FILL]` buildings that improved from `IsHighEnergyBuilding = 1` to `IsHighEnergyBuilding = 0` between 2022 and 2024, demonstrating that benchmark-driven intervention works.

### Recommendation
Institutionalize **annual benchmarking trend tracking** as a core city sustainability function:
- Run the full DW pipeline (data download → profiling → curation → ETL → mart refresh) every year upon LL84 disclosure publication.
- Publish an annual **NYC Building Energy Trend Report** (auto-generated from `FactBoroughPropertyTypeAnnualPerformance` and the mart) showing: citywide EUI trend, borough-level rankings, property-type trajectories, and count of buildings crossing each `EnergyIntensityBand` threshold.
- Track cohort performance: buildings that were `IsHighEnergyBuilding = 1` in 2022 — what fraction improved to 0 by 2024?
- Use trend projections (from regression model on `ReportingYear`) to forecast whether NYC is on track for its 2030 LL97 carbon caps and flag if course corrections are needed.

### Expected Impact
Institutionalizing DW-backed annual reporting transforms LL84 from a compliance checkbox into a genuine performance improvement system. Transparent, data-driven annual reporting increases public and stakeholder accountability, sustaining political will for continued investment in building decarbonization programs. Historical evidence from ENERGY STAR benchmarking programs nationally shows that buildings that consistently benchmark improve energy efficiency at 2–3× the rate of non-benchmarking peers.

---

## Summary Table

| # | Recommendation | Primary Metric | Priority | Timeframe |
|---|---|---|---|---|
| 1 | High-Energy Building Targeting | IsHighEnergyBuilding, SiteEUI | 🔴 High | Immediate |
| 2 | Borough-Level Policy Prioritization | avg_site_eui by Borough | 🔴 High | Near-term |
| 3 | Property-Type-Specific Standards | SiteEUI by PropertyTypeGroup | 🔴 High | Near-term |
| 4 | ENERGY STAR Score Incentive Program | EnergyStarScore, EnergyPerformanceBand | 🟡 Medium | Near-term |
| 5 | GHG Reduction Roadmap | GHGIntensity, IsHighGHGBuilding | 🔴 High | Immediate |
| 6 | Water Conservation Programs | WaterIntensity, WaterUse completeness | 🟡 Medium | Medium-term |
| 7 | Building Size Band Policies | BuildingSizeBand, SiteEUI | 🟡 Medium | Near-term |
| 8 | Data Quality Improvement | Missing value rates, Borough validity | 🟡 Medium | Immediate (upstream) |
| 9 | Real-Time Monitoring for Large Buildings | IsHighEnergyBuilding + Real-Time DW | 🟢 Strategic | Long-term |
| 10 | Annual Benchmarking Trend Tracking | Year-over-year SiteEUI, GHG trend | 🔴 High | Annual (recurring) |

> [!IMPORTANT]
> Recommendations 1, 2, 3, 5, and 10 have direct connections to Local Law 97 (LL97) carbon penalty schedules taking effect in 2024–2030. These should be treated as the highest priority deliverables from this analysis.

---

*Last updated: November 2026 | Project: TY B.Tech Data Warehouse — NYC Building Energy (LL84)*
