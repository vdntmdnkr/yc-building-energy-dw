# NYC Building Energy & Sustainability Analytics
## TY B.Tech Integrated Data Warehouse, OLAP and Data Mining Project

### Project Title
**Design and Implementation of Batch, Distributed and Real-Time Building Energy Data Warehouse with OLAP, Dashboard Analytics and Predictive Data Mining**

---

## Dataset
- **Name:** NYC Building Energy and Water Data Disclosure for Local Law 84
- **Source:** NYC Open Data / Department of Buildings
- **Link:** https://data.cityofnewyork.us/Environment/NYC-Building-Energy-and-Water-Data-Disclosure-for-/5zyy-y8am/about_data
- **Period:** 2022 onward (multiple annual reporting years combined)
- **Format:** CSV via NYC Open Data API

---

## Project Parts

| Part | Description |
|------|-------------|
| A | Dataset Understanding, Data Curation and EDA |
| B | Dimensional Modelling (Star, Snowflake, Fact Constellation) |
| C | Batch Data Warehouse (PostgreSQL) |
| D | Distributed Data Warehouse (Citus) |
| E | Real-Time Data Warehouse (Kafka + Spark + ClickHouse) |
| F | OLAP and Dashboard (Power BI + Grafana) |
| G | Regression Analysis |
| H | Association Rule Mining |
| I | Decision Tree Classification |
| J | Architecture Evaluation |

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Programming | Python 3.10+ |
| Data Processing | Pandas, NumPy |
| Large-Scale Processing | Apache Spark 3.x |
| Batch Warehouse | PostgreSQL 15 |
| Distributed Warehouse | Citus / PostgreSQL |
| Messaging | Apache Kafka |
| Streaming | Spark Structured Streaming |
| Real-Time Store | ClickHouse |
| Machine Learning | Scikit-learn |
| Association Mining | mlxtend |
| Dashboard | Power BI |
| Real-Time Dashboard | Grafana |
| Containerization | Docker / Docker Compose |
| Version Control | Git / GitHub |

---

## Repository Structure

```
.
├── data/
│   ├── raw/              # Original downloaded dataset(s)
│   ├── curated/          # Cleaned, feature-engineered data
│   └── staging/          # Staging area for ETL
├── notebooks/
│   ├── A1_data_profiling.ipynb
│   ├── A2_data_curation.ipynb
│   ├── A3_eda.ipynb
│   ├── G_regression.ipynb
│   ├── H_association_mining.ipynb
│   └── I_decision_tree.ipynb
├── sql/
│   ├── batch_dw/         # PostgreSQL schema + ETL scripts
│   ├── distributed_dw/   # Citus distribution scripts
│   ├── olap/             # OLAP cube queries
│   └── mart/             # Analytical mart
├── etl/                  # Python ETL pipeline scripts
├── streaming/            # Kafka producer + Spark streaming
├── ml/                   # ML helper scripts
├── dashboard/            # Power BI .pbix / Grafana JSON
├── docs/                 # Data dictionary, quality report, architecture
├── docker/               # Docker Compose for infrastructure
└── README.md
```

---

## Quick Start

### 1. Download Dataset
```bash
python etl/00_download_dataset.py
```

### 2. Run Data Curation
```bash
jupyter notebook notebooks/A2_data_curation.ipynb
```

### 3. Set Up PostgreSQL Batch DW
```bash
psql -U postgres -f sql/batch_dw/01_create_schema.sql
python etl/02_load_batch_dw.py
```

### 4. Start Streaming Infrastructure
```bash
cd docker && docker compose up -d
python streaming/kafka_producer.py
python streaming/spark_streaming_consumer.py
```

### 5. Run ML Notebooks
```bash
jupyter notebook notebooks/G_regression.ipynb
jupyter notebook notebooks/H_association_mining.ipynb
jupyter notebook notebooks/I_decision_tree.ipynb
```

---

## Dataset Citation
- **Dataset:** NYC Building Energy and Water Data Disclosure for Local Law 84
- **Publisher:** NYC Open Data / NYC Department of Buildings
- **Access Link:** https://data.cityofnewyork.us/Environment/NYC-Building-Energy-and-Water-Data-Disclosure-for-/5zyy-y8am/about_data
- **Selected Period:** Calendar years 2022–2024
- **Columns Used:** See `docs/data_dictionary.md`
- **Filters Applied:** ReportingYear >= 2022
- **Enrichment Sources:** None (all derived attributes computed from source fields; see `docs/data_dictionary.md`)
