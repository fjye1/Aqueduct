from pathlib import Path

import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.extraction import column_row_extractor
from utils.filters import os_to_lat_lon, get_borough_from_lat_lon

PIPELINES = [

    {
        "sources": [
            {
                "file": "ingestion_bus_stop_data_2025.csv"
            },

        ],
        "table_name": "bus_stop_data",
        "extraction_functions": [os_to_lat_lon, get_borough_from_lat_lon],
        "data_row_start": 2,
        "data_row_end": 21518,
        "columns": [
            {"col": 0, "name": "X", "type": "FLOAT"},
            {"col": 1, "name": "Y", "type": "FLOAT"},
            {"col": 3, "name": "stop_name", "type": "STRING"},
            {"col": 13, "name": "postcode", "type": "STRING"},
            {"col": 15, "name": "_source_file", "type": "STRING"},
            {"col": 16, "name": "_sheet_name", "type": "STRING"},
            {"col": 17, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 18, "name": "_row_number", "type": "INTEGER"},
        ]
    },
    {
        "sources": [
            {
                "file": "ingestion_dlr_stop_data_2025.csv"
            },

        ],
        "table_name": "dlr_stop_data",
        "extraction_functions": [os_to_lat_lon, get_borough_from_lat_lon],
        "data_row_start": 2,
        "data_row_end": 48,
        "columns": [
            {"col": 0, "name": "X", "type": "FLOAT"},
            {"col": 1, "name": "Y", "type": "FLOAT"},
            {"col": 3, "name": "stop_name", "type": "STRING"},
            {"col": 8, "name": "_source_file", "type": "STRING"},
            {"col": 9, "name": "_sheet_name", "type": "STRING"},
            {"col": 10, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 11, "name": "_row_number", "type": "INTEGER"},
        ]
    },
    {
        "sources": [
            {
                "file": "ingestion_elizabeth_stop_data_2025.csv"
            },

        ],
        "table_name": "elizabeth_stop_data",
        "extraction_functions": [os_to_lat_lon, get_borough_from_lat_lon],
        "data_row_start": 2,
        "data_row_end": 44,
        "columns": [
            {"col": 0, "name": "X", "type": "FLOAT"},
            {"col": 1, "name": "Y", "type": "FLOAT"},
            {"col": 3, "name": "stop_name", "type": "STRING"},
            {"col": 8, "name": "_source_file", "type": "STRING"},
            {"col": 9, "name": "_sheet_name", "type": "STRING"},
            {"col": 10, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 11, "name": "_row_number", "type": "INTEGER"},
        ]
    },
    {
        "sources": [
            {
                "file": "ingestion_overground_stop_data_2025.csv"
            },

        ],
        "table_name": "overground_stop_data",
        "extraction_functions": [os_to_lat_lon, get_borough_from_lat_lon],
        "data_row_start": 2,
        "data_row_end": 115,
        "columns": [
            {"col": 0, "name": "X", "type": "FLOAT"},
            {"col": 1, "name": "Y", "type": "FLOAT"},
            {"col": 3, "name": "stop_name", "type": "STRING"},
            {"col": 8, "name": "_source_file", "type": "STRING"},
            {"col": 9, "name": "_sheet_name", "type": "STRING"},
            {"col": 10, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 11, "name": "_row_number", "type": "INTEGER"},
        ]
    },
    {
        "sources": [
            {
                "file": "ingestion_tramlink_stop_data_2025.csv"
            },

        ],
        "table_name": "tramlink_stop_data",
        "extraction_functions": [os_to_lat_lon, get_borough_from_lat_lon],
        "data_row_start": 2,
        "data_row_end": 42,
        "columns": [
            {"col": 0, "name": "X", "type": "FLOAT"},
            {"col": 1, "name": "Y", "type": "FLOAT"},
            {"col": 3, "name": "stop_name", "type": "STRING"},
            {"col": 8, "name": "_source_file", "type": "STRING"},
            {"col": 9, "name": "_sheet_name", "type": "STRING"},
            {"col": 10, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 11, "name": "_row_number", "type": "INTEGER"},
        ]
    },
    {
        "sources": [
            {
                "file": "ingestion_tube_stop_data_2025.csv"
            },

        ],
        "table_name": "tube_stop_data",
        "extraction_functions": [os_to_lat_lon, get_borough_from_lat_lon],
        "data_row_start": 2,
        "data_row_end": 276,
        "columns": [
            {"col": 0, "name": "X", "type": "FLOAT"},
            {"col": 1, "name": "Y", "type": "FLOAT"},
            {"col": 3, "name": "stop_name", "type": "STRING"},
            {"col": 4, "name": "line_name", "type": "STRING"},
            {"col": 12, "name": "_source_file", "type": "STRING"},
            {"col": 13, "name": "_sheet_name", "type": "STRING"},
            {"col": 14, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 15, "name": "_row_number", "type": "INTEGER"},
        ]
    },
    {
        "sources": [
            {
                "file": "ingestion_ptal_borough_2015_2015.csv"
            },

        ],
        "table_name": "ptal_data",
        "data_row_start": 2,
        "data_row_end": 36,
        "columns": [
            {"col": 0, "name": "ons_code", "type": "STRING"},
            {"col": 1, "name": "BOROUGH", "type": "STRING"},
            {"col": 2, "name": "avg_ptal", "type": "FLOAT"},
            {"col": 3, "name": "ptal", "type": "STRING"},
            {"col": 4, "name": "_source_file", "type": "STRING"},
            {"col": 5, "name": "_sheet_name", "type": "STRING"},
            {"col": 6, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 7, "name": "_row_number", "type": "INTEGER"},
        ]
    },
]

PIPE_NAME = "infrastructure"
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
                dry_run=True  # Set to False when ready to upload
            )
        else:
            print(f"  [WARN] No data processed for pipeline: {table_name}")
