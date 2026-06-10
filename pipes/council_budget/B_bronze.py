
from utils.ingestion import ingestion_excel
from utils.big_query.import_big_query import load_into_bigquery
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# ──Test Config ───────────────────────────────────────────────────────────────────
RAW_FILE = PROJECT_ROOT / "data" / "0_raw" / "council_budget" / "Council_Budgets.xlsx"
SHEET_INDEX = 3
SHEET_NAME = "Worksheet 2: Revenue Account Budget (RA) 2025-26: Revenue Account data"
PIPE_NAME = "council_budget"
PROJECT_ID = "roomreview-487913"
LAYER = "bronze_layer"


def run_pipeline(project_root: Path):
    # Ingest excel sheet
    raw_file = project_root / "data" / "0_raw" / "council_budget" / "Council_Budgets.xlsx"
    df = ingestion_excel(
        file_path=raw_file,
        sheet_target=SHEET_INDEX,
        pipe_name=PIPE_NAME,
        sheet_name_label=SHEET_NAME
    )
    # Upload data to Big query
    load_into_bigquery(
        project_id=PROJECT_ID,
        layer=LAYER,
        table_name=PIPE_NAME,
        df=df,
        dry_run=True
    )