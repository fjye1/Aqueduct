from pathlib import Path

from utils.big_query.import_big_query import load_into_bigquery
from utils.helper import sanitise
from utils.io.ingestion import batch_ingestion_csv, batch_ingestion_excel

# ──pipes/market_pressure_index/B_bronze Config ───────────────────────────────────────────────────────────────────
# average-prices-2026,dwelling_stock_local

#"sources" refers to the different sources within a document
#"file" refers to the file path
#"table_name" is a short name for the source doc
#"ingestion_function" is the function you want to use either CSV or Excel
#PIPE_NAME is the pipe project
#OUTPUT_NAME refers to the stage of data transformation.

PIPELINES = [
    {
        "sources": [
            {
                "file": "Average-prices-2026-03(Average-Price(national)).csv",
                "sheet_index": "na",
                "year_name": "1968-2026"
            }
        ],
        "table_name": "average_prices_2026_03",
        "ingestion_function": batch_ingestion_csv,
    },
    {
        "sources": [
            {
                "file": "LiveTable100(Dwelling-stock(Local)).ods",
                "sheet_index": "2024",
                "year_name": "2024"
            },
            {
                "file": "LiveTable100(Dwelling-stock(Local)).ods",
                "sheet_index": "2025",
                "year_name": "2025"
            }
        ],
        "table_name": "dwelling_stock_local",
        "ingestion_function": batch_ingestion_excel,
    },

]

PIPE_NAME = "market_pressure_index"
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
