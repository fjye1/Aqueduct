import pandas as pd
from utils.functions import count_by_borough, standardise_names
from pathlib import Path
from utils.big_query.import_big_query import load_into_bigquery


GOLD_PIPELINES = [
    {
        "table_name": "infrastructure",
        "baseline_source": {
            "file": "extraction_ptal_data.csv",
            "columns": ["ons_code", "BOROUGH", "avg_ptal", "ptal"]
        },
        "metric_sources": [
            {"file": "extraction_bus_stop_data.csv", "mode": "bus", "count_col": "bus_count"},
            {"file": "extraction_dlr_stop_data.csv", "mode": "dlr", "count_col": "dlr_count"},
            {"file": "extraction_elizabeth_stop_data.csv", "mode": "elizabeth", "count_col": "elizabeth_count"},
            {"file": "extraction_overground_stop_data.csv", "mode": "overground", "count_col": "overground_count"},
            {"file": "extraction_tramlink_stop_data.csv", "mode": "tramlink", "count_col": "tramlink_count"},
            # tube is the only source with a text_col, since its lines are explicitly named per row
            {"file": "extraction_tube_stop_data.csv", "mode": "tube", "count_col": "tube_count", "text_col": "line_name"},
        ]
    }
]


PIPE_NAME = "infrastructure"
PROJECT_ID = "roomreview-487913"
LAYER = "gold_layer_borough"
OUTPUT_NAME = "Aggregation"  # Suffix or prefix handler depending on your naming style


def run_pipeline(project_root: Path):
    folder = project_root / "data" / "C_silver" / PIPE_NAME

    for config in GOLD_PIPELINES:
        table_name = config["table_name"]
        print(f"\n--- Processing Gold Pipeline: {table_name} ---")

        # 1. Extract Baseline PTAL Data dynamically from config
        base_cfg = config["baseline_source"]
        ptal_file = folder / base_cfg["file"]

        if not ptal_file.exists():
            print(f"  [ERROR] Critical baseline file missing: {ptal_file}")
            continue

        print(f"  Processing baseline file: {ptal_file.name}")
        ptal_df = pd.read_csv(ptal_file)

        # Keep only the declared baseline columns
        ptai_subset = ptal_df[base_cfg["columns"]].copy()

        # Calculate deviations
        global_avg_ptal = ptai_subset["avg_ptal"].mean()
        ptai_subset["pct_diff_from_avg"] = ((ptai_subset["avg_ptal"] - global_avg_ptal) / global_avg_ptal) * 100

        # Collapse to a strict single Borough level matrix anchor
        gold_matrix = ptai_subset.groupby("BOROUGH").agg({
            "ons_code": "first",
            "ptal": "first",
            "avg_ptal": "mean",
            "pct_diff_from_avg": "mean"
        }).reset_index()

        # 2. Iterate through and merge each sub-metric file declared in the config
        for metric in config["metric_sources"]:
            metric_file = folder / metric["file"]

            if not metric_file.exists():
                print(f"  [WARN] Metric file not found: {metric_file.name}. Skipping.")
                continue

            print(f"  Merging counts from: {metric_file.name}")
            metric_df = pd.read_csv(metric_file)

            # Process using your existing summary callback logic
            summary_df = count_by_borough(metric_df, metric["count_col"])

            # If this source declares a text_col, harvest the unique line names per borough.
            # Cells may contain a comma-joined list of lines (e.g. interchange stations serve
            # multiple lines), so we split, flatten, and dedupe at the individual-line level
            # rather than deduping whole combo-strings.
            if "text_col" in metric:
                text_col_name = metric["text_col"]

                def unique_lines_for_group(series):
                    all_lines = []
                    for cell in series.dropna().astype(str):
                        all_lines.extend(part.strip() for part in cell.split(","))
                    unique_sorted = sorted(set(all_lines))
                    return ", ".join(unique_sorted)

                line_summary = metric_df.groupby("BOROUGH")[text_col_name].agg(unique_lines_for_group).reset_index()

                summary_df = pd.merge(summary_df, line_summary, on="BOROUGH", how="left")

            # Create the matching keys
            gold_matrix["merge_key"] = standardise_names(gold_matrix["BOROUGH"])
            summary_df["merge_key"] = standardise_names(summary_df["BOROUGH"])

            # Drop the raw 'BOROUGH' from summary so it doesn't duplicate as BOROUGH_y
            summary_df = summary_df.drop(columns=["BOROUGH"], errors="ignore")

            # Flawless left merge using the clean matching keys
            gold_matrix = pd.merge(gold_matrix, summary_df, on="merge_key", how="left")

            # Drop the temporary key so it's fresh for the next file in the loop
            gold_matrix = gold_matrix.drop(columns=["merge_key"])

        # 3. Dynamic clean up of missing counts (filling NaN with 0)
        count_columns = [col for col in gold_matrix.columns if "count" in col]
        gold_matrix[count_columns] = gold_matrix[count_columns].fillna(0).astype(int)

        # Ensure line_name column exists (handles edge case if tube file was entirely skipped)
        if "line_name" not in gold_matrix.columns:
            gold_matrix["line_name"] = ""
        else:
            gold_matrix["line_name"] = gold_matrix["line_name"].fillna("")

        # --- APPEND OTHER NETWORKS INTO LINE_NAME BASED ON COUNT > 0 ---
        def append_other_networks(row):
            lines = [row["line_name"]] if row["line_name"] else []

            if row.get("dlr_count", 0) > 0:
                lines.append("DLR")
            if row.get("tramlink_count", 0) > 0:
                lines.append("Tramlink")
            if row.get("elizabeth_count", 0) > 0:
                lines.append("Elizabeth")
            if row.get("overground_count", 0) > 0:
                lines.append("Overground")
            if row.get("bus_count", 0) > 0:
                lines.append("Bus")

            return ", ".join(lines) if lines else "None"

        gold_matrix["line_name"] = gold_matrix.apply(append_other_networks, axis=1)

        # 4. Save locally to Gold
        out_path = project_root / "data" / "D_gold" / PIPE_NAME / f"{OUTPUT_NAME}_{table_name}.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        gold_matrix.to_csv(out_path, index=False)
        print(f"  Saved Gold matrix to {out_path}")

        # 5. Upload to BigQuery
        print(f"  Uploading to BigQuery table: {PIPE_NAME}_{table_name}...")
        load_into_bigquery(
            project_id=PROJECT_ID,
            layer=LAYER,
            table_name=f"{PIPE_NAME}_{table_name}",
            df=gold_matrix,
            dry_run=True  # Switch to False when moving out of testing
        )