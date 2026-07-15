from typing import List, Union
import pandas as pd
from google.cloud import bigquery
from utils.big_query.connection import big_query_engine
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

    # 1. Initialize SQLAlchemy Engine and extract its underlying BigQuery Client connection
    engine = big_query_engine(project_id)

    # This reaches through the SQLAlchemy wrapper to get the configured client
    client = engine.dialect.dbapi.connect()._client

    # Allow _pandas_dtype_to_bq to determine type
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
    Bypasses PyArrow limitations using load_table_from_json.
    """
    table_id = f"{project_id}.{layer}.{table_name}"

    # --- FIX: Early exit local dry-run logic ---
    if dry_run:
        print(f"[DRY RUN - JSON] Would APPEND {len(df)} rows into {table_id}")
        print(f"[DRY RUN - JSON] Treating '{json_column_name}' as native BQ JSON type.")
        if partition_col: print(f"[DRY RUN] Partitioning by column: {partition_col}")
        if clustering_fields: print(f"[DRY RUN] Clustering by fields: {clustering_fields}")
        print(f"[DRY RUN] Columns: {list(df.columns)}")
        with pd.option_context(
                'display.max_columns', None,
                'display.max_colwidth', None,
                'display.width', 1000
        ):
            print(f"[DRY RUN] Sample:\n{df.head(2)}")
        return

    # 1. Initialize SQLAlchemy Engine and extract its underlying BigQuery Client connection
    engine = big_query_engine(project_id)
    client = engine.dialect.dbapi.connect()._client

    # 2. Build schema, mapping specific columns explicitly
    bq_schema = []
    for col in df.columns:
        if col == json_column_name:
            bq_schema.append(bigquery.SchemaField(col, "JSON"))
        elif col == partition_col:
            bq_schema.append(bigquery.SchemaField(col, "DATE"))
        else:
            bq_schema.append(bigquery.SchemaField(col, _pandas_dtype_to_bq(df[col].dtype)))

    # 3. Configure the Load Job
    config_args = {
        "write_disposition": "WRITE_APPEND",
        "create_disposition": "CREATE_IF_NEEDED",
        "schema": bq_schema
    }

    if partition_col:
        config_args["time_partitioning"] = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=partition_col,
        )

    if clustering_fields:
        config_args["clustering_fields"] = (
            [clustering_fields] if isinstance(clustering_fields, str) else clustering_fields
        )

    job_config = bigquery.LoadJobConfig(**config_args)

    # 4. Format DataFrame into JSON-safe dictionary structures
    df_to_json = df.copy()
    if partition_col and partition_col in df_to_json.columns:
        # Convert Pandas timestamp objects into standard 'YYYY-MM-DD' text strings
        df_to_json[partition_col] = pd.to_datetime(df_to_json[partition_col]).dt.strftime('%Y-%m-%d')

    json_rows = df_to_json.to_dict(orient="records")

    # 5. Execute the load using BigQuery's native JSON loader
    job = client.load_table_from_json(json_rows, table_id, job_config=job_config)
    job.result()  # Wait for load to finish

    print(f"Successfully appended {len(df)} rows to {table_id}")