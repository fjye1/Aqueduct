import pandas as pd
from google.cloud import bigquery


def ingestion_excel(file_path, sheet_target, sheet_name_label=None):
    """Ingests an Excel sheet using either its 0-based index or its string name.

    Parameters:
    - file_path (str): Path to the Excel file.
    - sheet_target (int or str): The sheet name (str) or 0-indexed position
    (int) to load.
    - sheet_name_label (str, optional): A custom label for the audit column.
      If None, it defaults to the sheet_target.
    """
    print("Loading file...")

    # pd.read_excel natively accepts both integers (index) and strings (name) for sheet_name
    df = pd.read_excel(file_path, sheet_name=sheet_target, header=None)
    print(f"Loaded — shape: {df.shape}")

    # ── Rename data columns to positional names ───────────────────────────────────
    df.columns = [f"col_{i}" for i in range(df.shape[1])]

    # ── Safely cast all data columns to string ────────────────────────────────────
    df = df.where(df.isna(), df.astype(str))

    # ── Determine what to put in the audit column ─────────────────────────────────
    # If a specific label wasn't passed, use the target we loaded
    sheet_label = (
        sheet_name_label if sheet_name_label is not None else str(sheet_target)
    )

    # ── Add all audit columns in one concat (avoids fragmentation warning) ────────
    audit = pd.DataFrame(
        {
            "_source_file": file_path,
            "_sheet_name": sheet_label,
            "_ingested_at": pd.Timestamp.now(tz="UTC"),
            "_row_number": df.index,
        },
        index=df.index,
    )

    df = pd.concat([df, audit], axis=1)

    print(f"Final shape: {df.shape}")
    print(df.head())
    df.to_csv("Test_output.csv", index=False)
    return df


# ──Test Config ───────────────────────────────────────────────────────────────────
# RAW_FILE = "Council_Budgets.xlsx"
# SHEET_INDEX = 3
# SHEET_NAME = "Worksheet 2: Revenue Account Budget (RA) 2025-26: Revenue Account data"
#
# # Test it:
# df_test = ingestion_excel(
#     file_path=RAW_FILE, sheet_target=SHEET_INDEX, sheet_name_label=SHEET_NAME
# )

def load_into_bigquery(
        project_id: str,
        layer: str,
        table_name: str,
        df: pd.DataFrame,
        dry_run: bool,
) -> None:
    table_id = f"{project_id}.{layer}.{table_name}"

    if dry_run:
        print(f"[DRY RUN] Would load {len(df)} rows into {table_id}")
        print(f"[DRY RUN] Columns: {list(df.columns)}")
        print(f"[DRY RUN] Sample:\n{df.head(4)}")
        return

    client = bigquery.Client(project=project_id)  # only created when needed

    # Force all columns to STRING explicitly in the schema
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        schema=[
                   bigquery.SchemaField(col, "STRING",
                                        description="Raw Excel column — see silver layer for named, transformed equivalent")
                   for col in df.columns if not col.startswith("_")
               ] + [
                   bigquery.SchemaField("_source_file", "STRING", description="Source Excel filename"),
                   bigquery.SchemaField("_sheet_name", "STRING", description="Source sheet name or label"),
                   bigquery.SchemaField("_ingested_at", "TIMESTAMP", description="UTC timestamp of ingestion"),
                   bigquery.SchemaField("_row_number", "INTEGER",
                                        description="Original Excel row order — use ORDER BY _row_number to restore source sequence"),
               ]
    )

    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    # ── Add table description ─────────────────────────────────────────────────
    table = client.get_table(table_id)
    table.description = (
        "Bronze layer raw ingestion from Excel. "
        "Rows are not guaranteed to be in original order. "
        "Use ORDER BY _row_number to restore original Excel row sequence."
    )
    client.update_table(table, ["description"])

    print(f"Loaded {job.output_rows} rows to {table_id}")

    print(f"Loaded {job.output_rows} rows to {table_id}")
