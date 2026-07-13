import pandas as pd
from google.cloud import bigquery
from typing import Union, List
from utils.helper import _pandas_dtype_to_bq

"""
This function imports data from your local machine up to big query.

local machine -> Big query. 
"""


# TODO Read up on pandas-gbq to see if that is a better method
# TODO Write a test for this function
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


def append_json_dataframe_to_bigquery(
        project_id: str,
        layer: str,
        table_name: str,
        df: pd.DataFrame,
        json_column_name: str,
        dry_run: bool,
        partition_col: str = None,
        clustering_fields: Union[str, List[str]] = None,
) -> None:
    """
    Appends a DataFrame with a native JSON column into a partitioned/clustered BigQuery table.
    Ensures existing data is not truncated.
    """
    table_id = f"{project_id}.{layer}.{table_name}"

    if dry_run:
        print(f"[DRY RUN - JSON] Would APPEND {len(df)} rows into {table_id}")
        print(f"[DRY RUN - JSON] Treating '{json_column_name}' as native BQ JSON type.")
        return

    client = bigquery.Client(project=project_id)

    # 1. Build schema, mapping the specific column to native JSON
    bq_schema = []
    for col in df.columns:
        if col == json_column_name:
            bq_schema.append(bigquery.SchemaField(col, "JSON"))
        else:
            # Fall back to your existing helper for standard columns
            bq_schema.append(bigquery.SchemaField(col, _pandas_dtype_to_bq(df[col].dtype)))

    # 2. Configure for streaming/appending monthly files safely
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",  # 👈 Crucial: protects existing months/boroughs
        schema=bq_schema,
        time_partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=partition_col,  # BigQuery will partition by this date column
        ),
        clustering_cols = [clustering_fields] if isinstance(clustering_fields, str) else clustering_fields  # BigQuery will cluster by borough
    )

    # 3. Execute the load
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()

    print(f"Successfully appended {job.output_rows} rows to {table_id}")
