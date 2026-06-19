from datetime import datetime
from pathlib import Path

import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.extraction import column_row_extractor
from utils.filters import london_borough_filter, date_filter
# tables each borough appearing 5 times

# silver_council_tax_bands
# silver_avg_house_price
# silver_housing_stock
# silver_housing_stock_additions
# silver_affordable_housing



# ──pipes/housing/C_silver Config ───────────────────────────────────────────────────────────────────
PIPELINES = [

    {
        "sources": [
            {
                "file": "ingestion_dwelling_stock_local_2021.csv",
                "year_name": "2021"
            },
            {
                "file": "ingestion_dwelling_stock_local_2022.csv",
                "year_name": "2022"
            },
            {
                "file": "ingestion_dwelling_stock_local_2023.csv",
                "year_name": "2023"
            },
            {
                "file": "ingestion_dwelling_stock_local_2024.csv",
                "year_name": "2024"
            },
            {
                "file": "ingestion_dwelling_stock_local_2025.csv",
                "year_name": "2025"
            }
        ],
        "table_name": "housing_stock",
        "extraction_functions": [london_borough_filter],
        "data_row_start": 6,
        "data_row_end": 336,
        "columns": [
            {"col": 1, "name": "ons_code", "type": "STRING"},
            {"col": 2, "name": "Area", "type": "STRING"},
            {"col": 3, "name": "local_authority", "type": "FLOAT"},
            {"col": 4, "name": "private_registered_provider", "type": "FLOAT"},
            {"col": 5, "name": "Other public sector ", "type": "FLOAT"},
            {"col": 6, "name": "private_sector", "type": "FLOAT"},
            {"col": 7, "name": "total_dwellings", "type": "FLOAT"},
            {"col": 8, "name": "_source_file", "type": "STRING"},
            {"col": 9, "name": "_sheet_name", "type": "STRING"},
            {"col": 10, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 11, "name": "_row_number", "type": "INTEGER"},
        ]
    }
]

PIPE_NAME = "housing"
PROJECT_ID = "roomreview-487913"
LAYER = "silver_layer"
OUTPUT_NAME = "extraction"


def run_pipeline(project_root: Path):
    folder = project_root / "data" / "B_bronze" / PIPE_NAME

    for config in PIPELINES:
        table_name = config["table_name"]
        processed_dfs = []

        print(f"\n--- Processing Pipeline: {table_name} ---")

        for src in config["sources"]:
            raw_file = folder / src["file"]
            year_name = src["year_name"]

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
                    year_name = year_name
                )
                processed_dfs.append(df)

            except Exception as e:
                print(f"  [ERROR] Failed to process {raw_file.name}: {e}")
                continue

        # Concat and upload per pipeline table
        if processed_dfs:
            final_df = pd.concat(processed_dfs, ignore_index=True)
            min_year = int(final_df["year_name"].min())
            max_year = int(final_df["year_name"].max())


            out_path = project_root / "data" / "C_silver" / PIPE_NAME / f"{OUTPUT_NAME}_{table_name}{min_year}_{max_year}.csv"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            final_df.to_csv(out_path, index=False)
            print(f"  Saved to {out_path}")

            print(f"  Uploading to BigQuery table: {PIPE_NAME}_{table_name}...")
            load_into_bigquery(
                project_id=PROJECT_ID,
                layer=LAYER,
                table_name=f"{PIPE_NAME}_{table_name}",
                df=final_df,
                dry_run=True  # Set to False when ready to upload
            )
        else:
            print(f"  [WARN] No data processed for pipeline: {table_name}")
