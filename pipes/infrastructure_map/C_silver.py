from pathlib import Path
from functools import partial
import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.io.extraction import column_row_extractor
from utils.transformations.filters import get_borough_from_lat_lon, london_borough_filter

PIPELINES = [

    {
        "sources": [
            {
                "file": "ingestion_transport_stops_2026.csv"
            },

        ],
        "table_name": "transport_stops",
        "extraction_functions": [get_borough_from_lat_lon, partial(london_borough_filter, filter_by_ons_code=False)],
        "data_row_start": 2,
        "data_row_end": 435194,
        "columns": [
            {"col": 0, "name": "ATCOCode", "type": "STRING"},
            {"col": 4, "name": "commonname", "type": "STRING"},
            {"col": 29, "name": "Longitude", "type": "FLOAT"},
            {"col": 30, "name": "Latitude", "type": "FLOAT"},
            {"col": 43, "name": "_source_file", "type": "STRING"},
            {"col": 44, "name": "_sheet_name", "type": "STRING"},
            {"col": 45, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 46, "name": "_row_number", "type": "INTEGER"},
        ]
    },

]

PIPE_NAME = "infrastructure_map"
PROJECT_ID = "roomreview-487913"
LAYER = "silver_layer"
OUTPUT_NAME = "extraction"
DRY_RUN = True


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
                dry_run=DRY_RUN  # Set to False when ready to upload
            )
        else:
            print(f"  [WARN] No data processed for pipeline: {table_name}")
