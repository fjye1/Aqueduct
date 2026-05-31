import inspect
from google.cloud import bigquery
# TODO add this to a proper config
from config import PROJECT, LAYER


# table: target BigQuery table name
# source: GCS URI of the CSV file
# layer: defaults to config.LAYER, override if needed
# client: optional shared BigQuery client, creates its own if not provided
def load_data(table: str, source: str, layer=LAYER, client: bigquery.Client = None):
    client = client or bigquery.Client(project=PROJECT)
    func_name = inspect.currentframe().f_code.co_name

    sql = f"""
    -- drop anything in the table before starting
    TRUNCATE TABLE `{PROJECT}.{layer}.{table}`;
    -- load fresh data
    LOAD DATA INTO `{PROJECT}.{layer}.{table}`
    FROM FILES(
        format='CSV',
        uris=['{source}'],
        skip_leading_rows=1
    );
    """

    try:
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        for statement in statements:
            job = client.query(statement)
            job.result()
        print(f"Success {func_name} completed — table: {table}, layer: {layer}")
    except Exception as e:
        print(f"Failure {func_name} failed: {e}")
        raise


def age_london_five_year_bands(client: bigquery.Client = None):
    client = client or bigquery.Client(project=PROJECT)
    func_name = inspect.currentframe().f_code.co_name

    sql = f"""
    DROP TABLE IF EXISTS `{PROJECT}.{LAYER}.{func_name}`;
    CREATE TABLE `{PROJECT}.{LAYER}.{func_name}`
    (
      year INT64,
      borough_name STRING,
      ons_code STRING,
      all_ages INT64,
      age_0_4 INT64,
      aged_5_9 INT64,
      aged_10_14 INT64,
      aged_15_19 INT64,
      aged_20_24 INT64,
      aged_25_29 INT64,
      aged_30_34 INT64,
      aged_35_39 INT64,
      aged_40_44 INT64,
      aged_45_49 INT64,
      aged_50_54 INT64,
      aged_55_59 INT64,
      aged_60_64 INT64,
      aged_65_69 INT64,
      aged_70_74 INT64,
      aged_75_79 INT64,
      aged_80_84 INT64,
      aged_85 INT64,
      aged_90 INT64
    )
    CLUSTER BY year, borough_name;
    """

    try:
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        for statement in statements:
            job = client.query(statement)
            job.result()
        print(f"Success {func_name} completed successfully")
    except Exception as e:
        print(f"Failure {func_name} failed: {e}")
        raise