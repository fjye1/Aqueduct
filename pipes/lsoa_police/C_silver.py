from pathlib import Path

import json
import numpy as np
import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.transformations.filters import get_lsoa_from_lat_lon, process_crime_df

# ──pipes/lsoa_police/C_silver Config ───────────────────────────────────────
# Raw crime JSON is fetched and cached by the "police" pipe (borough grain).
# This pipe re-reads that cache and spatially joins each crime to its LSOA
# using the lat/lon the police API already returns per record.
POLICE_RAW_PIPE_NAME = "police"

PIPE_NAME = "lsoa_police"
PROJECT_ID = "roomreview-487913"
LAYER = "silver_layer"
OUTPUT_NAME = "extraction"
table_name = "crimes"
DRY_RUN = True  # Select False when ready to upload


def run_pipeline(project_root: Path):
    print("=== STARTING LSOA CRIME EXTRACTION ===")
    process_lsoa_crimes(project_root)

    print("\n=== PIPELINE RUN COMPLETE ===")


def process_lsoa_crimes(project_root: Path):
    base_path = project_root / "data" / "A_raw" / POLICE_RAW_PIPE_NAME / "police_crimes"

    monthly_frames = []
    for json_file in base_path.glob("year=*/month=*/*.json"):
        parts = json_file.relative_to(base_path).parts
        year = int(parts[0].split("=")[1])
        month = int(parts[1].split("=")[1])

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not data:
            continue

        df = pd.json_normalize(data)
        df["year"] = year
        df["month"] = month
        monthly_frames.append(df[["year", "month", "category", "location.latitude", "location.longitude"]])

    crimes_df = pd.concat(monthly_frames, ignore_index=True)
    crimes_df = crimes_df.dropna(subset=["location.latitude", "location.longitude"])
    crimes_df["location.latitude"] = crimes_df["location.latitude"].astype(float)
    crimes_df["location.longitude"] = crimes_df["location.longitude"].astype(float)

    # Spatially join each crime to its LSOA using its reported lat/lon
    crimes_df = get_lsoa_from_lat_lon(
        crimes_df, lat_col="location.latitude", lon_col="location.longitude"
    )
    crimes_df = crimes_df.dropna(subset=["lsoa21cd"])

    monthly_counts = (
        crimes_df
        .groupby(["year", "month", "lsoa21cd", "category"])
        .size()
        .reset_index(name="count")
    )

    df = (
        monthly_counts
        .groupby(["year", "lsoa21cd", "category"], as_index=False)
        .agg(
            total_count=("count", "sum"),
            months_present=("month", "nunique")
        )
    )
    # Safe division: replaces 0 months with NaN to avoid errors or infinite values
    df["annualised_rate"] = (
                                    df["total_count"] / df["months_present"].replace(0, np.nan)
                            ) * 12

    final_df = process_crime_df(df)
    out_path = project_root / "data" / "C_silver" / PIPE_NAME / f"{OUTPUT_NAME}_{table_name}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(out_path, index=False)

    if not final_df.empty:
        print(f"  Uploading to BigQuery table: {PIPE_NAME}_{table_name}...")
        load_into_bigquery(
            project_id=PROJECT_ID,
            layer=LAYER,
            table_name=f"{PIPE_NAME}_{table_name}",
            df=final_df,
            dry_run=DRY_RUN
        )
    else:
        print(f"  [WARN] No data processed for pipeline: {table_name}")
