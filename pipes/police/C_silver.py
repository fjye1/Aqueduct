import json
from pathlib import Path

import numpy as np
import pandas as pd
from utils.transformations.filters import process_crime_df
from utils.big_query.import_big_query import load_into_bigquery

PIPE_NAME = "police"
PROJECT_ID = "roomreview-487913"
LAYER = "silver_layer"
OUTPUT_NAME = "extraction"
table_name = "crimes"


def run_pipeline(project_root: Path):
    base_path = project_root / f"data/A_raw/{PIPE_NAME}/police_crimes"
    results = []

    for year_folder in base_path.glob("year=*"):
        year = int(year_folder.name.split("=")[1])

        for month_folder in year_folder.glob("month=*"):
            for json_file in month_folder.glob("*.json"):

                borough = json_file.stem  # "Barking & Dagenham"

                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                df = pd.json_normalize(data)

                counts = df["category"].value_counts()

                month = int(month_folder.name.split("=")[1])

                for category, count in counts.items():
                    results.append({
                        "year": year,
                        "month": month,
                        "borough": borough,
                        "category": category,
                        "count": count
                    })

    monthly_counts = pd.DataFrame(results)

    df = (
        monthly_counts
        .groupby(["year", "borough", "category"], as_index=False)
        .agg(
            total_count=("count", "sum"),
            months_present=("month", "nunique")
        )
    )
    # Safe division: replaces 0 months with NaN to avoid errors or infinite values
    df["annualised_rate"] = (
                                    df["total_count"] / df["months_present"].replace(0,
                                                                                     np.nan)
                            ) * 12

    final_df = process_crime_df(df)
    out_path = project_root / "data" / "C_silver" / PIPE_NAME / f"{OUTPUT_NAME}_{table_name}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(out_path, index=False)

    if not final_df.empty:
        print(f"  Uploading to BigQuery table: {PIPE_NAME}_{table_name}...")
        load_into_bigquery(
            project_id=PROJECT_ID,
            layer=LAYER,
            table_name=f"{PIPE_NAME}_{table_name}",
            df=final_df,
            dry_run=True
        )

    else:
        print(f"  [WARN] No data processed for pipeline: {table_name}")
