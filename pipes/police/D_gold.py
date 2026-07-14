from pathlib import Path

import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.transformations.aggregation import GoldGrain, MetricAggregator


# "join_on": { "SKELETON_COLUMN": "METRIC_SHEET_COLUMN" }

# "join_on": {
#     "borough_name": "BOROUGH",
#     "calendar_year": "Year_Reported"
# }

GOLD_PIPELINES = {
    "table_name": "police",
    "metric_sources": [
        {
            "file": "extraction_crimes.csv",
            "join_on": {"BOROUGH": "borough"},
            "rename_cols": {
                "total": "affordable_additions",
                "borough": "borough_name",
            },
            "keep_cols": [
                "year",
                "ons_code",


            ],
            "calculate_ratio": [
                # TODO the assignment of total to affordable additions happens in the wrong order
                {
                    "numerator_col": "total",
                    "denominator_col": "net_additions",
                    "output_col": "ratio_of_total_new_house_affordable",
                },
            ],

            "calculate_deviation": [
                {
                    "target_col": "average_price",
                    "new_avg_col": "lon_average_price",
                    "new_dev_col": "pct_diff_average_price",
                    "group_by": ["year"],
                },


            ],
            "calculate_yoy_change": [
                {
                    "target_col": "average_price",
                    "group_col": "ons_code",
                    "year_col": "year",
                    "output_col": "yoy_pct_change_average_price",
                },

            ],

        },
    ]
}

PIPE_NAME = "police"
PROJECT_ID = "roomreview-487913"
LAYER = "gold_layer_borough"
OUTPUT_NAME = "Aggregation"  # Suffix or prefix handler depending on your naming style


def run_pipeline(PROJECT_ROOT: Path):
    gold = GoldGrain(project_root=PROJECT_ROOT, pipe_name=PIPE_NAME, grain_columns=["borough_name", "ons_code"])
    pipeline_config = GOLD_PIPELINES

    # 2. Extract, Transform, and Blend all metrics onto the skeleton
    for source in pipeline_config["metric_sources"]:
        folder = PROJECT_ROOT / "data" / "C_silver" / PIPE_NAME
        table_name = GOLD_PIPELINES["table_name"]
        metric_df = pd.read_csv(folder / source["file"])

        # Transform current metric file
        metric_df = MetricAggregator.process(metric_df, source_config=source)

        # Attach cleanly to skeleton
        gold.merge_metric(other_df=metric_df, join_mapping=source["join_on"], how="left")

    # =========================================================================
    # 3. Post-Processing (THE NEW STEP CALLED HERE)
    # =========================================================================
    print("Finalizing consolidated gold matrix data...")

    # 4. Save final consolidated table
    out_path = PROJECT_ROOT / "data" / "D_gold" / PIPE_NAME / f"{OUTPUT_NAME}_{table_name}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gold.base_df.to_csv(out_path, index=False)
    print(f"  Saved Gold matrix to {out_path}")

    # 5. Upload to BigQuery
    print(f"  Uploading to BigQuery table: {PIPE_NAME}_{table_name}...")
    load_into_bigquery(
        project_id=PROJECT_ID,
        layer=LAYER,
        table_name=f"{PIPE_NAME}_{table_name}",
        df=gold.base_df,
        dry_run=False  # Switch to False when moving out of testing
    )

    # =========================================================================
    # 4b. Save Secondary CSV (Latest Year Only)
    # =========================================================================
    if "year" in gold.base_df.columns:
        latest_year = gold.base_df["year"].max()
        latest_df = gold.base_df[gold.base_df["year"] == latest_year]

        latest_out_path = PROJECT_ROOT / "data" / "D_gold" / PIPE_NAME / f"{OUTPUT_NAME}_{table_name}_latest.csv"
        latest_df.to_csv(latest_out_path, index=False)
        print(f"  Saved Latest Year ({latest_year}) subset to {latest_out_path}")
        # 5. Upload to BigQuery
        print(f"  Uploading to BigQuery table: {PIPE_NAME}_{table_name}_latest")
        load_into_bigquery(
            project_id=PROJECT_ID,
            layer=LAYER,
            table_name=f"{PIPE_NAME}_{table_name}_latest",
            df=latest_df,
            dry_run=False  # Switch to False when moving out of testing
        )
    else:
        print("  Warning: 'year' column not found. Skipping latest-year CSV export.")













def process_crime_record(api_record):
    """
    Takes a raw crime record from the police API and appends
    our custom analytical category.
    """
    raw_category = api_record.get("category", "other-crime")

    # Enrich the record with your custom bucket
    api_record["analytical_category"] = CRIME_BUCKETS.get(raw_category, "Other")
    return api_record


# TODO Flatten JSon Crime report into Usable information
# ~~~~~~~~~~
# 18/06/2026 notes for flatterning the crime data json into stats about crime.
# ~~~~~~~~~~
import json
from pathlib import Path

import pandas as pd



PROJECT_ROOT = Path(__file__).resolve().parents[2]
file_path = (
        PROJECT_ROOT
        / "data"
        / "A_raw"
        / "police"
        / "police_crimes"
        / "year=2026"
        / "month=05"
        / "Croydon.json"
)

print(file_path)
print(file_path.exists())
print(PROJECT_ROOT)

with open(file_path, 'r') as f:
    data = json.load(f)
# 2. Flatten the nested JSON structure into a clean dataframe
df = pd.json_normalize(data)

# 3. Export the flattened data directly to a CSV file
df.to_csv('london_crimes_flat.csv', index=False)
print("CSV File successfully created!")

# 4. Count the instances of each crime type
print("\n--- Crime Type Counts ---")
crime_counts = df['category'].value_counts()
print(crime_counts)
# (Optional) Save the aggregated counts to its own CSV
crime_counts.to_csv('crime_type_summary.csv')

outcomes = pd.json_normalize(df["outcome_status"])
outcomes = outcomes.rename(columns={
    "category": "outcome_status.category",
    "date": "outcome_status.date"
})
# --- Your existing code leaves off here ---
df = pd.concat([df.drop(columns=["outcome_status"]), outcomes], axis=1)
df.to_csv('crime_outcomes.csv', index=False)

# =====================================================================
# NEW: Create the Outcome Summary CSV
# =====================================================================

# 1. Fill missing outcomes so active investigations aren't excluded from counts
df['outcome_status.category'] = df['outcome_status.category'].fillna('Under Investigation / No Outcome')

print("\n--- Crime Outcome Counts ---")
# 2. Group, count, and immediately format into a structured DataFrame
outcome_counts = (
    df['outcome_status.category']
    .value_counts()
    .reset_index(name='count')  # Names the summary column 'count'
)

# Print it out to your terminal console so you can see it right away
print(outcome_counts)

# 3. Export the clean aggregated outcome table to its own CSV
outcome_counts.to_csv('outcome_types_summary.csv', index=False)
print("\n✅ 'outcome_types_summary.csv' successfully created!")

# TODO column suggestions



# ons_area, year,
#
# total_crime_count, lon_avg_total_crime_count, pct_diff_total_crime_count, yoy_pct_change_total_crime_count,
#
# violent_serious_crime_count, lon_avg_violent_serious_crime_count, pct_diff_violent_serious_crime_count, yoy_pct_change_violent_serious_crime_count,
#
# property_theft_crime_count, lon_avg_property_theft_crime_count, pct_diff_property_theft_crime_count, yoy_pct_change_property_theft_crime_count,
#
# qol_public_order_crime_count, lon_avg_qol_public_order_crime_count, pct_diff_qol_public_order_crime_count, yoy_pct_change_qol_public_order_crime_count,
#
# other_crime_count, lon_avg_other_crime_count, pct_diff_other_crime_count, yoy_pct_change_other_crime_count