from pathlib import Path

import geopandas as gpd
import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.operational.audit import build_audit_columns

PIPE_NAME = "lsoa_map"
PROJECT_ID = "roomreview-487913"
LAYER = "bronze_layer"
OUTPUT_NAME = "ingestion"
TABLE_NAME = "lsoa_boundaries"
DRY_RUN = True  # Set to False when you want to upload

# The raw shapefiles carry the geometry needed to draw each LSOA - that stays
# in data/A_raw/lsoa_map and is read directly by r_lsoa_map.R at render time
# (same pattern as infrastructure_map reading london_boroughs.shp straight
# from A_raw). This bronze step only pulls out the attribute table, so there
# is a single combined lsoa -> borough lookup instead of 33 separate shapefiles.
ATTRIBUTE_COLUMNS = {
    "lsoa21cd": "lsoa_code",
    "lsoa21nm": "lsoa_name",
    "msoa21cd": "msoa_code",
    "msoa21nm": "msoa_name",
    "lad22cd": "borough_code",
    "lad22nm": "borough_name",
}


def run_pipeline(project_root: Path):
    base_path = project_root / "data" / "A_raw" / PIPE_NAME
    shapefiles = sorted(base_path.glob("*.shp"))

    if not shapefiles:
        print(f"  [WARN] No shapefiles found under {base_path}")
        return

    frames = []
    for shp_path in shapefiles:
        print(f"  Reading {shp_path.name}")
        gdf = gpd.read_file(shp_path)
        df = pd.DataFrame(gdf.drop(columns="geometry"))
        df = df.rename(columns=ATTRIBUTE_COLUMNS)[list(ATTRIBUTE_COLUMNS.values())]
        df = build_audit_columns(df, source_file=shp_path.name)
        frames.append(df)

    final_df = pd.concat(frames, ignore_index=True)

    out_path = project_root / "data" / "B_bronze" / PIPE_NAME / f"{OUTPUT_NAME}_{TABLE_NAME}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(out_path, index=False)
    print(f"  Saved {len(final_df)} rows to {out_path}")

    target_table = f"{PIPE_NAME}_{TABLE_NAME}"
    print(f"  Uploading to BigQuery table: {target_table}...")
    load_into_bigquery(
        project_id=PROJECT_ID,
        layer=LAYER,
        table_name=target_table,
        df=final_df,
        dry_run=DRY_RUN,
    )
