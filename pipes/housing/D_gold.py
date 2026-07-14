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
    "table_name": "housing",
    "metric_sources": [
        {
            "file": "extraction_housing_merged.csv",
            "join_on": {"ons_code": "ons_code"},
            "rename_cols": {
                "total": "affordable_additions",
                "Area": "borough_name",
            },
            "keep_cols": [
                "year",
                "ons_code",
                "total_dwellings",
                "affordable_additions",
                "band_d",
                "average_price",
                "net_additions",

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
                {
                    # TODO the assignment of total to affordable additions happens in the wrong order
                    "target_col": "total",
                    "new_avg_col": "lon_avg_affordable_additions",
                    "new_dev_col": "pct_diff_affordable_additions",
                    "group_by": ["year"],
                },
                {
                    "target_col": "total_dwellings",
                    "new_avg_col": "lon_avg_total_dwellings",
                    "new_dev_col": "pct_diff_total_dwellings",
                    "group_by": ["year"],
                },
                {
                    "target_col": "net_additions",
                    "new_avg_col": "lon_avg_net_additions",
                    "new_dev_col": "pct_diff_net_additions",
                    "group_by": ["year"],
                },
                {
                    "target_col": "band_d",
                    "new_avg_col": "lon_avg_band_d",
                    "new_dev_col": "pct_diff_band_d",
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
                {
                    "target_col": "total_dwellings",
                    "group_col": "ons_code",
                    "year_col": "year",
                    "output_col": "yoy_pct_change_total_dwellings",
                },
            ],

        },
    ]
}

PIPE_NAME = "housing"
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
        dry_run=True  # Switch to False when moving out of testing
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


