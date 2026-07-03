from pathlib import Path
from functools import partial
import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.io.extraction import column_row_extractor
from utils.transformations.filters import london_borough_filter, merge_school_and_ofsted


JOINS = [
    # Example — leave empty/commented out unless you actually want a merge here
    {
        "name": "school_with_ofsted",
        "tables": ["school_location_data", "school_ofsted_inspection"],
        "merge_function": merge_school_and_ofsted,  # defined elsewhere, imported at top
    },
]

PIPELINES = [

    {
        "sources": [
            {
                "file": "ingestion_school_location_data_2026.csv"
            },

        ],
        "table_name": "school_location_data",
        "extraction_functions": [london_borough_filter],
        "data_row_start": 2,
        "data_row_end": 52403,
        "columns": [
            {"col": 0, "name": "unique_reference_number", "type": "INTEGER"},
            {"col": 2, "name": "borough_name", "type": "STRING"},
            {"col": 101, "name": "ons_code", "type": "STRING"},
            {"col": 6, "name": "type_of_establishment", "type": "STRING"},
            {"col": 8, "name": "establishment_group", "type": "STRING"},
            {"col": 10, "name": "status", "type": "STRING"},
            {"col": 19, "name": "stat_low_age", "type": "INTEGER"},
            {"col": 20, "name": "stat_high_age", "type": "INTEGER"},
            {"col": 35, "name": "pupil_capacity", "type": "INTEGER"},
            {"col": 39, "name": "current_pupils", "type": "INTEGER"},
            {"col": 135, "name": "_source_file", "type": "STRING"},
            {"col": 136, "name": "_sheet_name", "type": "STRING"},
            {"col": 137, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 138, "name": "_row_number", "type": "INTEGER"},

        ]
    },
    {
        "sources": [
            {
                "file": "ingestion_school_ofsted_inspection_2026.csv"
            },

        ],
        "table_name": "school_ofsted_inspection",
        "extraction_functions": [partial(london_borough_filter, filter_by_ons_code=False)],
        "data_row_start": 5,
        "data_row_end": 21996,
        "columns": [

            {"col": 1, "name": "unique_reference_number", "type": "INTEGER"},
            {"col": 14, "name": "borough_name", "type": "STRING"},
            {"col": 45, "name": "previous_urn", "type": "INTEGER"},
            {"col": 52, "name": "quality_of_education", "type": "INTEGER"},
            {"col": 53, "name": "behaviour_and_attitudes", "type": "INTEGER"},
            {"col": 54, "name": "personal_development", "type": "INTEGER"},
            {"col": 55, "name": "effectiveness_of_leadership_and_management", "type": "INTEGER"},
            {"col": 76, "name": "_source_file", "type": "STRING"},
            {"col": 77, "name": "_sheet_name", "type": "STRING"},
            {"col": 78, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 79, "name": "_row_number", "type": "INTEGER"},
        ]
    },

]

PIPE_NAME = "education"
PROJECT_ID = "roomreview-487913"
LAYER = "silver_layer"
OUTPUT_NAME = "extraction"


def run_pipeline(project_root: Path):
    folder = project_root / "data" / "B_bronze" / PIPE_NAME
    table_dfs = {}
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
            table_dfs[table_name] = final_df

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

            # --- NEW: optional aggregation step, safe if AGGREGATIONS not defined/empty ---
        joins = globals().get("JOINS", [])
        for j in joins:
            required = j["tables"]
            missing = [t for t in required if t not in table_dfs]
            if missing:
                print(f"  [SKIP] Aggregation '{j['name']}' skipped, missing tables: {missing}")
                continue

            print(f"\n--- Aggregating: {j['name']} ---")
            merged_df = j["merge_function"]({t: table_dfs[t] for t in required})

            out_path = project_root / "data" / "C_silver" / PIPE_NAME / f"{OUTPUT_NAME}_{j['name']}.csv"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            merged_df.to_csv(out_path, index=False)
            print(f"  Saved aggregation to {out_path}")

            print(f"  Uploading to BigQuery table: {PIPE_NAME}_{j['name']}...")
            load_into_bigquery(
                project_id=PROJECT_ID,
                layer=LAYER,
                table_name=f"{PIPE_NAME}_{j['name']}",
                df=merged_df,
                dry_run=True
            )

