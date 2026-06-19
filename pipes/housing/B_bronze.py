from pathlib import Path
from utils.helper import sanitise
from utils.big_query.import_big_query import load_into_bigquery
from utils.ingestion import batch_ingestion_excel

PIPELINES = [

    {
        "sources": [
            {
                "file": "Housing_Statistics_tables_June_2025.xlsx",
                "sheet_index": "Table 2a",
                "year_name": "2025"
            },
            {
                "file": "Housing_Statistics_tables_June_2024.xlsx",
                "sheet_index": "Table 2a",
                "year_name": "2024"
            },
            {
                "file": "Housing_Statistics_tables_June_2024.xlsx",
                "sheet_index": "Table 2b",
                "year_name": "2023"
            },
            {
                "file": "Housing_Statistics_tables_June_2024.xlsx",
                "sheet_index": "Table 2c",
                "year_name": "2022"
            },
            {
                "file": "Housing_Statistics_tables_June_2024.xlsx",
                "sheet_index": "Table 2d",
                "year_name": "2021"
            }
        ],
        "table_name": "Affordable_housing_net_additions_local",
        "ingestion_function": batch_ingestion_excel,
    },

]

PIPE_NAME = "housing"
PROJECT_ID = "roomreview-487913"
LAYER = "bronze_layer"
OUTPUT_NAME = "ingestion"


def run_pipeline(project_root: Path):
    for config in PIPELINES:
        # 1. Resolve full paths for all sources in this pipeline
        base_path = project_root / "data" / "A_raw" / PIPE_NAME

        resolved_sources = []
        for src in config["sources"]:
            resolved_sources.append({
                "file": base_path / src["file"],  # Converts just the filename to a full Path object
                "sheet_index": src.get("sheet_index", 0),
                "year_name": src.get("year_name")
            })

        dfs_to_upload = config["ingestion_function"](
            sources=resolved_sources,  # Matches the 'sources' parameter name
            pipe_name=PIPE_NAME,
            output_name=OUTPUT_NAME,
            table_name=config["table_name"],

        )
        for year_name, df in dfs_to_upload.items():
            clean_table_name = sanitise(config["table_name"])

            target_table = f"{PIPE_NAME}_{clean_table_name}_{year_name}"

            print(
                f"Uploading sheet '{year_name}' "
                f"to BigQuery table: {target_table}..."
            )

            load_into_bigquery(
                project_id=PROJECT_ID,
                layer=LAYER,
                table_name=target_table,
                df=df,
                dry_run=True  # Set to false when you want to upload
            )
