"""
06_export_mart.py
=================
Exports the analytical mart view (building_performance_analytics_mart)
from PostgreSQL to a CSV file for use in notebooks and ML scripts.

Usage:
    python 06_export_mart.py [--output PATH] [--view VIEW_NAME]

Configuration via environment variables:
  PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD

Requirements:
    pip install psycopg2-binary pandas
"""
from __future__ import annotations

import argparse
import os
import sys
import time

try:
    import pandas as pd
except ImportError:
    print("ERROR: 'pandas' is required.  pip install pandas")
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("ERROR: 'psycopg2-binary' is required.  pip install psycopg2-binary")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "data", "mart", "building_performance_mart.csv")
DEFAULT_VIEW = "building_performance_analytics_mart"

DB_CONFIG = {
    "host":     os.environ.get("PGHOST",     "localhost"),
    "port":     int(os.environ.get("PGPORT", "5432")),
    "dbname":   os.environ.get("PGDATABASE", "building_energy_dw"),
    "user":     os.environ.get("PGUSER",     "postgres"),
    "password": os.environ.get("PGPASSWORD", "postgres"),
}


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
            "  PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD\n"
            "Or start with:  docker-compose up -d postgres"
        )
        sys.exit(1)


def view_exists(cursor, view_name: str) -> bool:
    """Check whether a table or view named view_name exists in the public schema."""
    cursor.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = %s;",
        (view_name,)
    )
    return cursor.fetchone() is not None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export the analytical mart from PostgreSQL to CSV."
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--view",
        default=DEFAULT_VIEW,
        help=f"Name of the mart view/table in PostgreSQL (default: {DEFAULT_VIEW})",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("NYC Building Energy DW — Export Mart")
    print("=" * 60)
    print(f"Source view:  {args.view}")
    print(f"Output file:  {args.output}")
    print()

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    # Connect
    print(f"Connecting to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}"
          f"/{DB_CONFIG['dbname']} …")
    conn = get_connection()
    cursor = conn.cursor()
    print("  Connected.")

    # Check view exists
    if not view_exists(cursor, args.view):
        print(
            f"\nWARNING: View/table '{args.view}' not found in public schema.\n"
            "  Options:\n"
            "  1. Run 04_load_batch_dw.py to populate the DW first.\n"
            "  2. Check the view name with:  \\dv in psql\n"
            "  3. Try --view another_mart_name"
        )
        # Attempt to list available mart-like objects as a hint
        try:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name ILIKE '%mart%';"
            )
            candidates = [r[0] for r in cursor.fetchall()]
            if candidates:
                print(f"  Available mart-like tables/views: {candidates}")
        except Exception:
            pass
        cursor.close()
        conn.close()
        sys.exit(1)

    # --- SELECT * ---
    print(f"\nQuerying {args.view} …")
    t_start = time.perf_counter()

    try:
        # Use pandas read_sql for convenience (handles types & NULLs well)
        df = pd.read_sql(f'SELECT * FROM "{args.view}";', conn)
    except Exception as exc:
        print(f"ERROR: Query failed: {exc}")
        cursor.close()
        conn.close()
        sys.exit(1)

    elapsed = time.perf_counter() - t_start
    print(f"  Query returned {len(df):,} rows in {elapsed:.2f}s")

    # --- Save CSV ---
    print(f"\nSaving to {args.output} …")
    df.to_csv(args.output, index=False)
    print(f"  Saved {len(df):,} rows × {len(df.columns)} columns")

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"Row count:  {len(df):,}")
    print(f"Columns ({len(df.columns)}):")
    for i, col in enumerate(df.columns, 1):
        dtype = str(df[col].dtype)
        null_count = df[col].isna().sum()
        print(f"  {i:3d}. {col:<45} {dtype:<12} nulls={null_count:,}")

    print(f"\n✓ Mart exported successfully → {args.output}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
