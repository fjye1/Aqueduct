import os
from datetime import datetime

import pandas as pd

from utils.audit import build_audit_columns
from utils.helper import sanitise


def ingestion_excel(file_path, sheet_target, pipe_name, output_name, table_name):
    print(f"\n--- Processing Sheet: {sheet_target} ---")
    """Ingests an Excel sheet using either its 0-based index or its string name.

            Parameters:
            - file_path (str): Path to the Excel file.
            - sheet_target (int or str): The sheet name (str) or 0-indexed position
            (int) to load.
            - sheet_name_label (str, optional): A custom label for the audit column.
              If None, it defaults to the sheet_target.
            """
    # 1. Load the specific sheet
    df = pd.read_excel(file_path, sheet_name=sheet_target, header=None, dtype=str, )
    print(f"Loaded — shape: {df.shape}")

    # 2. Format columns
    df.columns = [f"col_{i}" for i in range(df.shape[1])]
    df = df.where(df.isna(), df.astype(str))

    # 3. Audit columns
    df = build_audit_columns(
        df,
        source_file=table_name,
        sheet_target=sheet_target,
    )

    # 4. Save files with a unique sheet suffix to prevent overwriting
    date = datetime.now().strftime("%Y-%m-%d")
    sheet_target = sanitise(sheet_target)

    csv_path = f"data/B_bronze/{pipe_name}/{output_name}_{table_name}_Sheetid_{sheet_target}-{date}.csv"

    # Ensure directory exists
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    df.to_csv(csv_path, index=False)

    print(f"Saved to {csv_path}")

    return df


def batch_ingestion_excel(sources, pipe_name, output_name, table_name):
    # Create a dictionary to hold all dataframes
    processed_dfs = {}
    for src in sources:
        file_path = src["file"]
        sheet_targets = src.get("sheet_index", 0)
        """
            Orchestrates the ingestion. Accepts a single sheet (str/int)
            or a list of sheets [str/int].
            """

        # If it's a single entry (not a list/tuple), wrap it in a list so we can loop
        if not isinstance(sheet_targets, (list, tuple)):
            sheet_targets = [sheet_targets]



        print(f"Starting pipeline for {len(sheet_targets)} sheet(s)...")

        # Loop through every sheet targeted
        for target in sheet_targets:
            try:
                # single ingestion function executes and returns a single dataframe
                df = ingestion_excel(
                    file_path=file_path,
                    sheet_target=target,
                    pipe_name=pipe_name,
                    output_name=output_name,
                    table_name=table_name
                )

                # Store it using the sheet target (or name) as the key
                processed_dfs[target] = df

            except Exception as e:
                # If one sheet fails, log it but keep processing the other sheets!
                print(f" Error processing sheet '{target}': {e}")
                continue

    # Return the entire dictionary of dataframes
    return processed_dfs


def ingestion_csv(file_path, pipe_name, output_name, table_name):
    print(f"\n--- Processing CSV File: {file_path} ---")
    """Ingests a CSV file.

    Parameters:
    - file_path (str): Path to the CSV file.
    - pipe_name (str): Name of the pipeline folder.
    - output_name (str): Prefix for the output filename.
    - file_label (str, optional): A custom label for the audit column.
      If None, it defaults to the base file name.
    """
    # 1. Load the CSV file
    # added keep_default_na=False or similar if you want to match Excel's blank handling,
    # but header=None is kept to match your original logic.
    df = pd.read_csv(file_path, header=None, dtype=str, )
    print(f"Loaded — shape: {df.shape}")

    # 2. Format columns
    df.columns = [f"col_{i}" for i in range(df.shape[1])]
    df = df.where(df.isna(), df.astype(str))

    # 3. Audit columns (Updated parameters to reflect file-based tracking)
    df = build_audit_columns(
        df,
        source_file=table_name,
    )

    # 4. Save files with a unique suffix based on the original file name
    date = datetime.now().strftime("%Y-%m-%d")

    csv_path = f"data/B_bronze/{pipe_name}/{output_name}_{table_name}-{date}.csv"

    # Ensure directory exists
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    df.to_csv(csv_path, index=False)
    print(f"Saved to {csv_path}")

    return df


def batch_ingestion_csv(sources, pipe_name, output_name, table_name):
    """
    Ingest multiple CSV sources and return dict of dataframes.
    Each source is expected to be:
    {"file": "path/to/file.csv"}
    """

    processed_dfs = {}

    print(f"Starting CSV pipeline for {len(sources)} file(s)...")

    for src in sources:
        file_path = src["file"]

        try:
            df = ingestion_csv(
                file_path=file_path,
                pipe_name=pipe_name,
                output_name=output_name,
                table_name=table_name
            )

            # key by file so nothing gets overwritten
            processed_dfs[table_name] = df

        except Exception as e:
            print(f"Error processing file '{file_path}': {e}")
            continue

    return processed_dfs

# # ──Test Config ───────────────────────────────────────────────────────────────────
# RAW_FILE = "/data/A_raw/council_budget/Council_Budgets.xlsx"
# SHEET_INDEX = 3
# SHEET_NAME = "Worksheet 2: Revenue Account Budget (RA) 2025-26: Revenue Account data"
# PIPE_NAME = "Council_Budgets"
# OUTPUT_NAME = "ingestion"
#
# raw_file = project_root / "data" / "A_raw" / "council_budget" / "Council_Budgets.xlsx"
# batch_ingestion_excel(
#         file_path=raw_file,
#         sheet_targets=SHEET_INDEX,
#         pipe_name=PIPE_NAME,
#         output_name=OUTPUT_NAME
#     )
