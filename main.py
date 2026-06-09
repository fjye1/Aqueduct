from council_budget.silver.council_budget_silver import flatten_drop
import os

from dotenv import load_dotenv

from council_budget.silver.council_budget_silver import flatten_drop

# This main is designed to be changed when new projects are loaded.
load_dotenv()

project_id = os.getenv("PROJECT_ID")
layer = os.getenv("LAYER")

RAW_FILE = "council_budget/bronze/Council_Budgets.xlsx"
SHEET_INDEX = 3
SHEET_NAME = "Worksheet 2: Revenue Account Budget (RA) 2025-26: Revenue Account data"

# Test it:
# df = ingestion_excel(
#     file_path=RAW_FILE, sheet_target=SHEET_INDEX, sheet_name_label=SHEET_NAME
# )



flatten_drop(
    file_path="Test_output.csv",

    data_row_start=11,
    data_row_end=424,
    columns=[
        {"col": 1, "name": "ons_code", "type": "STRING"},
        {"col": 2, "name": "local_authority", "type": "STRING"},
        {"col": 12, "name": "total_education_services", "type": "FLOAT"},
        {"col": 28, "name": "total_highways_and_transport_services", "type": "FLOAT"},
        {"col": 212, "name": "_source_file", "type": "STRING"},
        {"col": 213, "name": "_sheet_name", "type": "STRING"},
        {"col": 214, "name": "_ingested_at", "type": "DATETIME"},
        {"col": 215, "name": "_row_number", "type": "INTEGER"},
    ],
    output_name="council_budget_flat"
)

# load_into_bigquery(project_id,layer,"council_budget",df,dry_run=False)


# pip freeze > requirements.txt
