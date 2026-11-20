"""
04_load_batch_dw.py
===================
Orchestrates the full batch ETL into the data warehouse by calling the
PostgreSQL stored function fn_run_full_etl().

After the ETL runs it prints:
  - Row counts for every dimension and fact table
  - Reconciliation query results (staging vs DW totals)
  - Total execution time

Configuration via environment variables (with defaults):
  PGHOST       = localhost
  PGPORT       = 5432
  PGDATABASE   = building_energy_dw
  PGUSER       = postgres
  PGPASSWORD   = postgres

Usage:
    python 04_load_batch_dw.py

Requirements:
    pip install psycopg2-binary
"""
from __future__ import annotations

import os
import sys
import time

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: 'psycopg2-binary' is required.  pip install psycopg2-binary")
    sys.exit(1)

# ---------------------------------------------------------------------------
# DB config from environment
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host":     os.environ.get("PGHOST",     "localhost"),
    "port":     int(os.environ.get("PGPORT", "5432")),
    "dbname":   os.environ.get("PGDATABASE", "building_energy_dw"),
    "user":     os.environ.get("PGUSER",     "postgres"),
    "password": os.environ.get("PGPASSWORD", "postgres"),
}

# ---------------------------------------------------------------------------
# Tables to report on after ETL
# ---------------------------------------------------------------------------
DIMENSION_TABLES = [
    "dim_property",
    "dim_date",
    "dim_borough",
    "dim_property_type",
    "dim_building_size",
    "dim_energy_performance",
]

FACT_TABLES = [
    "fact_building_energy",
]

# Optional mart views / tables
MART_TABLES = [
    "building_performance_analytics_mart",
]

# Reconciliation: compare staging totals vs fact table totals
RECONCILIATION_SQL = """
SELECT
    'staging' AS source,
    COUNT(*)                              AS row_count,
    ROUND(SUM("GHGEmissions")::NUMERIC, 2)   AS total_ghg,
    ROUND(AVG("SiteEUI")::NUMERIC, 4)        AS avg_site_eui,
    ROUND(SUM("GrossFloorArea")::NUMERIC, 2) AS total_gfa
FROM staging_building_energy

UNION ALL

SELECT
    'fact_building_energy' AS source,
    COUNT(*)                               AS row_count,
    ROUND(SUM(ghg_emissions)::NUMERIC, 2)  AS total_ghg,
    ROUND(AVG(site_eui)::NUMERIC, 4)       AS avg_site_eui,
    ROUND(SUM(gross_floor_area)::NUMERIC, 2) AS total_gfa
FROM fact_building_energy;
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as exc:
        print(f"ERROR: Cannot connect to PostgreSQL: {exc}")
        print(
            "Ensure PostgreSQL is running and env vars are set:\n"
            "  PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD\n"
            "Or start with:  docker-compose up -d postgres"
        )
        sys.exit(1)


def table_row_count(cursor, table_name: str) -> int | str:
    """Return row count for a table, or 'N/A' if it doesn't exist."""
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        return cursor.fetchone()[0]
    except psycopg2.errors.UndefinedTable:
        return "N/A (table does not exist)"
    except Exception as exc:
        return f"ERROR: {exc}"


def run_reconciliation(cursor) -> list[dict]:
    """Run the reconciliation query and return rows as list of dicts."""
    try:
        cursor.execute(RECONCILIATION_SQL)
        cols = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    except Exception as exc:
        print(f"  WARNING: Reconciliation query failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("NYC Building Energy DW — Full Batch ETL")
    print("=" * 60)
    print(f"DB: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}"
          f"/{DB_CONFIG['dbname']}")
    print()

    conn = get_connection()
    conn.autocommit = False   # fn_run_full_etl() manages its own transactions
    cursor = conn.cursor()

    wall_start = time.perf_counter()

    # ------------------------------------------------------------------
    # 1. Call fn_run_full_etl()
    # ------------------------------------------------------------------
    print("[1] Calling fn_run_full_etl() …")
    etl_start = time.perf_counter()
    try:
        # The function may return a status text or nothing.
        cursor.execute("SELECT fn_run_full_etl();")
        result = cursor.fetchone()
        conn.commit()
        etl_elapsed = time.perf_counter() - etl_start
        status = result[0] if result else "OK"
        print(f"    fn_run_full_etl() returned: {status}")
        print(f"    ETL function elapsed: {etl_elapsed:.2f}s")
    except psycopg2.errors.UndefinedFunction:
        conn.rollback()
        print(
            "    WARNING: fn_run_full_etl() not found in the database.\n"
            "    Make sure the SQL scripts in sql/batch_dw/ have been executed first.\n"
            "    You can run them manually or via Docker init scripts."
        )
    except Exception as exc:
        conn.rollback()
        print(f"    ERROR during fn_run_full_etl(): {exc}")
        raise

    # ------------------------------------------------------------------
    # 2. Row counts — dimension tables
    # ------------------------------------------------------------------
    print("\n[2] Dimension table row counts:")
    for tbl in DIMENSION_TABLES:
        count = table_row_count(cursor, tbl)
        print(f"    {tbl:<35} {count:>12,}" if isinstance(count, int)
              else f"    {tbl:<35} {count}")

    # ------------------------------------------------------------------
    # 3. Row counts — fact tables
    # ------------------------------------------------------------------
    print("\n[3] Fact table row counts:")
    for tbl in FACT_TABLES:
        count = table_row_count(cursor, tbl)
        print(f"    {tbl:<35} {count:>12,}" if isinstance(count, int)
              else f"    {tbl:<35} {count}")

    # ------------------------------------------------------------------
    # 4. Mart / analytical views
    # ------------------------------------------------------------------
    print("\n[4] Mart/analytical view row counts:")
    for tbl in MART_TABLES:
        count = table_row_count(cursor, tbl)
        print(f"    {tbl:<35} {count:>12,}" if isinstance(count, int)
              else f"    {tbl:<35} {count}")

    # ------------------------------------------------------------------
    # 5. Reconciliation
    # ------------------------------------------------------------------
    print("\n[5] Reconciliation (staging vs fact):")
    recon_rows = run_reconciliation(cursor)
    if recon_rows:
        # Header
        header = f"{'Source':<30} {'Rows':>10} {'Total GHG':>15} {'Avg SiteEUI':>14} {'Total GFA':>18}"
        print(f"    {header}")
        print("    " + "-" * len(header))
        for row in recon_rows:
            line = (
                f"    {str(row.get('source','')):<30}"
                f" {str(row.get('row_count','')):>10}"
                f" {str(row.get('total_ghg','')):>15}"
                f" {str(row.get('avg_site_eui','')):>14}"
                f" {str(row.get('total_gfa','')):>18}"
            )
            print(line)

    # ------------------------------------------------------------------
    # 6. Total time
    # ------------------------------------------------------------------
    wall_elapsed = time.perf_counter() - wall_start
    print(f"\n{'=' * 60}")
    print(f"Total execution time: {wall_elapsed:.2f}s ({wall_elapsed / 60:.1f} min)")
    print("✓ Batch ETL complete.")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
