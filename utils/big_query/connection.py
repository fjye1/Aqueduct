from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def big_query_engine(project_id: str) -> Engine:
    """
    Creates a SQLAlchemy Engine for BigQuery.
    Automatically uses your local gcloud CLI login (Application Default Credentials).
    """
    # No credentials path or service account needed!
    # Just the project ID is enough to trigger Google's automatic auth lookup.
    connection_string = f"bigquery://{project_id}"

    print(f"Connecting to BigQuery project '{project_id}' using local CLI credentials...")
    return create_engine(connection_string)