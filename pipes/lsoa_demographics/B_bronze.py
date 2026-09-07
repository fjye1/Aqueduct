from pathlib import Path

from utils.big_query.import_big_query import load_into_bigquery
from utils.helper import sanitise
from utils.io.ingestion import batch_ingestion_excel


PIPELINES = [

    {
        "sources": [
            {
                "file": "sapelsoasyoa20222024.xlsx",
                "sheet_index": "Mid-2024 LSOA 2021",
                "year_name": "2024"
            },

        ],
        "table_name": "lsoa_demographics",
        "ingestion_function": batch_ingestion_excel,
    }

]

PIPE_NAME = "lsoa_demographics"
PROJECT_ID = "roomreview-487913"
LAYER = "bronze_layer"
OUTPUT_NAME = "ingestion"
DRY_RUN = True  # Select False when ready to upload

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
                dry_run=DRY_RUN
            )
