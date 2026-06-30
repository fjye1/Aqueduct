from pathlib import Path
import pandas as pd
from utils.transformations.aggregation import GoldGrain, MetricAggregator, GoldMatrixPostProcessor

PROJECT_ROOT = Path(__file__).resolve().parent

# "join_on": { "SKELETON_COLUMN": "METRIC_SHEET_COLUMN" }

# "join_on": {
#     "borough_name": "BOROUGH",
#     "calendar_year": "Year_Reported"
# }

GOLD_PIPELINES = {
    "table_name": "infrastructure",
    # Notice: baseline_source is gone. Clean and sleek.
    "metric_sources": [
        {
            "file": "extraction_ptal_data.csv",
            "join_on": {"borough_name": "BOROUGH"},  # maps skeleton col -> this file's col
            "keep_cols": ["BOROUGH", "avg_ptal", "ptal"],

            # Use this define the function you want to use and define these parameters for use
            "calculate_deviation": {
                "target_col": "avg_ptal",  # Changed from ptal_score to match keep_cols
                "new_avg_col": "lon_avg_ptal_score",
                "new_dev_col": "ptal_deviation_from_avg",
            }
        },
        # This file only has ONS Code
        {
            "file": "extraction_bus_stop_data.csv",
            "join_on": {"borough_name": "BOROUGH"},  # maps skeleton col -> this file's col
            "groupby_cols": ["BOROUGH"],

            # use_size = True means: don't rely on any single column
            # (stop_name, postcode, etc.) being fully populated.
            # Just count rows per BOROUGH group. Avoids undercounting
            # caused by nulls in whichever column we'd otherwise count.
            "use_size": True,
            "rename_cols": {
                "size": "bus_count"  # .size() always outputs a col named "size"
            }
        },
        {
            "file": "extraction_elizabeth_stop_data.csv",
            "join_on": {"borough_name": "BOROUGH"},
            "groupby_cols": ["BOROUGH"],
            "use_size": True,
            "rename_cols": {
                "size": "elizabeth_count"
            }
        },
        {
            "file": "extraction_overground_stop_data.csv",
            "join_on": {"borough_name": "BOROUGH"},
            "groupby_cols": ["BOROUGH"],
            "use_size": True,
            "rename_cols": {
                "size": "overground_count"
            }
        },
        {
            "file": "extraction_tramlink_stop_data.csv",
            "join_on": {"borough_name": "BOROUGH"},
            "groupby_cols": ["BOROUGH"],
            "use_size": True,
            "rename_cols": {
                "size": "tramlink_count"
            }
        },
        {
            "file": "extraction_tube_stop_data.csv",
            "join_on": {"borough_name": "BOROUGH"},
            "groupby_cols": ["BOROUGH"],
            "use_size": True,
            # Use textual col if you want to extract data that is presented in a string / "string, string" format
            "textual_col": "line_name",
            "rename_cols": {
                "size": "tube_count"
            }
        },

    ]
}

PIPE_NAME = "infrastructure"
PROJECT_ID = "roomreview-487913"
LAYER = "gold_layer_borough"
OUTPUT_NAME = "Aggregation"  # Suffix or prefix handler depending on your naming style





gold = GoldGrain(project_root=PROJECT_ROOT, pipe_name=PIPE_NAME, grain_columns=["borough_name", "ons_code"])
pipeline_config = GOLD_PIPELINES

# 2. Extract, Transform, and Blend all metrics onto the skeleton
for source in pipeline_config["metric_sources"]:
    folder = PROJECT_ROOT / "data" / "C_silver" / PIPE_NAME
    metric_df = pd.read_csv(folder / source["file"])

    # Transform current metric file
    metric_df = MetricAggregator.process(metric_df, source_config=source)

    # Attach cleanly to skeleton
    gold.merge_metric(other_df=metric_df, join_mapping=source["join_on"], how="left")

# =========================================================================
# 3. Post-Processing (THE NEW STEP CALLED HERE)
# =========================================================================
print("Finalizing consolidated gold matrix data...")
gold.base_df = GoldMatrixPostProcessor.finalize(gold.base_df, text_col="transport_line_name")

# 4. Save final consolidated table
gold.base_df.to_csv("test_test_1", index=False)
print(gold.base_df)