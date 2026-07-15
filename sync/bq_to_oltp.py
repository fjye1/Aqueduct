from sync.database import engine, SessionLocal, Base
from sync.models import Borough, BoroughEducation, BoroughHousing, BoroughInfrastructure, BoroughPolice, \
    BoroughHousingHistorical, BoroughPoliceHistorical
import pandas as pd

# 1. Grab your existing BigQuery client/engine setup from your utils!
# (Assuming you have a BQ engine in utils/big_query/...)
from utils.big_query.connection import bq_engine


def etl_pipeline():
    # Make sure the tables exist in PostgreSQL/MySQL
    # (Just like db.create_all() in Flask!)
    Base.metadata.create_all(bind=engine)

    print("Reading data from BigQuery...")
    # Read tables from BQ
    df_transport = pd.read_sql("SELECT * FROM `your_dataset.transport`", con=bq_engine)
    df_housing = pd.read_sql("SELECT * FROM `your_dataset.housing`", con=bq_engine)

    # Initialize a clean session
    session = SessionLocal()
    try:
        # Step A: Populate Boroughs
        b1 = df_transport[['ons_code', 'BOROUGH']].rename(columns={'BOROUGH': 'name'})
        b2 = df_housing[['ons_code', 'borough_name']].rename(columns={'borough_name': 'name'})
        unique_boroughs = pd.concat([b1, b2]).drop_duplicates(subset=['ons_code']).dropna()

        print("Syncing Borough entities...")
        for _, row in unique_boroughs.iterrows():
            borough = Borough(ons_code=row['ons_code'], name=row['name'])
            session.merge(borough)
        session.commit()

        # Step B: Sync Transport Metrics
        print("Syncing Transport metrics...")
        for _, row in df_transport.iterrows():
            record = BoroughInfrastructure(
                ons_code=row['ons_code'],
                ptal=row['ptal'],
                avg_ptal=row['avg_ptal'],
                pct_diff_from_avg=row['pct_diff_from_avg'],
                bus_count=row['bus_count'],
                dlr_count=row['dlr_count'],
                elizabeth_count=row['elizabeth_count'],
                overground_count=row['overground_count'],
                tramlink_count=row['tramlink_count'],
                tube_count=row['tube_count'],
                line_name=row['line_name']
            )
            session.merge(record)
        session.commit()

        # Step C: Sync Yearly Housing Stats
        print("Syncing Yearly Housing Metrics...")
        for _, row in df_housing.iterrows():
            # Check if this borough + year combination exists
            existing = session.query(BoroughHousingHistorical).filter_by(
                ons_code=row['ons_code'],
                year=int(row['year'])
            ).first()

            # Map the dataframe fields to your model fields
            housing_record_data = {
                "ons_code": row['ons_code'],
                "year": int(row['year']),
                "total_dwellings": row['total_dwellings'],
                "affordable_additions": row['affordable_additions'],
                "band_d": row['band_d'],
                "average_price": row['average_price'],
                "net_additions": row['net_additions'],
                "ratio_of_total_new_house_affordable": row['ratio_of_total_new_house_affordable'],
                "lon_average_price": row['lon_average_price'],
                "lon_avg_affordable_additions": row['lon_avg_affordable_additions'],
                "lon_avg_total_dwellings": row['lon_avg_total_dwellings'],
                "lon_avg_net_additions": row['lon_avg_net_additions'],
                "lon_avg_band_d": row['lon_avg_band_d'],
                "pct_diff_average_price": row['pct_diff_average_price'],
                "pct_diff_affordable_additions": row['pct_diff_affordable_additions'],
                "pct_diff_total_dwellings": row['pct_diff_total_dwellings'],
                "pct_diff_net_additions": row['pct_diff_net_additions'],
                "pct_diff_band_d": row['pct_diff_band_d'],
                "yoy_pct_change_average_price": row['yoy_pct_change_average_price'],
                "yoy_pct_change_total_dwellings": row['yoy_pct_change_total_dwellings']
            }

            if existing:
                for key, value in housing_record_data.items():
                    setattr(existing, key, value)
            else:
                new_record = BoroughHousingHistorical(**housing_record_data)
                session.add(new_record)

        session.commit()
        print("Downstream OLTP sync successfully completed!")

    except Exception as e:
        session.rollback()
        print(f"ETL pipeline failed: {e}")
        raise
    finally:
        session.close()
