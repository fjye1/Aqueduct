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
    "table_name": "education",
    # Notice: baseline_source is gone. Clean and sleek.
    "metric_sources": [
        {
            "file": "extraction_school_with_ofsted.csv",
            "join_on": {"borough_name": "borough_name"},  # maps skeleton col -> this file's col
            "filter_out": [
                {
                    "column": "status",
                    "values": ["Closed"]
                },
                {
                    "column": "establishment_group",
                    "values": ["Online provider", "Other types", "Special schools", "Universities"]

                },
                {
                    "column": "type_of_establishment",
                    "values": ["Pupil referral unit"]
                },

            ],
            "conditional_aggregations": [
                {
                    "filter_column": "establishment_group",
                    "filter_value": "Independent schools",
                    "group_by": "borough_name",
                    "count_column_name": "independent_school_count",
                    "aggregations": {
                        "pupil_capacity": {"operation": "sum", "output_name": "independent_pupil_capacity"},
                        "current_pupils": {"operation": "sum", "output_name": "independent_current_pupils"}
                    }
                },
                {
                    "filter_column": "establishment_group",  # Using group or type depending on your column mapping
                    "filter_value": [
                        "Local authority maintained schools",
                        "Free schools",
                        "Colleges",
                        "Academies"
                    ],
                    "group_by": "borough_name",
                    "count_column_name": "public_funded_school_count",  # Kept lowercase snake_case to match pattern
                    "aggregations": {
                        "pupil_capacity": {"operation": "sum", "output_name": "public_funded_pupil_capacity"},
                        "current_pupils": {"operation": "sum", "output_name": "public_funded_current_pupils"},
                        "quality_of_education": {"operation": "ofsted_average", "output_name": "avg_quality_of_education"},
                        "behaviour_and_attitudes": {"operation": "ofsted_average", "output_name": "avg_behaviour_and_attitudes"},
                        "personal_development": {"operation": "ofsted_average", "output_name": "avg_personal_development"},
                        "effectiveness_of_leadership_and_management": {"operation": "ofsted_average", "output_name": "avg_effectiveness_of_leadership_and_management"},
                    }
                }
            ],

            # "keep_cols": ["borough_name", "ons_code", "type_of_establishment", "establishment_group", "status",
            #               "stat_low_age", "stat_high_age", "pupil_capacity", "current_pupils", "quality_of_education",
            #               "behaviour_and_attitudes", "personal_development",
            #               "effectiveness_of_leadership_and_management"],

        },
    ]
}

PIPE_NAME = "education"
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
