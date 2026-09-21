from pathlib import Path

import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery

PIPE_NAME = "postcodes"
PROJECT_ID = "roomreview-487913"
LAYER = "bronze_layer"
OUTPUT_NAME = "ingestion"
TABLE_NAME = "postcode_centroids"
DRY_RUN = True  # Set to False when you want to upload

RAW_FILE = "NSPL_Online_latest_Centroids_918116276238402986.csv"

# The raw NSPL export already has real column headers (unlike the headerless
# spreadsheet exports batch_ingestion_csv/excel are built for), so this
# reads it directly rather than forcing it through the col_N + column_row_extractor
# convention used elsewhere. At 2.7M rows nationally, only pulling the
# columns actually needed keeps this from ballooning further - no row
# filtering yet, that happens in C_silver.py (live + London only).
SOURCE_COLUMNS = {
    "PCDS": "pcds",
    "DOINTR": "dointr",
    "DOTERM": "doterm",
    "OA21CD": "oa21cd",
    "LSOA21CD": "lsoa21cd",
    "MSOA21CD": "msoa21cd",
    "LAD25CD": "lad25cd",
    "EAST1M": "easting",
    "NORTH1M": "northing",
    "LAT": "lat",
    "LONG": "long",
}


def run_pipeline(project_root: Path):
    raw_path = project_root / "data" / "A_raw" / PIPE_NAME / RAW_FILE

    if not raw_path.exists():
        print(f"  [SKIP] File not found: {raw_path}")
        return

    print(f"  Reading {raw_path.name} (columns: {list(SOURCE_COLUMNS)})")
    df = pd.read_csv(raw_path, usecols=list(SOURCE_COLUMNS), dtype=str)
    df = df.rename(columns=SOURCE_COLUMNS)

    out_path = project_root / "data" / "B_bronze" / PIPE_NAME / f"{OUTPUT_NAME}_{TABLE_NAME}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"  Saved {len(df)} rows to {out_path}")

    target_table = f"{PIPE_NAME}_{TABLE_NAME}"
    print(f"  Uploading to BigQuery table: {target_table}...")
    load_into_bigquery(
        project_id=PROJECT_ID,
        layer=LAYER,
        table_name=target_table,
        df=df,
        dry_run=DRY_RUN,
    )
