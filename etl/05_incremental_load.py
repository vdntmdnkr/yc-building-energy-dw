"""
05_incremental_load.py
======================
Demonstrates an incremental load: calls fn_incremental_load(year) in
PostgreSQL and prints before/after row counts for the affected tables.

Usage:
    python 05_incremental_load.py [--year 2023]

If --year is omitted, the script queries the staging table for the latest
(maximum) reporting year and uses that.

Configuration via environment variables:
  PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD

Requirements:
    pip install psycopg2-binary
"""
from __future__ import annotations

import argparse
import os
import sys
import time

try:
    import psycopg2
except ImportError:
    print("ERROR: 'psycopg2-binary' is required.  pip install psycopg2-binary")
    sys.exit(1)

# ---------------------------------------------------------------------------
# DB config
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host":     os.environ.get("PGHOST",     "localhost"),
    "port":     int(os.environ.get("PGPORT", "5432")),
    "dbname":   os.environ.get("PGDATABASE", "building_energy_dw"),
    "user":     os.environ.get("PGUSER",     "postgres"),
    "password": os.environ.get("PGPASSWORD", "postgres"),
}

# Tables affected by an incremental load
AFFECTED_TABLES = [
    "staging_building_energy",
    "fact_building_energy",
    "dim_property",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as exc:
        print(f"ERROR: Cannot connect to PostgreSQL: {exc}")
        print(
            "Ensure PostgreSQL is running and env vars are set:\n"
            "  PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD"
        )
        sys.exit(1)


def count_rows(cursor, table: str, where: str = "") -> int | str:
    sql = f"SELECT COUNT(*) FROM {table}" + (f" WHERE {where}" if where else "") + ";"
    try:
        cursor.execute(sql)
        return cursor.fetchone()[0]
    except psycopg2.errors.UndefinedTable:
        return "N/A"
    except Exception as exc:
        return f"ERROR: {exc}"


def get_latest_year(cursor) -> int | None:
    """Return the maximum reporting year from the staging table."""
    try:
        cursor.execute(
            'SELECT MAX("ReportingYear") FROM staging_building_energy;'
        )
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Incremental load: call fn_incremental_load(year) in PostgreSQL."
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Reporting year to load incrementally. Defaults to the latest year in staging.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("NYC Building Energy DW — Incremental Load")
    print("=" * 60)

    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    # Determine target year
    year = args.year
    if year is None:
        year = get_latest_year(cursor)
        if year is None:
            print(
                "ERROR: Could not determine latest year from staging_building_energy.\n"
                "       Run 03_load_staging.py first, or pass --year explicitly."
            )
            cursor.close()
            conn.close()
            sys.exit(1)
        print(f"  No --year supplied.  Using latest year from staging: {year}")
    else:
        print(f"  Target year: {year}")

    # --- Before counts ---
    print("\n[1] Row counts BEFORE incremental load:")
    before_counts: dict[str, int | str] = {}
    for tbl in AFFECTED_TABLES:
        cnt = count_rows(cursor, tbl)
        before_counts[tbl] = cnt
        print(f"    {tbl:<40} {cnt:>12,}" if isinstance(cnt, int) else f"    {tbl:<40} {cnt}")

    # --- Call incremental function ---
    print(f"\n[2] Calling fn_incremental_load({year}) …")
    t_start = time.perf_counter()
    try:
        cursor.execute("SELECT fn_incremental_load(%s);", (year,))
        result = cursor.fetchone()
        conn.commit()
        elapsed = time.perf_counter() - t_start
        status = result[0] if result else "OK"
        print(f"    Result: {status}  |  elapsed: {elapsed:.2f}s")
    except psycopg2.errors.UndefinedFunction:
        conn.rollback()
        print(
            "    WARNING: fn_incremental_load() not found in the database.\n"
            "    Make sure the SQL scripts have been executed (see sql/batch_dw/)."
        )
        cursor.close()
        conn.close()
        sys.exit(1)
    except Exception as exc:
        conn.rollback()
        print(f"    ERROR: {exc}")
        cursor.close()
        conn.close()
        raise

    # --- After counts ---
    print(f"\n[3] Row counts AFTER incremental load (year={year}):")
    for tbl in AFFECTED_TABLES:
        after = count_rows(cursor, tbl)
        before = before_counts[tbl]
        if isinstance(after, int) and isinstance(before, int):
            diff = after - before
            diff_str = f"(+{diff:,})" if diff >= 0 else f"({diff:,})"
            print(f"    {tbl:<40} {after:>12,}  {diff_str}")
        else:
            print(f"    {tbl:<40} {after}")

    # --- Year-specific counts ---
    print(f"\n[4] Rows for year={year} in affected tables:")
    for tbl in AFFECTED_TABLES:
        # Determine year column name
        year_col_candidates = ['"ReportingYear"', "reporting_year", "year_id"]
        for yc in year_col_candidates:
            cnt = count_rows(cursor, tbl, f"{yc} = {year}")
            if not isinstance(cnt, str) or "ERROR" not in cnt:
                print(f"    {tbl:<40} {cnt:>12,}" if isinstance(cnt, int)
                      else f"    {tbl:<40} {cnt}")
                break

    print(f"\n✓ Incremental load for year {year} complete.")
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
