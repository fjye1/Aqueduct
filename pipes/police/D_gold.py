from pathlib import Path

import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.transformations.aggregation import GoldGrain, MetricAggregator
from utils.transformations.filters import pivot_raw_police_categories

RAW_CATEGORIES = [
    "anti_social_behaviour",
    "bicycle_theft",
    "burglary",
    "criminal_damage_arson",
    "drugs",
    "other_crime",
    "other_theft",
    "possession_of_weapons",
    "public_order",
    "robbery",
    "shoplifting",
    "theft_from_the_person",
    "vehicle_crime",
    "violent_crime",
]

GOLD_PIPELINES = {
    "table_name": "police",

    "metric_sources": [
        {
            "file": "extraction_population.csv",
            "join_on": {
                "ons_code": "ons_code",
            },
            "keep_cols": [
                "ons_code",
                "population",
                "year"
            ],
            "pivot": False,
        },

        {
            "file": "extraction_crimes.csv",
            "join_on": {
                "borough_name": "borough",
                "year": "year"
            },
            "pivot": True,
            "keep_cols": [
                "borough",
                "year",
                *[f"{c}_annualised_rate" for c in RAW_CATEGORIES],
            ],

        },
    ],

    # Runs after all metric_sources have been joined
    "post_processing": {

        "sum_columns": [
            {
                "inputs": [
                    f"{c}_annualised_rate" for c in RAW_CATEGORIES
                ],
                "output_name": "total_crimes_annualised"
            }
        ],

        # Total crimes
        "calculate_ratio_per_1k": [
            {
                "numerator_col": "total_crimes_annualised",
                "denominator_col": "population",
                "output_col": "total_crimes_per_1000",
            },

            # Individual crime categories
            *[
                {
                    "numerator_col": f"{c}_annualised_rate",
                    "denominator_col": "population",
                    "output_col": f"{c}_per_1000",
                }
                for c in RAW_CATEGORIES
            ]
        ],

        "calculate_deviation": [
            {
                "target_col": "total_crimes_per_1000",
                "new_avg_col": "lon_avg_total_crimes_per_1000",
                "new_dev_col": "pct_diff_total_crimes_per_1000",
                "group_by": ["year"],
            },

            *[
                {
                    "target_col": f"{c}_per_1000",
                    "new_avg_col": f"lon_avg_{c}_per_1000",
                    "new_dev_col": f"pct_diff_{c}_per_1000",
                    "group_by": ["year"],
                }
                for c in RAW_CATEGORIES
            ]
        ],

        "calculate_yoy_change": [
            {
                "target_col": "total_crimes_per_1000",
                "group_col": "borough_name",
                "year_col": "year",
                "output_col": "yoy_pct_change_total_crimes_per_1000",
            },

            *[
                {
                    "target_col": f"{c}_per_1000",
                    "group_col": "borough_name",
                    "year_col": "year",
                    "output_col": f"yoy_pct_change_{c}_per_1000",
                }
                for c in RAW_CATEGORIES
            ]
        ],
    }
}

PIPE_NAME = "police"
PROJECT_ID = "roomreview-487913"
LAYER = "gold_layer_borough"
OUTPUT_NAME = "Aggregation"  # Suffix or prefix handler depending on your naming style
DRY_RUN = True  # Select False when ready to upload


def run_pipeline(PROJECT_ROOT: Path):
    gold = GoldGrain(project_root=PROJECT_ROOT, pipe_name=PIPE_NAME, grain_columns=["borough_name", "ons_code"])
    pipeline_config = GOLD_PIPELINES

    # 2. Extract, Transform, and Blend all metrics onto the skeleton
    for source in pipeline_config["metric_sources"]:
        folder = PROJECT_ROOT / "data" / "C_silver" / PIPE_NAME
        table_name = GOLD_PIPELINES["table_name"]
        metric_df = pd.read_csv(folder / source["file"])

        # Transform current metric file
        # 1. Pivot ONLY if the source explicitly requires it
        if source.get("pivot", False):
            metric_df, category_lookup = pivot_raw_police_categories(metric_df)

            # save the lookup once, e.g. alongside your gold output — it's reference data,
            # not something that needs deviation/yoy calcs run on it
            # Save lookup reference data
            lookup_path = PROJECT_ROOT / "data" / "D_gold" / PIPE_NAME / "category_lookup.csv"
            lookup_path.parent.mkdir(parents=True, exist_ok=True)
            category_lookup.to_csv(lookup_path, index=False)

        metric_df = MetricAggregator.process(metric_df, source_config=source)

        # Attach cleanly to skeleton
        gold.merge_metric(other_df=metric_df, join_mapping=source["join_on"], how="left")

    # =========================================================================
    # 3. Post-Processing (THE NEW STEP CALLED HERE)
    # =========================================================================
    print("Finalizing consolidated gold matrix data...")
    if "post_processing" in pipeline_config:
        gold.base_df = MetricAggregator.process(
            gold.base_df,
            source_config=pipeline_config["post_processing"]
        )
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
        dry_run=DRY_RUN  # Switch to False when moving out of testing
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
            dry_run=DRY_RUN  # Switch to False when moving out of testing
        )
    else:
        print("  Warning: 'year' column not found. Skipping latest-year CSV export.")
