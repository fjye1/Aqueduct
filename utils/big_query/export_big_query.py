from utils.helper import sanitise
from datetime import datetime
import pandas as pd
from utils.big_query.connection import big_query_engine
"""
This function exports data from Big Query down to your local machine

Big query -> local machine. 
"""
#TODO Write a test for this function


def export_big_query(project_id: str, layer: str, table_name: str) -> None:
    """
    Exports a BigQuery table to a sanitized, timestamped CSV using SQLAlchemy.
    """
    # Simply pass the project ID. SQLAlchemy will find your local gcloud login!
    engine = big_query_engine(project_id)

    query = f"""
        SELECT *
        FROM `{project_id}.{layer}.{table_name}`
        ORDER BY _row_number
    """

    print(f"Fetching data from {layer}.{table_name}...")
    with engine.connect() as connection:
        df_exported = pd.read_sql_query(query, con=connection)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = f"{sanitise(project_id)}_{sanitise(layer)}_{sanitise(table_name)}_{timestamp}.csv"

    df_exported.to_csv(clean_name, index=False)
    print(f"Successfully exported {len(df_exported)} rows to: {clean_name}")

# Example usage:
# big_query_export("my-project", "raw_data", "budget_table")