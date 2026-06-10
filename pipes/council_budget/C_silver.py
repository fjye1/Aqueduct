from utils.extraction import column_row_extractor
from utils.big_query.import_big_query import load_into_bigquery
from pathlib import Path

# ──pipes/council_budget/C_silver Config ───────────────────────────────────────────────────────────────────
DATA_ROW_START = 11
DATA_ROW_END = 424
COLUMNS= [
            {"col": 1, "name": "ons_code", "type": "STRING"},
            {"col": 2, "name": "local_authority", "type": "STRING"},
            {"col": 12, "name": "total_education_services", "type": "FLOAT"},
            {"col": 28, "name": "total_highways_and_transport_services", "type": "FLOAT"},
            {"col": 212, "name": "_source_file", "type": "STRING"},
            {"col": 213, "name": "_sheet_name", "type": "STRING"},
            {"col": 214, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 215, "name": "_row_number", "type": "INTEGER"},
        ]
OUTPUT_NAME ="extraction"
SHEET_NAME = "Worksheet 2: Revenue Account Budget (RA) 2025-26: Revenue Account data"
PIPE_NAME = "council_budget"
PROJECT_ID = "roomreview-487913"
LAYER = "silver_layer"


def run_pipeline(project_root: Path):
    # extract rows and columns from csv
    raw_file = project_root / "data" / "B_bronze" / "council_budget" / "ingestion.csv"
    df = column_row_extractor(
        file_path=raw_file,
        data_row_start=DATA_ROW_START,
        data_row_end=DATA_ROW_END,
        columns=COLUMNS,
        output_name=OUTPUT_NAME,
        pipe_name=PIPE_NAME
    )

    # Upload data to Big query
    load_into_bigquery(
        project_id=PROJECT_ID,
        layer=LAYER,
        table_name=PIPE_NAME,
        df=df,
        dry_run=True
    )