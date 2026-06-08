from council_budget.bronze.council_budget_ingest import ingestion_excel, load_into_bigquery

from dotenv import load_dotenv
import os

load_dotenv()

project_id = os.getenv("PROJECT_ID")
layer = os.getenv("LAYER")

RAW_FILE = "council_budget/bronze/Council_Budgets.xlsx"
SHEET_INDEX = 3
SHEET_NAME = "Worksheet 2: Revenue Account Budget (RA) 2025-26: Revenue Account data"

# Test it:
df = ingestion_excel(
    file_path=RAW_FILE, sheet_target=SHEET_INDEX, sheet_name_label=SHEET_NAME
)



load_into_bigquery(project_id,layer,"council_budget",df,dry_run=True)


# pip freeze > requirements.txt