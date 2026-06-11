from datetime import datetime
from pathlib import Path

import pandas as pd
from utils.big_query.import_big_query import load_into_bigquery
from utils.extraction import column_row_extractor
from utils.filters import london_borough_filter

# ──pipes/council_budget/C_silver Config ───────────────────────────────────────────────────────────────────
DATA_ROW_START = 11
DATA_ROW_END = 424
COLUMNS = [
    {"col": 1, "name": "ons_code", "type": "STRING"},
    {"col": 2, "name": "local_authority", "type": "STRING"},
    {"col": 12, "name": "total_education_services", "type": "FLOAT"},
    {"col": 28, "name": "total_highways_and_transport_services", "type": "FLOAT"},
    {"col": 212, "name": "_source_file", "type": "STRING"},
    {"col": 213, "name": "_sheet_name", "type": "STRING"},
    {"col": 214, "name": "_ingested_at", "type": "DATETIME"},
    {"col": 215, "name": "_row_number", "type": "INTEGER"},
]


OUTPUT_NAME = "extraction"
SHEET_NAME = "Worksheet 2: Revenue Account Budget (RA) 2025-26: Revenue Account data"
PIPE_NAME = "council_budget"
PROJECT_ID = "roomreview-487913"
LAYER = "silver_layer"

# A list of the sheets that you wish to target and append from the previous transformation



def run_pipeline(project_root: Path):
    folder = project_root / "data" / "B_bronze" / "council_budget"
    target_sheets = TARGET_SHEETS
    # Initialize a list to hold dataframes for each processed sheet
    processed_dfs = []
    # Iterate through the sheets in the exact order provided in the list
    for sheet in target_sheets:
        # Find all files for this specific sheet recursively
        # Pattern matches: ingestion_Sheet_3-*.csv
        sheet_files = sorted(folder.rglob(f"ingestion_Sheet_{sheet}-*.csv"))
        if not sheet_files:
            print(f"Warning: No files found for Sheet {sheet} in {folder}")
            continue
        # Pick the latest file for this specific sheet (mirroring your original logic)
        raw_file = sheet_files[-1]
        print(f"Processing Sheet {sheet}: {raw_file.name}")
        # Run your extractor for this specific file
        df_sheet = column_row_extractor(
            file_path=raw_file,
            data_row_start=DATA_ROW_START,
            data_row_end=DATA_ROW_END,
            columns=COLUMNS,
            output_name=OUTPUT_NAME,
            pipe_name=PIPE_NAME,
            function_filter=london_borough_filter,
            sheet=sheet,
        )
        # Optional: Add a column to keep track of which sheet this data came from
        df_sheet["source_sheet"] = sheet
        processed_dfs.append(df_sheet)
    # Combine all the processed sheets into one final DataFrame
    if processed_dfs:
        final_df = pd.concat(processed_dfs, ignore_index=True)
        date = datetime.now().strftime("%Y-%m-%d")
        final_df.to_csv(f"data/C_silver/{PIPE_NAME}/{OUTPUT_NAME}_CONCAT-{date}.csv", index=False)
        # Load into BigQuery after data concatenated
        print(f"Loading data into BigQuery table: {PIPE_NAME}...")
        load_into_bigquery(
            project_id=PROJECT_ID,
            layer=LAYER,
            table_name=PIPE_NAME,
            df=final_df,

            # SET to false when you want to upload to BQ
            dry_run=True
        )
        return final_df
    else:
        print("No data was processed.")
        return None

    # # Upload data to Big query
