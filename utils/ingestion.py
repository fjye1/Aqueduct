from utils.audit import build_audit_columns
import pandas as pd
import os


def ingestion_excel(file_path, sheet_target, pipe_name, output_name,sheet_name_label=None):
    """Ingests an Excel sheet using either its 0-based index or its string name.

        Parameters:
        - file_path (str): Path to the Excel file.
        - sheet_target (int or str): The sheet name (str) or 0-indexed position
        (int) to load.
        - sheet_name_label (str, optional): A custom label for the audit column.
          If None, it defaults to the sheet_target.
        """
    print(os.getcwd())
    print("Loading file...")
    # pd.read_excel natively accepts both integers (index) and strings (name) for sheet_name
    df = pd.read_excel(file_path, sheet_name=sheet_target, header=None)
    print(f"Loaded — shape: {df.shape}")
    # ── Rename data columns to positional names ───────────────────────────────────
    df.columns = [f"col_{i}" for i in range(df.shape[1])]
    # ── Safely cast all data columns to string ────────────────────────────────────
    df = df.where(df.isna(), df.astype(str))
    # ── Call audit function to add audit info for logging──────────────────────────
    df = build_audit_columns(
        df,
        file_path=file_path,
        sheet_target=sheet_target,
        sheet_name_label=sheet_name_label,
    )

    print(f"Final shape: {df.shape}")
    print(df.head())
    df.to_csv(f"data/1_bronze/{pipe_name}/{output_name}.csv", index=False)
    df.to_excel(f"data/1_bronze/{pipe_name}/{output_name}.xlsx", index=False)
    return df


# # ──Test Config ───────────────────────────────────────────────────────────────────
# RAW_FILE = "/data/A_raw/council_budget/Council_Budgets.xlsx"
# SHEET_INDEX = 3
# SHEET_NAME = "Worksheet 2: Revenue Account Budget (RA) 2025-26: Revenue Account data"
# PIPE_NAME = "Council_Budgets"
#
#
# # Test it:
# df_test = ingestion_excel(
#     file_path=RAW_FILE, sheet_target=SHEET_INDEX, pipe_name=PIPE_NAME, sheet_name_label=SHEET_NAME
# )

