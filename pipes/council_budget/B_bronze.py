
from utils.ingestion import ingestion_excel, batch_ingestion_excel
from utils.big_query.import_big_query import load_into_bigquery
from pathlib import Path



# ──pipes/council_budget/B_bronze Config ───────────────────────────────────────────────────────────────────
SHEET_INDEX = [3]
SHEET_NAME = "Worksheet 2: Revenue Account Budget (RA) 2025-26: Revenue Account data"
PIPE_NAME = "council_budget"
PROJECT_ID = "roomreview-487913"
LAYER = "bronze_layer"
OUTPUT_NAME = "ingestion"


def run_pipeline(project_root: Path):
    # Ingest excel sheet
    raw_file = project_root / "data" / "A_raw" / "council_budget" / "Council_Budgets.xlsx"
    df = batch_ingestion_excel(
        file_path=raw_file,
        sheet_targets=SHEET_INDEX,
        pipe_name=PIPE_NAME,
        output_name=OUTPUT_NAME
    )
    # # Upload data to Big query
    # load_into_bigquery(
    #     project_id=PROJECT_ID,
    #     layer=LAYER,
    #     table_name=PIPE_NAME,
    #     df=df,
    #     dry_run=True
    # )