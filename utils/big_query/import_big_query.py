import pandas as pd
from utils.helper import _pandas_dtype_to_bq
from google.cloud import bigquery

"""
This function imports data from your local machine up to big query.

local machine -> Big query. 
"""

# TODO Read up on pandas-gbq to see if that is a better method
#TODO Write a test for this function
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
        print(f"[DRY RUN] table_id:\n{table_id}")
        return

    client = bigquery.Client(project=project_id)  # only created when needed

    # allow _pandas_dtype_to_bq to determine type.
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        schema=[
            bigquery.SchemaField(col, _pandas_dtype_to_bq(df[col].dtype))
            for col in df.columns
        ]
    )
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    # ── Add table description ─────────────────────────────────────────────────
    table = client.get_table(table_id)
    table.description = (

        "Rows are not guaranteed to be in original order. "
        "Use ORDER BY _row_number to restore original row sequence."
    )
    client.update_table(table, ["description"])

    print(f"Loaded {job.output_rows} rows to {table_id}")

