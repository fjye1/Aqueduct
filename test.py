from pathlib import Path

# market_pressure_index
# from pipes.market_pressure_index.B_bronze import run_pipeline
# from pipes.market_pressure_index.C_silver import run_pipeline

# # council_Budget
# from pipes.council_budget.B_bronze import run_pipeline
# from pipes.council_budget.C_silver import run_pipeline

# Housing
# from pipes.housing.B_bronze import run_pipeline
# from pipes.housing.C_silver import run_pipeline

#Infrastructure
# from pipes.infrastructure.B_bronze import run_pipeline
# from pipes.infrastructure.C_silver import run_pipeline
# from pipes.infrastructure.D_gold import run_pipeline

#Education
# from pipes.education.B_bronze import run_pipeline
# from pipes.education.C_silver import run_pipeline
from pipes.education.D_gold import run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent

run_pipeline(PROJECT_ROOT)

# TODO extact pipes.market_pressure_index.C_silver into
# date, ons_area, avg_price, total_dwell
# 2024-01-01,E09000007,835092,5000,
# 2025-01-01,E09000007,835092,5000,

# test join
#TODO merge market pressure extraction into silver.
# import pandas as pd
#
# df_prices = pd.read_csv("data/C_silver/market_pressure_index/extraction_average_prices-2026-06-13.csv")
# df_dwellings = pd.read_csv("data/C_silver/market_pressure_index/extraction_dwelling_stock_local-2026-06-13.csv")
#
# # df_joined = df1.merge(df2, on="ons_code", how="left")
# #
# # df_joined.to_csv("out.csv", index=False)
# #
# # df_joined["date"] = pd.to_datetime(df_joined["date"])
# #
# # df = df_joined[
# #     (df_joined["date"].dt.month == 1) &
# #     (df_joined["date"].dt.day == 1)
# #  ].sort_values("date")
# #
# # df.to_csv("out2.csv", index=False)
#
# # 1. Ensure dates are datetime
# df_prices["date"] = pd.to_datetime(df_prices["date"])
#
# df_prices = df_prices[
#     (df_prices["date"].dt.month == 1) &
#     (df_prices["date"].dt.day == 1)
#     ].sort_values("date")
#
# # 2. Extract the year from the price date
# df_prices["year"] = df_prices["date"].dt.year
#
# # 3. Make sure your dwelling stock dataframe has a matching year column (integers)
# df_dwellings["year"] = df_dwellings["_sheet_name"].astype(int)  # assuming _sheet_name holds the year
#
# # 4. Merge on BOTH local authority code AND year
# df_joined = pd.merge(
#     df_prices,
#     df_dwellings,
#     left_on=["ons_code", "year"],
#     right_on=["ons_code", "year"],
#     how="left"
# )
#
# df_joined.to_csv("out3.csv", index=False)





# TODO Flatten JSon Crime report into Usable information
# ~~~~~~~~~~
# 18/06/2026 notes for flatterning the crime data json into stats about crime.
# ~~~~~~~~~~
# import json
# import pandas as pd
#
# # 1. Load your raw API JSON data
# # (Replace 'response.json' with your file or direct API response)
# with open('response.json', 'r') as f:
#     data = json.load(f)
#
# # 2. Flatten the nested JSON structure into a clean dataframe
# df = pd.json_normalize(data)
#
# # 3. Export the flattened data directly to a CSV file
# df.to_csv('london_crimes_flat.csv', index=False)
# print("CSV File successfully created!")
#
# # 4. Count the instances of each crime type
# print("\n--- Crime Type Counts ---")
# crime_counts = df['category'].value_counts()
# print(crime_counts)
#
# # (Optional) Save the aggregated counts to its own CSV
# crime_counts.to_csv('crime_type_summary.csv')
