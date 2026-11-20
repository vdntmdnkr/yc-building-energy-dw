# Power BI Sustainability Analytics Dashboard Specification
## NYC Building Energy and Water Data Disclosure (Local Law 84)

This document provides the complete technical design, semantic data model, DAX measures, and visual configuration for building the enterprise **Power BI Dashboard** connected to the PostgreSQL / Citus Dimensional Data Warehouse.

---

## 1. Power BI Data Model Architecture

The semantic model implements a clean **Star Schema** with 1-to-Many single-directional filter relationships propagating from Dimension tables to Fact tables.

```
       [DimYear] (1) ─────────────< (*)
                                     │
   [DimGeography] (1) ────────────< (*) [FactBuildingBenchmark]
                                     │
    [DimProperty] (1) ────────────< (*)
                                     │
[DimPropertyType] (1) ────────────< (*)
                                     │
[DimPerformanceBand] (1) ─────────< (*)
```

### Table Relationships:
1. `DimYear[YearKey]` 1 ── * `FactBuildingBenchmark[YearKey]` (Single)
2. `DimGeography[GeographyKey]` 1 ── * `FactBuildingBenchmark[GeographyKey]` (Single)
3. `DimProperty[PropertyKey]` 1 ── * `FactBuildingBenchmark[PropertyKey]` (Single)
4. `DimPropertyType[PropertyTypeKey]` 1 ── * `FactBuildingBenchmark[PropertyTypeKey]` (Single)
5. `DimPerformanceBand[PerformanceKey]` 1 ── * `FactBuildingBenchmark[PerformanceKey]` (Single)

---

## 2. Core DAX Measures Table (`_Measures`)

Create a dedicated DAX measure container table with these calculations:

```dax
// 1. Total Benchmarked Properties
Total Properties = DISTINCTCOUNT(FactBuildingBenchmark[PropertyKey])

// 2. Total Gross Floor Area (Million Sq Ft)
Total GFA (MSqFt) = 
DIVIDE(SUM(FactBuildingBenchmark[GrossFloorArea]), 1000000, 0)

// 3. Total Portfolio Energy Consumption (Billion kBtu)
Total Energy Use (Billion kBtu) = 
DIVIDE(SUM(FactBuildingBenchmark[SiteEnergyUse]), 1000000000, 0)

// 4. Portfolio Average Site EUI (Weighted by Floor Area)
Avg Site EUI = 
DIVIDE(
    SUM(FactBuildingBenchmark[SiteEnergyUse]),
    SUM(FactBuildingBenchmark[GrossFloorArea]),
    0
)

// 5. Total Greenhouse Gas Emissions (Metric Tons CO2e)
Total GHG Emissions = SUM(FactBuildingBenchmark[GHGEmissions])

// 6. Average ENERGY STAR Score
Avg Energy Star Score = 
AVERAGE(FactBuildingBenchmark[EnergyStarScore])

// 7. High-Energy Buildings Count
High Energy Count = 
CALCULATE(
    COUNTROWS(FactBuildingBenchmark),
    FactBuildingBenchmark[IsHighEnergyBuilding] = 1
)

// 8. High-Energy Building Percentage
High Energy % = 
DIVIDE([High Energy Count], [Total Properties], 0)

// 9. Average GHG Intensity (kg CO2e / Sq Ft)
Avg GHG Intensity = 
DIVIDE(
    SUM(FactBuildingBenchmark[GHGEmissions]) * 1000,
    SUM(FactBuildingBenchmark[GrossFloorArea]),
    0
)

// 10. Year-over-Year Energy Change %
YoY Energy Change % = 
VAR CurrentYearEnergy = [Total Energy Use (Billion kBtu)]
VAR PriorYearEnergy = 
    CALCULATE(
        [Total Energy Use (Billion kBtu)],
        SAMEPERIODLASTYEAR(DimYear[ReportingYear])
    )
RETURN
    DIVIDE(CurrentYearEnergy - PriorYearEnergy, PriorYearEnergy, 0)
```

---

## 3. Dashboard Page Layouts & Visual Configurations

### Page 1: Executive Sustainability Dashboard
**Target Audience:** Chief Sustainability Officer, City Regulators, Portfolio Executives

| Visual Component | Chart Type | Fields / Measures | Formatting & Slicers |
|---|---|---|---|
| **KPI Card 1** | Card | `[Total Properties]` | Formatted as integer with thousands separator |
| **KPI Card 2** | Card | `[Total GFA (MSqFt)]` | Formatted as `0.0 M sqft` |
| **KPI Card 3** | Card | `[Total Energy Use (Billion kBtu)]` | Formatted as `0.0 B kBtu` |
| **KPI Card 4** | Card | `[Avg Site EUI]` | Formatted as `0.0 kBtu/ft²` with target callout |
| **KPI Card 5** | Card | `[Total GHG Emissions]` | Formatted as `0.00 M tCO2e` |
| **KPI Card 6** | Card | `[Avg Energy Star Score]` | Formatted as `0` (1-100 gauge) |
| **Yearly Trend** | Area Chart | X: `DimYear[ReportingYear]`, Y: `[Total GHG Emissions]`, Secondary: `[Avg Site EUI]` | Dual-axis showing emissions vs intensity decline |
| **Borough Map** | Filled Map | Location: `DimGeography[Borough]`, Color Saturation: `[Avg Site EUI]` | Tooltip with property count and total energy |
| **Global Slicers** | Dropdown / Tile | `DimYear[ReportingYear]`, `DimGeography[Borough]`, `DimPropertyType[PropertyTypeGroup]` | Top banner |

---

### Page 2: Property and Type Analytics
**Target Audience:** Building Engineers, Facility Managers, Energy Auditors

| Visual Component | Chart Type | Fields / Measures | Description |
|---|---|---|---|
| **Energy by Type** | Clustered Bar | Y: `DimPropertyType[PrimaryPropertyType]`, X: `[Total Energy Use (Billion kBtu)]` | Top 15 property types by total consumption |
| **EUI by Type** | Clustered Column | X: `DimPropertyType[PropertyTypeGroup]`, Y: `[Avg Site EUI]` | Highlights commercial & specialized facilities |
| **Size Stratification** | Treemap | Group: `DimProperty[SizeBand]`, Values: `[Total Properties]`, Color: `[Avg Site EUI]` | Explores small vs medium vs large impact |
| **High EUI Focus** | Table / Grid | Columns: `PropertyID`, `PropertyName`, `Borough`, `PrimaryPropertyType`, `SiteEUI`, `GHGEmissions` | Filtered to `[IsHighEnergyBuilding] = 1`, top 50 sorted by Site EUI |
| **Performance Bands** | Donut Chart | Legend: `DimPerformanceBand[EnergyIntensityBand]`, Values: `[Total Properties]` | Low (<50), Medium (50-100), High (100-200), Very High (>200) |

---

### Page 3: Geographic Sustainability Analytics
**Target Audience:** Urban Planners, Borough Presidents, Utility Demand Planners

| Visual Component | Chart Type | Fields / Measures | Description |
|---|---|---|---|
| **Borough Energy & GHG** | 100% Stacked Bar | Y: `DimGeography[Borough]`, X: `[Total Energy Use]`, `[Total GHG Emissions]` | Compares borough proportional contributions |
| **Property Density** | Column Chart | X: `DimGeography[Borough]`, Y: `[Total Properties]` | Visualizes building count distribution across boroughs |
| **Borough EUI Comparison** | Scatter Plot | X: `[Total GFA (MSqFt)]`, Y: `[Avg Site EUI]`, Size: `[Total GHG Emissions]`, Legend: `DimGeography[Borough]` | Identifies high-density intensity clusters |
| **Emission Concentration** | Funnel / Matrix | Rows: `Borough`, Columns: `PropertyTypeGroup`, Values: `[Total GHG Emissions]` | Heatmap matrix identifying borough hotspots |

---

### Page 4: Energy and Emissions Deep Dive
**Target Audience:** Policy Analysts, Environmental Compliance Officers

| Visual Component | Chart Type | Fields / Measures | Description |
|---|---|---|---|
| **EUI Distribution** | Histogram / Column | Bins of `FactBuildingBenchmark[SiteEUI]` (width 20), Count of properties | Displays positive skew of energy intensity |
| **GHG vs Energy Correlation** | Scatter Plot | X: `FactBuildingBenchmark[SiteEnergyUse]`, Y: `FactBuildingBenchmark[GHGEmissions]`, Legend: `DimPropertyType[PropertyTypeGroup]` | Evaluates fuel source carbon intensity |
| **ENERGY STAR Distribution** | Bar Chart | X: `DimPerformanceBand[EnergyStarBand]`, Y: `[Total Properties]` | Categorizes properties into Excellent, Good, Fair, Poor |
| **Water Intensity** | Clustered Column | X: `DimPropertyType[PropertyTypeGroup]`, Y: Average Water Intensity | Evaluates cooling tower water and residential domestic use |
| **Multi-Year Variance** | Waterfall Chart | Category: `DimYear[ReportingYear]`, Y: `[YoY Energy Change %]` | Demonstrates year-over-year decarbonization progress |

---

## 4. How to Connect Power BI to the Data Warehouse

1. **Launch Power BI Desktop**.
2. Select **Get Data** → **PostgreSQL database**.
3. Server: `localhost:5432`, Database: `building_energy_dw`.
4. Data Connectivity mode: Select **DirectQuery** for live OLAP synchronization or **Import** for maximum in-memory DAX performance.
5. Select tables:
   - `DimYear`
   - `DimProperty`
   - `DimGeography`
   - `DimPropertyType`
   - `DimPerformanceBand`
   - `FactBuildingBenchmark`
   - `FactBoroughPropertyTypeAnnualPerformance`
6. Verify relationships in the **Model View** matching the Star Schema above.
7. Paste the DAX measures from Section 2 into a new table named `_Measures`.
