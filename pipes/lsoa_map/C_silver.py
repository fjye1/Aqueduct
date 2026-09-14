from pathlib import Path

import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.transformations.filters import london_lsoa_filter

PIPE_NAME = "lsoa_map"
PROJECT_ID = "roomreview-487913"
LAYER = "silver_layer"
OUTPUT_NAME = "extraction"
TABLE_NAME = "lsoa_boundaries"
DRY_RUN = True


def run_pipeline(project_root: Path):
    raw_path = project_root / "data" / "B_bronze" / PIPE_NAME / f"ingestion_{TABLE_NAME}.csv"

    if not raw_path.exists():
        print(f"  [SKIP] File not found: {raw_path}")
        return

    df = pd.read_csv(raw_path)
    df = london_lsoa_filter(df, lsoa_column="lsoa_code")

    out_path = project_root / "data" / "C_silver" / PIPE_NAME / f"{OUTPUT_NAME}_{TABLE_NAME}.csv"
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
