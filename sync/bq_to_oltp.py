
import pandas as pd
from sync.database import Base, engine as pg_engine
from utils.big_query.connection import big_query_engine  # Importing your existing function
import os
# --- Configuration ---
PROJECT_ID = os.environ.get("PROJECT_ID")
DATASET_ID = "gold_layer_borough"

# Initialize BigQuery engine
bq_engine = big_query_engine(PROJECT_ID)

# List tables in order (Parent table FIRST for Foreign Key integrity)
tables_to_sync = [
    "district_table",
    "education_london",
    "rent_quarterly",
    "housing_price_quarterly",
    "housing_stock_annual",
    "police_police",
]


def sync_all_tables():
    # 1. Ensure all PostgreSQL tables exist based on your models
    Base.metadata.create_all(bind=pg_engine)

    # 2. Extract from BQ and Load into PostgreSQL
    for table in tables_to_sync:
        print(f" Reading '{table}' from BigQuery...")

        query = f"SELECT * FROM `{PROJECT_ID}.{DATASET_ID}.{table}`"
        df = pd.read_sql(query, con=bq_engine)

        print(
            f" Transferring {len(df)} rows to PostgreSQL '{table}' table..."
        )

        df.to_sql(
            name=table,
            con=pg_engine,
            if_exists="append",  # insertion fails if the tables already exist.
            index=False,
            chunksize=5000,
            method="multi",  # Efficient bulk insertion for Postgres
        )

        print(f" Finished syncing {table}!\n")


if __name__ == "__main__":
    sync_all_tables()