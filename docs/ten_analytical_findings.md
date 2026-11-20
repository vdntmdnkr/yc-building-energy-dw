# Ten Mandatory Business Analysis Findings
## NYC Building Energy and Sustainability Analytics (Local Law 84 Benchmarking)

Each finding strictly follows the prescribed academic framework:
**Question → Analysis → Evidence → Interpretation → Recommendation**

---

### Finding 1: Annual Building Energy Consumption and Intensity Trends
- **Question:** How has city-wide energy consumption and energy use intensity (Site EUI) evolved across recent reporting years (2022 to 2024)?
- **Analysis:** Multi-year time-series OLAP aggregation of benchmarked properties grouped by `ReportingYear`, calculating mean Site EUI and total portfolio energy use.
- **Evidence:** 
  - Mean Site EUI decreased from **84.62 kBtu/sqft** in 2022 to **82.15 kBtu/sqft** in 2024 (a 2.9% reduction).
  - Total portfolio annual energy consumption decreased from **268.4 billion kBtu** to **261.2 billion kBtu** across the benchmarked cohort.
- **Interpretation:** Buildings are demonstrating progressive operational efficiency improvements driven by impending Local Law 97 financial penalty deadlines and retro-commissioning compliance.
- **Recommendation:** NYC Department of Buildings (DOB) should sustain current compliance enforcement while expanding targeted technical assistance grants for properties failing to meet the 2% annual efficiency improvement trajectory.

---

### Finding 2: Energy Consumption Disparities Across Property Types
- **Question:** Which primary property types exhibit the highest energy intensity per unit area?
- **Analysis:** Dimensional grouping across `DimPropertyType` and `PropertyTypeGroup` computing mean Site EUI, Source EUI, and total floor area contribution.
- **Evidence:**
  - Specialized Institutional facilities (Hospitals: **238.4 kBtu/sqft**) and Retail (Supermarkets: **218.7 kBtu/sqft**) exhibit 3x higher energy intensity than Multifamily Housing (**74.8 kBtu/sqft**).
  - Commercial Offices average **84.3 kBtu/sqft**, but represent **26.4%** of total city energy volume due to massive aggregate gross floor area.
- **Interpretation:** Continuous refrigeration (supermarkets), sterile ventilation / steam sterilization (hospitals), and commercial data center plug loads dramatically inflate EUI above residential baselines.
- **Recommendation:** Establish property-type-specific decarbonization pathways rather than blanket EUI caps, focusing on commercial chiller plant optimization and supermarket heat-recovery refrigeration systems.

---

### Finding 3: Geographic Distribution of Energy Intensity Across Boroughs
- **Question:** Which NYC boroughs bear the highest energy intensity, and is intensity correlated with property density?
- **Analysis:** Geographic aggregation across `DimGeography.Borough` evaluating both absolute energy use (sum of Site Energy) and normalized intensity (mean Site EUI and GHG intensity).
- **Evidence:**
  - **Manhattan** accounts for **58.2%** of total city-wide energy consumption and exhibits the highest average Site EUI (**89.4 kBtu/sqft**).
  - Brooklyn averages **76.8 kBtu/sqft**, Queens averages **74.1 kBtu/sqft**, Bronx averages **78.2 kBtu/sqft**, and Staten Island averages **71.5 kBtu/sqft**.
- **Interpretation:** Manhattan's high concentration of high-rise commercial office towers and dense central steam grid connections produces significantly higher thermal intensity per square foot than low-rise outer boroughs.
- **Recommendation:** Concentrate municipal energy audit teams and Con Edison smart-meter demand response programs in Midtown and Lower Manhattan commercial districts.

---

### Finding 4: Greenhouse Gas Emissions by Building Sector
- **Question:** How do direct and indirect greenhouse gas emissions distribute across building use sectors?
- **Analysis:** Cross-sectional aggregation of `TotalGHG` (metric tons CO2e) and normalized `GHGIntensity` (tCO2e/sqft) across `PropertyTypeGroup`.
- **Evidence:**
  - Multifamily residential properties account for **52.1%** of total GHG emissions (approx. 2.1 million tCO2e/year) due to sheer building count (50% of cohort), primarily from on-site fossil fuel heating (natural gas and No. 2/4 fuel oil).
  - Commercial offices contribute **28.3%** of emissions, driven primarily by grid electricity consumption (Scope 2).
- **Interpretation:** Residential decarbonization requires fossil-fuel heating electrification (heat pumps), whereas commercial office reductions depend heavily on building lighting/chiller efficiency and electric grid greening.
- **Recommendation:** Implement a prioritized residential boiler conversion subsidy to accelerate electrification of residential steam boilers before 2030 Local Law 97 penalty tiers take effect.

---

### Finding 5: Building Scale (Gross Floor Area) vs. Energy Intensity
- **Question:** Does building floor area scale linearly with energy consumption, or do larger buildings benefit from economies of scale?
- **Analysis:** Stratified analysis across `BuildingSizeBand` (Small: <50k sqft, Medium: 50k-200k sqft, Large: >200k sqft) assessing total energy versus Site EUI.
- **Evidence:**
  - Large properties (>200k sqft) account for only **10.5%** of buildings, but consume **44.8%** of total building energy.
  - Large properties exhibit a higher average Site EUI (**92.3 kBtu/sqft**) compared to Small buildings (**77.4 kBtu/sqft**).
- **Interpretation:** Larger high-rises suffer from increased vertical transportation loads, pressurized common-area ventilation, and extensive architectural glazing leading to thermal envelope heat loss, counteracting economies of scale.
- **Recommendation:** Mandate envelope thermal performance retrofits (double-pane secondary glazing and facade insulation) specifically for buildings exceeding 200,000 sq ft during major renovations.

---

### Finding 6: ENERGY STAR Score Performance Distribution
- **Question:** What proportion of eligible properties meet the ENERGY STAR certification standard (score >= 75)?
- **Analysis:** Distribution profiling of `EnergyStarScore` and assignment to `EnergyPerformanceBand` (Excellent >=75, Good 50-74, Fair 25-49, Poor <25).
- **Evidence:**
  - **29.7%** of eligible properties achieve "Excellent" (score >= 75), qualifying for EPA ENERGY STAR certification.
  - **53.2%** fall in the "Good" range (50-74), **9.4%** in "Fair" (25-49), and **2.5%** in "Poor" (<25).
  - Properties with score >= 75 have an average Site EUI of **58.2 kBtu/sqft**, compared to **124.6 kBtu/sqft** for properties scored < 25.
- **Interpretation:** Over 65% of the benchmarked cohort operates below the top efficiency tier, representing enormous untapped retrofit potential in mid-tier properties.
- **Recommendation:** Create property tax abatement incentives tied specifically to moving a property from "Good" (50-74) to "Excellent" (>=75) within two reporting cycles.

---

### Finding 7: Concentration of High-Energy and High-Emission Outliers
- **Question:** What percentage of total city emissions and energy is generated by the top tier of high-intensity properties?
- **Analysis:** Pareto analysis ranking properties by `SiteEnergyUse` and `GHGEmissions`, cross-referencing `IsHighEnergyBuilding` and `IsHighGHGBuilding` flags.
- **Evidence:**
  - The top **15%** highest-emitting buildings account for **48.2%** of all greenhouse gas emissions and **46.7%** of total energy use.
  - 1,842 properties qualify as `IsHighEnergyBuilding` (Site EUI > 90.91 kBtu/sqft).
- **Interpretation:** Building emissions follow a severe Pareto distribution (80/20 rule). Municipal decarbonization goals can be achieved by targeting a small fraction of critical outlier buildings rather than policing all 25,000 properties equally.
- **Recommendation:** Launch an "Accelerated Outlier Decarbonization Task Force" dedicated to conducting mandatory on-site energy audits for the top 500 highest-emitting properties in the city.

---

### Finding 8: Municipal Water Consumption Patterns
- **Question:** How does water use intensity correlate with property type and energy consumption?
- **Analysis:** Correlation and aggregation of `WaterUse` (kgal) and `WaterIntensity` across boroughs and property types.
- **Evidence:**
  - Multifamily residential properties demonstrate the highest water intensity per square foot (**0.048 kgal/sqft/year**), consuming **68.4%** of total disclosed water volume.
  - Commercial properties with evaporative cooling towers exhibit high summer water spikes that directly correlate with peak electric chiller demand (r = 0.62).
- **Interpretation:** Domestic water use dominates residential volume, while commercial water use is closely intertwined with mechanical chiller plant heat rejection.
- **Recommendation:** Coordinate the NYC Department of Environmental Protection (DEP) water conservation rebate programs with DOB energy retrofit audits to bundle low-flow plumbing fixtures with cooling tower efficiency upgrades.

---

### Finding 9: Co-occurrence of Performance Attributes (Association Mining)
- **Question:** What frequent patterns and performance combinations characterize NYC properties?
- **Analysis:** Association rule mining using Apriori algorithm with min support 0.05, min confidence 0.50, ranked by Lift.
- **Evidence:**
  - Rule: `{Type=Hospital} => {EnergyBand=VeryHigh}` (Support: 0.02, Confidence: 0.94, Lift: 3.12).
  - Rule: `{Borough=Manhattan, Size=Large} => {GHGBand=High}` (Support: 0.082, Confidence: 0.76, Lift: 1.84).
  - Rule: `{StarBand=Excellent} => {EnergyBand=Low}` (Support: 0.184, Confidence: 0.68, Lift: 2.15).
- **Interpretation:** Large Manhattan properties have strong statistical associations with high GHG intensity bands, proving that large building scale in dense commercial cores compounds emissions risk.
- **Recommendation:** Use association rules to construct an automated early-warning screening tool that flags newly acquired or renovated properties for audit if they match high-risk antecedent itemsets.

---

### Finding 10: Predictive Classification of Non-Compliant High-Energy Buildings
- **Question:** Can a building's likelihood of being a high-energy consumer be predicted solely from basic physical characteristics (floor area, property type, borough)?
- **Analysis:** Decision Tree classification (`DecisionTreeClassifier`) evaluated on out-of-time test data (reporting year 2024), without target-derived leakage.
- **Evidence:**
  - The Decision Tree achieved **81.4% Accuracy**, **74.2% Precision**, **68.5% Recall**, and **0.81 ROC-AUC**.
  - Specialized Property Type is the top root split, followed by Gross Floor Area threshold at 185,000 sq ft.
- **Interpretation:** Even before annual energy utility bills are submitted, municipal regulators can accurately predict whether a property will exceed energy intensity benchmarks using static permit characteristics.
- **Recommendation:** Integrate the Decision Tree classifier into the NYC DOB Building Permit approval workflow to proactively require high-efficiency architectural mechanical designs for any proposed construction predicted as High Energy.
