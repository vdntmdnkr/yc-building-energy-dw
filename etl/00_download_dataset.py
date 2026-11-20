"""
00_download_dataset.py
======================
Downloads the NYC Building Energy Benchmarking dataset (Local Law 84)
from the NYC Open Data Socrata API and saves it locally.

Usage:
    python 00_download_dataset.py [--token APP_TOKEN] [--year 2022]

Requirements:
    pip install requests
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------
try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is not installed.")
    print("Install it with:  pip install requests")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("ERROR: 'pandas' library is not installed.")
    print("Install it with:  pip install pandas")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://data.cityofnewyork.us/resource/5zyy-y8am.csv"
PAGE_LIMIT = 50_000          # rows per API call
DEFAULT_FILTER_YEAR = 2022   # reportingyear >= this value

# Output paths (relative to this script's directory)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
OUTPUT_CSV = os.path.join(RAW_DATA_DIR, "nyc_building_energy.csv")
METADATA_JSON = os.path.join(RAW_DATA_DIR, "download_metadata.json")


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def build_params(offset: int, limit: int, min_year: int, app_token: str | None) -> dict:
    """Build the query-string parameters for a single page request."""
    params = {
        "$limit": limit,
        "$offset": offset,
        "$where": f"reportingyear >= {min_year}",
        "$order": "reportingyear ASC",   # deterministic ordering
    }
    if app_token:
        params["$$app_token"] = app_token
    return params


def download_all_pages(base_url: str, app_token: str | None, min_year: int) -> list[bytes]:
    """
    Paginate through the Socrata CSV endpoint and collect all pages as raw bytes.
    Returns a list of byte strings, one per page (including the header row on page 0).
    """
    pages: list[bytes] = []
    offset = 0
    page_num = 0

    session = requests.Session()
    # Socrata recommends setting a custom User-Agent
    session.headers.update({"User-Agent": "NYC-Energy-ETL/1.0"})

    print(f"Downloading from: {base_url}")
    print(f"Filter: reportingyear >= {min_year}  |  page size: {PAGE_LIMIT:,} rows")
    print("-" * 60)

    while True:
        params = build_params(offset, PAGE_LIMIT, min_year, app_token)
        print(f"  Page {page_num + 1}: offset={offset:,} ...", end=" ", flush=True)

        try:
            response = session.get(base_url, params=params, timeout=120)
        except requests.exceptions.ConnectionError as exc:
            print(f"\nERROR: Connection failed — {exc}")
            print("Check your internet connection and try again.")
            sys.exit(1)
        except requests.exceptions.Timeout:
            print("\nERROR: Request timed out after 120 s.  Try again later.")
            sys.exit(1)

        # Handle HTTP-level errors
        if response.status_code == 401:
            print(
                "\nERROR 401 Unauthorized — the endpoint requires an app token.\n"
                "Register at https://data.cityofnewyork.us/profile/app_tokens\n"
                "then run:  python 00_download_dataset.py --token YOUR_TOKEN"
            )
            sys.exit(1)
        elif response.status_code == 403:
            print(
                "\nERROR 403 Forbidden — your app token may be invalid or throttled.\n"
                "Check https://data.cityofnewyork.us/profile/app_tokens"
            )
            sys.exit(1)
        elif response.status_code != 200:
            print(f"\nERROR: HTTP {response.status_code}\n{response.text[:500]}")
            sys.exit(1)

        content = response.content

        # Strip the CSV header from subsequent pages so we don't duplicate it
        if page_num == 0:
            pages.append(content)
        else:
            # Drop the first line (header) from continuation pages
            first_newline = content.find(b"\n")
            if first_newline != -1:
                pages.append(content[first_newline + 1:])
            else:
                pages.append(content)

        # Count rows in this page (subtract 1 for header on first page)
        row_count = content.count(b"\n")
        if page_num == 0:
            row_count -= 1   # exclude header

        print(f"got {row_count:,} rows")

        if row_count < PAGE_LIMIT:
            # Last page — fewer rows than the page limit means no more data
            break

        offset += PAGE_LIMIT
        page_num += 1

    return pages


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Download NYC Building Energy dataset from NYC Open Data"
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("NYC_OPENDATA_APP_TOKEN", ""),
        help="Socrata app token (optional but recommended to avoid rate limits). "
             "Also reads NYC_OPENDATA_APP_TOKEN env var.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_FILTER_YEAR,
        help=f"Filter: only download rows where reportingyear >= YEAR (default: {DEFAULT_FILTER_YEAR})",
    )
    args = parser.parse_args()

    app_token = args.token if args.token else None
    if not app_token:
        print(
            "NOTE: No app token supplied.  Requests will be rate-limited (throttled).\n"
            "      Register at https://data.cityofnewyork.us/profile/app_tokens\n"
            "      and pass --token YOUR_TOKEN  (or set NYC_OPENDATA_APP_TOKEN env var).\n"
        )

    # Ensure output directories exist
    os.makedirs(RAW_DATA_DIR, exist_ok=True)

    # --- Download ---
    download_start = datetime.now(timezone.utc)
    pages = download_all_pages(BASE_URL, app_token, args.year)
    download_end = datetime.now(timezone.utc)

    print("-" * 60)
    print("Concatenating pages and parsing CSV …")

    # Combine all pages into one CSV blob and parse with pandas
    combined_bytes = b"".join(pages)
    import io
    df = pd.read_csv(io.BytesIO(combined_bytes), low_memory=False)

    total_rows = len(df)
    total_cols = len(df.columns)
    print(f"Download complete: {total_rows:,} rows × {total_cols} columns")

    # --- Save CSV ---
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved raw CSV → {OUTPUT_CSV}")

    # --- Save metadata ---
    metadata = {
        "download_timestamp_utc": download_start.isoformat(),
        "download_completed_utc": download_end.isoformat(),
        "duration_seconds": (download_end - download_start).total_seconds(),
        "source_url": BASE_URL,
        "filter_year_gte": args.year,
        "page_size": PAGE_LIMIT,
        "pages_fetched": len(pages),
        "row_count": total_rows,
        "column_count": total_cols,
        "columns": df.columns.tolist(),
        "output_file": OUTPUT_CSV,
        "app_token_used": bool(app_token),
    }

    with open(METADATA_JSON, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata  → {METADATA_JSON}")
    print("-" * 60)
    print("Summary:")
    print(f"  Rows:    {total_rows:,}")
    print(f"  Columns: {total_cols}")
    print(f"  Columns: {df.columns.tolist()}")


if __name__ == "__main__":
    main()
