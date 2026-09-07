from pathlib import Path

import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.io.extraction import column_row_extractor
from utils.transformations.filters import london_lsoa_filter


def make_age_columns(start_col: int, prefix: str, max_age: int = 90) -> list[dict]:
    """
    Generates {col, name, type} entries for single-year-of-age columns.
    e.g. prefix="F", max_age=90 -> F0, F1, ..., F89, F90+
    """
    cols = []
    for age in range(max_age + 1):
        label = f"{prefix}{age}" if age < max_age else f"{prefix}{max_age}+"
        cols.append({"col": start_col + age, "name": label, "type": "INTEGER"})
    return cols


columns = [

    {"col": 2, "name": "lsoa21cd", "type": "STRING"},
    {"col": 4, "name": "total", "type": "INTEGER"},
]

columns += make_age_columns(start_col=5, prefix="F")            # F0 .. F90+ → cols 5-95
columns += make_age_columns(start_col=5 + 91, prefix="M")        # M0 .. M90+ → cols 96-186

columns += [
    {"col": 187, "name": "_source_file", "type": "STRING"},
    {"col": 188, "name": "_sheet_name", "type": "STRING"},
    {"col": 189, "name": "_ingested_at", "type": "DATETIME"},
    {"col": 190, "name": "_row_number", "type": "INTEGER"},
]
PIPELINES = [

    {
        "sources": [
            {
                "file": "ingestion_lsoa_demographics_2024.csv"
            },

        ],
        "table_name": "lsoa_demographics",
        "extraction_functions": [london_lsoa_filter],
        "data_row_start": 6,
        "data_row_end": 35678,
        "columns": columns
    },

]

PIPE_NAME = "lsoa_demographics"
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


