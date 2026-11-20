"""
03_load_staging.py
==================
Loads the curated NYC Building Energy CSV into the PostgreSQL staging table
(staging_building_energy) using a fast COPY-based bulk load.

Configuration via environment variables (with defaults):
  PGHOST       = localhost
  PGPORT       = 5432
  PGDATABASE   = building_energy_dw
  PGUSER       = postgres
  PGPASSWORD   = postgres

Usage:
    python 03_load_staging.py [--input PATH_TO_CSV]

Requirements:
    pip install psycopg2-binary pandas
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from datetime import datetime

try:
    import pandas as pd
except ImportError:
    print("ERROR: 'pandas' is required.  pip install pandas")
    sys.exit(1)

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: 'psycopg2-binary' is required.  pip install psycopg2-binary")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_INPUT = os.path.join(PROJECT_ROOT, "data", "curated", "nyc_building_energy_curated.csv")

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

STAGING_TABLE = "staging_building_energy"


# ---------------------------------------------------------------------------
# Helper: get connection
# ---------------------------------------------------------------------------

def get_connection():
    """Create and return a psycopg2 connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as exc:
        print(f"ERROR: Cannot connect to PostgreSQL: {exc}")
        print(
            "Make sure PostgreSQL is running and env vars are set:\n"
            "  PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD\n"
            "Or start the stack with:  docker-compose up -d postgres"
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Helper: ensure staging table exists (DDL fallback)
# ---------------------------------------------------------------------------
CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {STAGING_TABLE} (
    stg_id              SERIAL PRIMARY KEY,
    "PropertyID"        TEXT,
    "PropertyName"      TEXT,
    "Borough"           TEXT,
    "BoroughGroup"      TEXT,
    "PrimaryPropertyType" TEXT,
    "PropertyTypeGroup" TEXT,
    "GrossFloorArea"    DOUBLE PRECISION,
    "SiteEUI"           DOUBLE PRECISION,
    "SourceEUI"         DOUBLE PRECISION,
    "GHGEmissions"      DOUBLE PRECISION,
    "WaterUse"          DOUBLE PRECISION,
    "EnergyStarScore"   DOUBLE PRECISION,
    "ReportingYear"     INTEGER,
    "BBL"               TEXT,
    "BIN"               TEXT,
    "BuildingSizeBand"  TEXT,
    "EnergyIntensityBand" TEXT,
    "GHGIntensity"      DOUBLE PRECISION,
    "WaterIntensity"    DOUBLE PRECISION,
    "EnergyPerformanceBand" TEXT,
    "IsHighEnergyBuilding" INTEGER,
    "IsHighGHGBuilding" INTEGER,
    loaded_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def ensure_staging_table(cursor):
    """Create the staging table if it does not already exist."""
    cursor.execute(CREATE_TABLE_SQL)
    print(f"  Staging table '{STAGING_TABLE}' ready.")


# ---------------------------------------------------------------------------
# Main load logic
# ---------------------------------------------------------------------------

def load_staging(csv_path: str):
    """Truncate the staging table and bulk-load from CSV via COPY."""

    # --- Read CSV ---
    print(f"Reading curated CSV: {csv_path} …")
    df = pd.read_csv(csv_path, low_memory=False)
    csv_rows = len(df)
    print(f"  CSV rows: {csv_rows:,}  |  columns: {list(df.columns)}")

    # --- Connect ---
    print(f"\nConnecting to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']} / "
          f"{DB_CONFIG['dbname']} …")
    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor()
    print("  Connected.")

    try:
        # --- Ensure table ---
        ensure_staging_table(cursor)

        # --- Truncate ---
        print(f"\nTruncating {STAGING_TABLE} …")
        cursor.execute(f"TRUNCATE TABLE {STAGING_TABLE} RESTART IDENTITY;")
        print("  Table truncated.")

        # --- Prepare in-memory CSV buffer for COPY ---
        # We only COPY columns that exist in the staging table (skip extra cols)
        # Build list of columns that the table knows about
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s ORDER BY ordinal_position;",
            (STAGING_TABLE,)
        )
        db_cols = [r[0] for r in cursor.fetchall() if r[0] not in ("stg_id", "loaded_at")]

        # Keep only DataFrame columns that exist in the DB (case-sensitive match)
        copy_cols = [c for c in db_cols if c in df.columns]
        missing_in_df = [c for c in db_cols if c not in df.columns]
        extra_in_df = [c for c in df.columns if c not in db_cols]

        if missing_in_df:
            print(f"  NOTE: Columns in DB but not in CSV (will load as NULL): {missing_in_df}")
        if extra_in_df:
            print(f"  NOTE: Extra CSV columns not in staging table (skipped): {extra_in_df}")

        # Build a copy of the dataframe with only the needed columns
        df_copy = df[copy_cols].copy()

        # Serialise to CSV in memory
        print(f"\nLoading {csv_rows:,} rows via COPY ({len(copy_cols)} columns) …")
        t_start = datetime.now()

        buffer = io.StringIO()
        df_copy.to_csv(buffer, index=False, header=True, na_rep="\\N")
        buffer.seek(0)

        # PostgreSQL COPY with CSV format and NULL represented as \N
        col_list = ", ".join(f'"{c}"' for c in copy_cols)
        copy_sql = (
            f"COPY {STAGING_TABLE} ({col_list}) "
            f"FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '\\N');"
        )
        cursor.copy_expert(copy_sql, buffer)

        t_end = datetime.now()
        elapsed = (t_end - t_start).total_seconds()

        # --- Commit ---
        conn.commit()
        print(f"  COPY complete in {elapsed:.1f}s")

        # --- Validate row count ---
        cursor.execute(f"SELECT COUNT(*) FROM {STAGING_TABLE};")
        db_count = cursor.fetchone()[0]
        print(f"\n{'=' * 50}")
        print(f"Validation:")
        print(f"  Rows in CSV:              {csv_rows:,}")
        print(f"  Rows in {STAGING_TABLE}: {db_count:,}")
        if db_count == csv_rows:
            print("  ✓ Row counts match — load successful!")
        else:
            diff = abs(db_count - csv_rows)
            print(f"  ✗ MISMATCH: difference of {diff:,} rows.  Check ETL logs.")

    except Exception as exc:
        conn.rollback()
        print(f"\nERROR during load: {exc}")
        raise
    finally:
        cursor.close()
        conn.close()
        print("  Database connection closed.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Load curated NYC Building Energy CSV into PostgreSQL staging."
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help=f"Path to curated CSV (default: {DEFAULT_INPUT})",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        print("Run 02_data_curation.py first to generate the curated CSV.")
        sys.exit(1)

    load_staging(args.input)


if __name__ == "__main__":
    main()
