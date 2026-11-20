# Architecture Comparison Report
## NYC Building Energy Benchmarking (Local Law 84) — Data Warehouse Project

> [!NOTE]
> This report evaluates three data warehouse architectures — Batch DW, Distributed DW, and Real-Time DW — in the context of NYC LL84 sustainability reporting. It includes architecture diagrams, a parameter-by-parameter comparison, a final recommendation, and a scored decision matrix.

---

## 1. Architecture Overview Diagrams

### 1.1 Batch Data Warehouse (Recommended — Primary)

```
┌─────────────┐   Download    ┌──────────────┐   Python ETL  ┌────────────────────┐
│  NYC Open   │ ────────────► │ Raw CSV File │ ────────────► │  PostgreSQL        │
│  Data API   │               │  (data/raw/) │               │  Staging Schema    │
└─────────────┘               └──────────────┘               └────────────────────┘
                                                                        │
                                                                  Dim/Fact Load
                                                                        ▼
┌─────────────────┐  SQL Queries  ┌──────────────────────┐   OLAP    ┌───────────┐
│   Power BI /    │ ◄──────────── │   PostgreSQL         │ ◄──────── │  Pandas   │
│   Tableau       │               │   Dimensional DW     │           │  Analytics│
└─────────────────┘               └──────────────────────┘           └───────────┘
```

**Flow:** Raw CSV → Python ETL (curation notebooks) → PostgreSQL Staging → Dimensional DW (Star Schema) → OLAP Queries → Power BI Dashboards

---

### 1.2 Distributed Data Warehouse

```
┌──────────────────────┐  Partition   ┌──────────────────────────────────────────────┐
│  NYC LL84 Dataset    │ ──────────► │            Apache Spark                       │
│  (Multi-year, large) │             │   (PySpark ETL — parallel partition reads)   │
└──────────────────────┘             └──────────────────────────────────────────────┘
                                                          │
                                              Distributed Write
                                                          ▼
                                     ┌────────────────────────────────────┐
                                     │  Citus Coordinator Node            │
                                     │  (PostgreSQL-compatible interface) │
                                     └────────────────────────────────────┘
                                          /           │           \
                                         /            │            \
                               ┌─────────┐    ┌─────────┐    ┌─────────┐
                               │ Citus   │    │ Citus   │    │ Citus   │
                               │ Worker 1│    │ Worker 2│    │ Worker N│
                               └─────────┘    └─────────┘    └─────────┘
                                                   │
                                      Distributed OLAP Queries
                                                   ▼
                                         ┌──────────────┐
                                         │   Power BI   │
                                         └──────────────┘
```

**Flow:** Partitioned Data → Apache Spark (parallel ETL) → Citus Coordinator → Worker Nodes (sharded storage) → Distributed OLAP → Power BI

---

### 1.3 Real-Time Data Warehouse

```
┌────────────────────┐   Historical   ┌──────────────────┐   Produce Events   ┌───────────┐
│  Historical LL84   │ ─────────────► │  Python Producer │ ─────────────────► │   Kafka   │
│  Records (CSV)     │               │  (kafka_producer)│                     │  Topic    │
└────────────────────┘               └──────────────────┘                     └───────────┘
                                                                                     │
                                                                           Stream Consume
                                                                                     ▼
                                                                        ┌────────────────────┐
                                                                        │   Spark Streaming  │
                                                                        │   (Structured      │
                                                                        │    Streaming)      │
                                                                        └────────────────────┘
                                                                                     │
                                                                             Micro-batch Write
                                                                                     ▼
                                                                        ┌────────────────────┐
                                                                        │    ClickHouse      │
                                                                        │  (Columnar OLAP)   │
                                                                        └────────────────────┘
                                                                                     │
                                                                             Real-time Query
                                                                                     ▼
                                                                        ┌────────────────────┐
                                                                        │    Grafana         │
                                                                        │  (Live Dashboard)  │
                                                                        └────────────────────┘
```

**Flow:** Historical Records → Python Kafka Producer → Kafka Topic → Spark Structured Streaming → ClickHouse (columnar store) → Grafana Live Dashboards

---

## 2. Architecture Comparison Table

| Parameter | Batch DW | Distributed DW | Real-Time DW |
|---|---|---|---|
| **Data arrival pattern** | Periodic / annual bulk download | Large partitioned batch (multi-year) | Continuous events / smart-meter streams |
| **Processing paradigm** | Sequential ETL (Python + SQL) | Parallel / distributed ETL (PySpark) | Streaming ETL (Spark Structured Streaming) |
| **Storage engine** | PostgreSQL 15 (row-store) | Citus / PostgreSQL (sharded row-store) | ClickHouse (columnar store) |
| **Query latency** | Seconds to minutes (OLAP on single node) | Seconds (distributed parallel scans) | Sub-second to seconds (columnar, pre-aggregated) |
| **Historical analytics** | Excellent — full SQL, window functions, CTEs | Excellent — same SQL dialect, horizontal scale | Moderate — requires materialized views for complex history |
| **Live / near-real-time monitoring** | Poor — data refreshed once per batch cycle | Limited — batch intervals (minutes to hours) | Excellent — sub-second lag from event arrival |
| **Horizontal scalability** | Moderate — single-node vertical scaling only | High — add Citus worker nodes; shard redistribution | High — Kafka partitions + ClickHouse distributed tables |
| **Operational complexity** | Low — PostgreSQL is well-understood; minimal ops overhead | Medium — Citus cluster management, shard rebalancing | High — Kafka cluster, Zookeeper, Spark cluster, ClickHouse, Grafana |
| **Query performance at scale** | Baseline (reference) | 2–5× faster at large scale (parallelism) | Near-real-time; columnar compression aids aggregation |
| **Fault tolerance / recovery** | ACID transactions; WAL-based point-in-time recovery | Shard replication; coordinator failover | Kafka consumer offsets; at-least-once delivery; ClickHouse replication |
| **Resource requirement** | Low — single PostgreSQL server (4–8 GB RAM) | Medium–High — multiple nodes; Spark cluster | High — Kafka, Spark, ClickHouse each require dedicated resources |
| **Best suited for** | Annual LL84 disclosure reporting, academic analysis | City-wide benchmarking at scale (millions of records) | Live smart-meter feeds, real-time carbon dashboards |

---

## 3. Final Recommendation: Hybrid Architecture

For the NYC LL84 sustainability reporting context, a **tiered hybrid architecture** is recommended, selecting the best tool for each use case:

### Tier 1: Batch DW (PostgreSQL) — Annual Reporting ✅ *Implemented*

**Use when:** Processing the annual LL84 CSV download for academic analysis, SQL-based EDA, dimensional warehouse, and machine learning feature extraction.

**Justification:**
- LL84 data is published annually — there is no requirement for real-time ingestion.
- PostgreSQL is mature, fully ACID-compliant, and has excellent SQL support (window functions, CTEs, extensions).
- Low operational complexity: a single Docker container (`postgres:15`) is sufficient.
- The star-schema design (FactBuildingBenchmark + 5 dimensions) fits naturally into a single-node relational database at the scale of NYC's ~25,000 annual benchmark submissions.
- Power BI and Tableau connect natively via ODBC/JDBC.

---

### Tier 2: Distributed DW (Citus/PostgreSQL) — Large-Scale Benchmarking 🔭 *Future Scale*

**Use when:** The dataset grows to encompass multiple cities, nationwide benchmarking, or multi-decade historical data exceeding single-node PostgreSQL capacity.

**Justification:**
- Citus extends PostgreSQL with transparent sharding — no application-layer changes required.
- Maintains full PostgreSQL SQL compatibility: the same queries from Tier 1 run unchanged on Citus.
- Benchmarks show 2–5× query speedup for large aggregation queries when distributed across worker nodes.
- Horizontal scaling by adding worker nodes avoids expensive single-node vertical upgrades.
- Recommended transition threshold: > 50 million records or query times exceeding 60 seconds on Tier 1.

---

### Tier 3: Real-Time DW (Kafka + ClickHouse + Grafana) — Smart-Meter Feeds 🔭 *Future Capability*

**Use when:** NYC deploys real-time smart meter data or LL97 compliance monitoring requires live energy dashboards.

**Justification:**
- Kafka provides durable, replay-capable event streaming with exactly-once semantics.
- ClickHouse columnar storage delivers sub-second aggregate query responses on billions of rows.
- Grafana provides live dashboard alerting (e.g., alert when a building's hourly EUI exceeds its baseline).
- Not warranted for current LL84 data (annual batch) — introduces unnecessary operational overhead.

---

### Experimental Evidence Placeholder

| Experiment | Batch DW (PostgreSQL) | Distributed DW (Citus, 3 workers) | Real-Time DW (ClickHouse) |
|---|---|---|---|
| Aggregate query: avg SiteEUI by Borough × Year | `[FILL: ms]` | `[FILL: ms]` | `[FILL: ms]` |
| Full table scan: 25,000 rows, 20 columns | `[FILL: ms]` | `[FILL: ms]` | `[FILL: ms]` |
| Concurrent query throughput (10 users) | `[FILL: QPS]` | `[FILL: QPS]` | `[FILL: QPS]` |
| ETL load time (25,000 rows) | `[FILL: s]` | `[FILL: s]` | `[FILL: s]` |
| Storage footprint (raw + indexes) | `[FILL: MB]` | `[FILL: MB]` | `[FILL: MB]` |

> [!NOTE]
> Populate this table by running the benchmarking scripts in `scripts/benchmark_query_performance.py` against each deployed environment.

---

## 4. Architecture Decision Matrix

Architectures are scored on five criteria, each weighted by importance for the NYC LL84 context. Scores are on a 1–5 scale (5 = best).

| Criterion | Weight | Batch DW | Distributed DW | Real-Time DW |
|---|---|---|---|---|
| **Cost** (infrastructure & ops) | 25% | 5 | 3 | 2 |
| **Complexity** (setup & maintenance) | 20% | 5 | 3 | 1 |
| **Latency** (time from data arrival to dashboard) | 15% | 2 | 3 | 5 |
| **Scalability** (handling data volume growth) | 20% | 2 | 5 | 5 |
| **Maintainability** (team skill, documentation, long-term) | 20% | 5 | 3 | 2 |
| **Weighted Score** | **100%** | **3.95** | **3.40** | **2.95** |

**Scoring rationale:**

- **Batch DW** scores highest on cost (single container), complexity (standard PostgreSQL), and maintainability (widely understood). It scores lowest on latency (annual refresh) and scalability (single-node limit), but these are acceptable constraints for the current LL84 use case.
- **Distributed DW** balances scalability and SQL compatibility well but adds Citus cluster management overhead.
- **Real-Time DW** excels only on latency — which is irrelevant for annual-publication LL84 data — while incurring the highest cost, complexity, and maintenance burden.

> [!TIP]
> The Batch DW (PostgreSQL) is the **recommended primary architecture** for this project, with Distributed and Real-Time tiers documented as a roadmap for future scale and capability evolution.

---

*Last updated: November 2026 | Project: TY B.Tech Data Warehouse — NYC Building Energy (LL84)*
