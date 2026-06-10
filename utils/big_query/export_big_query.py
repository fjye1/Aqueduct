from utils.helper import sanitise
from datetime import datetime
from google.cloud import bigquery

"""
This function exports data from Big Query down to your local machine

Big query -> local machine. 
"""

def export_big_query(project_id: str, layer: str, table_name: str) -> None:
    """
    Exports a BigQuery table to a sanitized, timestamped CSV.
    """
    client = bigquery.Client()

    # 1. Prepare Query
    query = f"""
        SELECT *
        FROM `{project_id}.{layer}.{table_name}`
        ORDER BY _row_number
    """

    # 2. Extract Data
    print(f"Fetching data from {table_name}...")
    df_exported = client.query(query).to_dataframe()


    # 3. sanitise file name and create time stamp for extraction.

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = f"{sanitise(project_id)}_{sanitise(layer)}_{sanitise(table_name)}_{timestamp}.csv"

    # 4. Save
    df_exported.to_csv(clean_name, index=False)
    print(f"Successfully exported {len(df_exported)} rows to: {clean_name}")

# Example usage:
# big_query_export("my-project", "raw_data", "budget_table")