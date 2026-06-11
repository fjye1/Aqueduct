from utils.audit import build_audit_columns
import pandas as pd
import os
from datetime import datetime

# def ingestion_excel(file_path, sheet_target, pipe_name, output_name,sheet_name_label=None):
#     """Ingests an Excel sheet using either its 0-based index or its string name.
#
#         Parameters:
#         - file_path (str): Path to the Excel file.
#         - sheet_target (int or str): The sheet name (str) or 0-indexed position
#         (int) to load.
#         - sheet_name_label (str, optional): A custom label for the audit column.
#           If None, it defaults to the sheet_target.
#         """
#     print(os.getcwd())
#     print("Loading file...")
#     # pd.read_excel natively accepts both integers (index) and strings (name) for sheet_name
#     df = pd.read_excel(file_path, sheet_name=sheet_target, header=None)
#     print(f"Loaded — shape: {df.shape}")
#     # ── Rename data columns to positional names ───────────────────────────────────
#     df.columns = [f"col_{i}" for i in range(df.shape[1])]
#     # ── Safely cast all data columns to string ────────────────────────────────────
#     df = df.where(df.isna(), df.astype(str))
#     # ── Call audit function to add audit info for logging──────────────────────────
#     df = build_audit_columns(
#         df,
#         file_path=file_path,
#         sheet_target=sheet_target,
#         sheet_name_label=sheet_name_label,
#     )
#
#     print(f"Final shape: {df.shape}")
#     print(df.head())
#     date = datetime.now().strftime("%Y-%m-%d")
#     df.to_csv(f"data/B_bronze/{pipe_name}/{output_name}-{date}.csv", index=False)
#     df.to_excel(f"data/B_bronze/{pipe_name}/{output_name}-{date}.xlsx", index=False)
#     return df


def ingestion_excel(file_path, sheet_target, pipe_name, output_name, sheet_name_label=None):
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
    df = pd.read_excel(file_path, sheet_name=sheet_target, header=None)
    print(f"Loaded — shape: {df.shape}")

    # 2. Format columns
    df.columns = [f"col_{i}" for i in range(df.shape[1])]
    df = df.where(df.isna(), df.astype(str))

    # 3. Handle labels cleanly
    label = sheet_name_label if sheet_name_label else str(sheet_target)

    # 4. Audit columns
    df = build_audit_columns(
        df,
        file_path=file_path,
        sheet_target=sheet_target,
        sheet_name_label=label,
    )

    # 5. Save files with a unique sheet suffix to prevent overwriting
    date = datetime.now().strftime("%Y-%m-%d")
    clean_sheet_suffix = str(sheet_target).lower().replace(" ", "_")

    csv_path = f"data/B_bronze/{pipe_name}/{output_name}_Sheet_{clean_sheet_suffix}-{date}.csv"


    # Ensure directory exists
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    df.to_csv(csv_path, index=False)

    print(f"Saved to {csv_path}")

    return df


def batch_ingestion_excel(file_path, sheet_targets, pipe_name, output_name):
    """
    Orchestrates the ingestion. Accepts a single sheet (str/int)
    or a list of sheets [str/int].
    """

    # If it's a single entry (not a list/tuple), wrap it in a list so we can loop
    if not isinstance(sheet_targets, (list, tuple)):
        sheet_targets = [sheet_targets]

    # Create a dictionary to hold all dataframes
    processed_dfs = {}

    print(f"Starting pipeline for {len(sheet_targets)} sheet(s)...")

    # Loop through every sheet targeted
    for target in sheet_targets:
        try:
            # single ingestion function executes and returns a single dataframe
            df = ingestion_excel(
                file_path=file_path,
                sheet_target=target,
                pipe_name=pipe_name,
                output_name=output_name
            )

            # Store it using the sheet target (or name) as the key
            processed_dfs[target] = df

        except Exception as e:
            # If one sheet fails, log it but keep processing the other sheets!
            print(f" Error processing sheet '{target}': {e}")
            continue

    # Return the entire dictionary of dataframes
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