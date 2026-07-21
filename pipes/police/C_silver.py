import json
from pathlib import Path

import numpy as np
import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.transformations.filters import process_crime_df
from utils.transformations.filters import year_filter, london_borough_filter
from utils.io.extraction import column_row_extractor
# ──pipes/police/C_silver Config ───────────────────────────────────────────────────────────────────
PIPELINES = [
    {
        "sources": [
            {
                "file": "ingestion_population_2011.csv",

            },

        ],
        "table_name": "population",
        "extraction_functions": [year_filter, london_borough_filter],
        "data_row_start": 2,
        "data_row_end": 1718,
        "columns": [
            {"col": 0, "name": "ons_code", "type": "STRING"},
            {"col": 1, "name": "local_authority", "type": "STRING"},
            {"col": 2, "name": "year", "type": "DATETIME"},
            {"col": 5, "name": "population", "type": "INTERGER"},
            {"col": 10, "name": "_source_file", "type": "STRING"},
            {"col": 11, "name": "_sheet_name", "type": "STRING"},
            {"col": 12, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 13, "name": "_row_number", "type": "INTEGER"},
        ]
    },

]

PIPE_NAME = "police"
PROJECT_ID = "roomreview-487913"
LAYER = "silver_layer"
OUTPUT_NAME = "extraction"
table_name = "crimes"
DRY_RUN = True  # Select False when ready to upload


def run_pipeline(project_root: Path):
    # Step 1: Gather raw assets locally
    print("=== STARTING JSON DATA EXTRACTION ===")
    # process_json(project_root)

    print("=== STARTING CSV DATA EXTRACTION ===")
    process_csv(project_root)



    print("\n=== PIPELINE RUN COMPLETE ===")


def process_json(project_root: Path):
    base_path = project_root / f"data/A_raw/{PIPE_NAME}/police_crimes"
    results = []

    for year_folder in base_path.glob("year=*"):
        year = int(year_folder.name.split("=")[1])

        for month_folder in year_folder.glob("month=*"):
            for json_file in month_folder.glob("*.json"):

                borough = json_file.stem  # "Barking & Dagenham"

                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                df = pd.json_normalize(data)

                counts = df["category"].value_counts()

                month = int(month_folder.name.split("=")[1])

                for category, count in counts.items():
                    results.append({
                        "year": year,
                        "month": month,
                        "borough": borough,
                        "category": category,
                        "count": count
                    })

    monthly_counts = pd.DataFrame(results)

    df = (
        monthly_counts
        .groupby(["year", "borough", "category"], as_index=False)
        .agg(
            total_count=("count", "sum"),
            months_present=("month", "nunique")
        )
    )
    # Safe division: replaces 0 months with NaN to avoid errors or infinite values
    df["annualised_rate"] = (
                                    df["total_count"] / df["months_present"].replace(0,
                                                                                     np.nan)
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

def process_csv(project_root: Path):
    folder = project_root / "data" / "B_bronze" / PIPE_NAME

    for config in PIPELINES:
        table_name = config["table_name"]
        processed_dfs = []

        print(f"\n--- Processing Pipeline: {table_name} ---")

        for src in config["sources"]:
            raw_file = folder / src["file"]

            if not raw_file.exists():
                print(f"  [SKIP] File not found: {raw_file}")
                continue

            print(f"  Processing file: {raw_file.name}")

            raw_filters = config.get("extraction_functions") or [config.get("extraction_function")]
            raw_filters = [f for f in raw_filters if f is not None]

            # Compose multiple filters into one callable if needed
            if len(raw_filters) > 1:
                def combined_filter(df, filters=raw_filters):
                    for f in filters:
                        df = f(df)
                    return df

                function_filter = combined_filter
            elif len(raw_filters) == 1:
                function_filter = raw_filters[0]
            else:
                function_filter = None

            try:
                df = column_row_extractor(
                    file_path=raw_file,
                    data_row_start=config["data_row_start"],
                    data_row_end=config["data_row_end"],
                    columns=config["columns"],
                    output_name=OUTPUT_NAME,
                    pipe_name=PIPE_NAME,
                    function_filter=function_filter,

                )
                processed_dfs.append(df)

            except Exception as e:
                print(f"  [ERROR] Failed to process {raw_file.name}: {e}")
                continue

        # Concat and upload per pipeline table
        if processed_dfs:
            final_df = pd.concat(processed_dfs, ignore_index=True)

            out_path = project_root / "data" / "C_silver" / PIPE_NAME / f"{OUTPUT_NAME}_{table_name}.csv"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            final_df.to_csv(out_path, index=False)
            print(f"  Saved to {out_path}")

            print(f"  Uploading to BigQuery table: {PIPE_NAME}_{table_name}...")
            load_into_bigquery(
                project_id=PROJECT_ID,
                layer=LAYER,
                table_name=f"{PIPE_NAME}_{table_name}",
                df=final_df,
                dry_run=DRY_RUN  # Set to False when ready to upload
            )
        else:
            print(f"  [WARN] No data processed for pipeline: {table_name}")
