from utils.helper import sanitise
from utils.ingestion import batch_ingestion_excel
from utils.big_query.import_big_query import load_into_bigquery
from pathlib import Path



# ──pipes/council_budget/B_bronze Config ───────────────────────────────────────────────────────────────────
SHEET_INDEX = [3]
SHEET_NAME = "Council_Budgets.xlsx"
TABLE_NAME = "Council_budget_2026"
PIPE_NAME = "council_budget"
PROJECT_ID = "roomreview-487913"
LAYER = "bronze_layer"
OUTPUT_NAME = "ingestion"


PIPELINES = [
    {
        "sources": [
            {
                "file": "Council_Budgets.xlsx",
                "sheet_index": 3
            }
        ],
        "table_name": "Council_budget_2026",
        "ingestion_function": batch_ingestion_excel,
    },

]

def run_pipeline(project_root: Path):
    for config in PIPELINES:
        # 1. Resolve full paths for all sources in this pipeline
        base_path = project_root / "data" / "A_raw" / PIPE_NAME

        resolved_sources = []
        for src in config["sources"]:
            resolved_sources.append({
                "file": base_path / src["file"],  # Converts just the filename to a full Path object
                "sheet_index": src.get("sheet_index", 0)
            })

        dfs_to_upload = config["ingestion_function"](
            sources=resolved_sources,  # Matches the 'sources' parameter name
            pipe_name=PIPE_NAME,
            output_name=OUTPUT_NAME,
            table_name=config["table_name"],
        )
        # Loop through the dictionary and upload each dataframe to BigQuery
        for sheet_name, df in dfs_to_upload.items():
            # Clean the sheet name for BigQuery compatibility (e.g., "2025 Data" -> "2025_data")
            clean_sheet_name = sanitise(sheet_name)

            # Combine pipe name and sheet name for a unique Bronze table
            target_table = f"{PIPE_NAME}__{clean_sheet_name}"

            print(f"Uploading sheet '{sheet_name}' to BigQuery table: {target_table}...")

            load_into_bigquery(
                project_id=PROJECT_ID,
                layer=LAYER,
                table_name=target_table,  # Dynamically named per sheet
                df=df,
                dry_run=True  # Set to False when you want to upload to big query
            )






