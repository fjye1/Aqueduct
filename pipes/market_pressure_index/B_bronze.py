from utils.helper import sanitise
from utils.ingestion import batch_ingestion_csv
from utils.big_query.import_big_query import load_into_bigquery
from pathlib import Path

# ──pipes/market_pressure_index/B_bronze Config ───────────────────────────────────────────────────────────────────

SHEET_NAME = "Average-prices-2026-03(Average-Price(national)).csv"
TABLE_NAME = "average_prices_2026_03"
PIPE_NAME = "market_pressure_index"
PROJECT_ID = "roomreview-487913"
LAYER = "bronze_layer"
OUTPUT_NAME = "ingestion"


def run_pipeline(project_root: Path):
    # Ingest csv sheet
    raw_file = project_root / "data" / "A_raw" / f"{PIPE_NAME}" / f"{SHEET_NAME}"

    dfs_to_upload = batch_ingestion_csv(
        file_paths=raw_file,
        pipe_name=PIPE_NAME,
        output_name=OUTPUT_NAME,
        table_name=TABLE_NAME
    )


    # Loop through the dictionary and upload each dataframe to BigQuery
    for sheet_name, df in dfs_to_upload.items():
        # Clean the sheet name for BigQuery compatibility (e.g., "2025 Data" -> "2025_data")
        clean_table_name = sanitise(TABLE_NAME)

        # Combine pipe name and sheet name for a unique Bronze table
        target_table = f"{PIPE_NAME}__{clean_table_name}"

        print(f"Uploading sheet '{sheet_name}' to BigQuery table: {target_table}...")

        # load_into_bigquery(
        #     project_id=PROJECT_ID,
        #     layer=LAYER,
        #     table_name=target_table,  # Dynamically named per sheet
        #     df=df,
        #     dry_run=True  # Set to false when you want to test the feature but not upload
        # )
