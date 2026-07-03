import functools
from pathlib import Path

import pandas as pd

from utils.functions import standardise_names


def initialize_gold_skeleton(project_root: Path, pipe_name: str, grain_columns: list[str]) -> pd.DataFrame:
    skeleton_path = project_root / "data" / "D_gold" / pipe_name / "_skeleton.csv"

    if not skeleton_path.exists():
        raise FileNotFoundError(f"Expected baseline skeleton file not found at: {skeleton_path}")

    n_cols = len(grain_columns)
    try:
        skeleton_df = pd.read_csv(
            skeleton_path,
            usecols=list(range(n_cols)),
            dtype={i: str for i in range(n_cols)},
        )
    except Exception as e:
        raise ValueError(
            f"Failed to read skeleton CSV at {skeleton_path}. "
            f"Expected at least {n_cols} positional columns."
        ) from e

    skeleton_df.columns = grain_columns
    return skeleton_df


class GoldGrain:
    def __init__(self, project_root: Path, pipe_name: str, grain_columns: list[str]):
        # Read the skeleton (e.g., columns: ['borough_name', 'ons_code'])
        self.base_df = initialize_gold_skeleton(project_root, pipe_name, grain_columns)

    def _build_standardized_key(self, df: pd.DataFrame, cols: list[str]) -> pd.Series:
        """Helper to create a standardized single or composite string key."""
        parts = [standardise_names(df[col]) for col in cols]
        return parts[0] if len(parts) == 1 else functools.reduce(lambda a, b: a.str.cat(b, sep="||"), parts)

    def merge_metric(self, other_df: pd.DataFrame, join_mapping: dict[str, str], how: str = "left") -> None:
        """
        Merges an enrichment dataframe based on a dynamic mapping configuration.

        join_mapping: {"skeleton_col": "metric_df_col"}
                      e.g., {"borough_name": "BOROUGH"} or {"ons_code": "ons_code"}
        """
        skeleton_join_cols = list(join_mapping.keys())
        metric_join_cols = list(join_mapping.values())

        # 1. Generate temp keys for both sides matching just the configured columns
        base_temp_key = self._build_standardized_key(self.base_df, skeleton_join_cols)

        other_df = other_df.copy()
        other_df["_temp_merge_key"] = self._build_standardized_key(other_df, metric_join_cols)

        # 2. Drop the original joining columns from the incoming metric to avoid suffix collisions
        other_df = other_df.drop(columns=metric_join_cols, errors="ignore")

        # 3. Create a temporary version of base_df to safely merge on
        temp_base = self.base_df.copy()
        temp_base["_temp_merge_key"] = base_temp_key

        # 4. Perform the merge
        merged_res = pd.merge(temp_base, other_df, on="_temp_merge_key", how=how)

        # 5. Drop the temporary key and save back to base_df
        self.base_df = merged_res.drop(columns=["_temp_merge_key"])


class MetricAggregator:

    @staticmethod
    def process(df: pd.DataFrame, source_config: dict) -> pd.DataFrame:
        """Main entry point to transform incoming silver metrics."""
        processed_df = df.copy()

        # =========================================================================
        #  Conditional Aggregations
        # =========================================================================
        if "conditional_aggregations" in source_config:
            cond_rules = source_config["conditional_aggregations"]

            # Convert a single dict setup to a list for uniform processing loop
            if isinstance(cond_rules, dict):
                cond_rules = [cond_rules]

            for cond_meta in cond_rules:
                f_col = cond_meta["filter_column"]
                f_val = cond_meta["filter_value"]
                group_by_col = cond_meta["group_by"]

                if f_col in processed_df.columns:
                    # 1. Filter out the subset data dynamically
                    if f_col in processed_df.columns:
                        # 👇 NEW LOGIC: Standardize f_val to always be a list for .isin()
                        filter_vals = f_val if isinstance(f_val, list) else [f_val]

                        # 1. Filter out the subset data dynamically using .isin()
                        sub_df = processed_df[processed_df[f_col].isin(filter_vals)].copy()

                    # 2. Build the dynamic Pandas aggregation map and rename mapping
                    agg_dict = {}
                    rename_dict = {}

                    for src_col, ops in cond_meta.get("aggregations", {}).items():
                        if src_col in sub_df.columns:
                            op_name = ops["operation"]

                            # 👇 INTERCEPT CUSTOM OPERATIONS HERE
                            if op_name == "ofsted_average":
                                agg_dict[src_col] = MetricAggregator._calculate_ofsted_average
                            else:
                                agg_dict[src_col] = op_name  # Falls back to standard strings like 'sum'

                            rename_dict[src_col] = ops["output_name"]

                    # 3. Perform standard group-by math
                    if agg_dict:
                        sub_agg = sub_df.groupby(group_by_col, as_index=False).agg(agg_dict)
                        sub_agg = sub_agg.rename(columns=rename_dict)
                    else:
                        sub_agg = pd.DataFrame(columns=[group_by_col])

                    # 4. Handle the dynamic row counting element if requested
                    if "count_column_name" in cond_meta:
                        count_col_name = cond_meta["count_column_name"]
                        counts = sub_df.groupby(group_by_col).size().reset_index(name=count_col_name)
                        sub_agg = pd.merge(sub_agg, counts, on=group_by_col, how="outer")

                    # 5. Merge the completed subset metrics back into the main pipeline dataframe
                    processed_df = pd.merge(processed_df, sub_agg, on=group_by_col, how="left")

                    # 6. Safely clean up resulting missing NaN values with 0
                    all_new_cols = list(rename_dict.values())
                    if "count_column_name" in cond_meta:
                        all_new_cols.append(cond_meta["count_column_name"])

                    processed_df[all_new_cols] = processed_df[all_new_cols].fillna(0)

        # =========================================================================
        #  Row Filtering
        # =========================================================================
        if "filter_out" in source_config:
            filter_rules = source_config["filter_out"]

            # If a user passed a single dict, wrap it in a list so the loop handles it perfectly
            if isinstance(filter_rules, dict):
                filter_rules = [filter_rules]

            for rule in filter_rules:
                target_col = rule["column"]
                drop_values = rule["values"]

                if target_col in processed_df.columns:
                    # Keep only rows where the value is NOT in the dropped list
                    processed_df = processed_df[~processed_df[target_col].isin(drop_values)]

        # Step 1: Text-based aggregation (Looks for 'textual_col')
        text_summary_df = None
        if "textual_col" in source_config and "groupby_cols" in source_config:
            target_text_col = source_config["textual_col"]
            groupby_cols = source_config["groupby_cols"]

            text_summary_df = (
                processed_df.groupby(groupby_cols)[target_text_col]
                .agg(MetricAggregator._unique_comma_strings)
                .reset_index(name=f"transport_{target_text_col}")  # Dynamically creates e.g., 'transport_line_name'
            )

        # Step 2: Handle Standard GroupBy/Aggregations (Stops counts)
        if "groupby_cols" in source_config:
            if source_config.get("use_size"):
                processed_df = processed_df.groupby(source_config["groupby_cols"]).size().reset_index(name="size")
            else:
                aggregations = source_config.get("aggregations", {})
                processed_df = processed_df.groupby(source_config["groupby_cols"], as_index=False).agg(aggregations)

        # Step 3: Merge text summary back with numerical aggregations
        if text_summary_df is not None and "groupby_cols" in source_config:
            groupby_cols = source_config["groupby_cols"]
            processed_df = pd.merge(processed_df, text_summary_df, on=groupby_cols, how="left")

        # Step 4: Custom Math - Average and Deviation
        if "calculate_deviation" in source_config:
            calc_meta = source_config["calculate_deviation"]
            processed_df = MetricAggregator._compute_deviation(processed_df, calc_meta)

        # Step 5: Column Filtering
        if "keep_cols" in source_config:
            allowed_cols = list(source_config["keep_cols"])
            if "calculate_deviation" in source_config:
                allowed_cols.extend([calc_meta["new_avg_col"], calc_meta["new_dev_col"]])

            cols_to_keep = [c for c in allowed_cols if c in processed_df.columns]
            processed_df = processed_df[cols_to_keep]

        # Step 6: Handle Column Renaming
        if "rename_cols" in source_config:
            processed_df = processed_df.rename(columns=source_config["rename_cols"])

        return processed_df

    @staticmethod
    def _unique_comma_strings(series: pd.Series) -> str:
        """Splits comma-separated strings, flattens them, dedupes, and sorts them."""
        all_items = []
        for cell in series.dropna().astype(str):
            all_items.extend(part.strip() for part in cell.split(","))
        return ", ".join(sorted(set(all_items)))

    @staticmethod
    def _compute_deviation(df: pd.DataFrame, calc_meta: dict) -> pd.DataFrame:
        """Helper method using Pandas' native columns for the math operations."""
        target = calc_meta["target_col"]
        avg_col = calc_meta["new_avg_col"]
        dev_col = calc_meta["new_dev_col"]

        if target in df.columns:
            global_avg = df[target].mean()
            df[dev_col] = df[target] - global_avg

        return df

    @staticmethod
    def _calculate_ofsted_average(series: pd.Series) -> float:
        """Cleans Ofsted grading data, keeping only numeric values between 1 and 4, then averages them."""
        # 1. Force conversion to numeric data, turning strings/errors into NaN
        numeric_series = pd.to_numeric(series, errors="coerce")

        # 2. Filter keeping strictly values >= 1 and <= 4 (automatically drops NaNs)
        valid_scores = numeric_series[numeric_series.between(1, 4)]

        # 3. Return the mean, or NaN if a borough has zero valid ratings
        return valid_scores.mean() if not valid_scores.empty else pd.NA


class GoldMatrixPostProcessor:
    """Handles final cleanup, filling missing counts, and network consolidation on the final Gold Matrix."""

    @staticmethod
    def finalize(matrix_df: pd.DataFrame, text_col: str = "transport_line_name") -> pd.DataFrame:
        df = matrix_df.copy()

        # Step 1: Clean up numerical count columns (Fill missing data with 0)
        count_columns = [col for col in df.columns if "count" in col]
        df[count_columns] = df[count_columns].fillna(0).astype(int)

        # Step 2: Ensure text column exists and has no NaNs
        if text_col not in df.columns:
            df[text_col] = ""
        else:
            df[text_col] = df[text_col].fillna("")

        # Step 3: Apply row-by-row consolidation
        df[text_col] = df.apply(lambda row: GoldMatrixPostProcessor._append_networks(row, text_col), axis=1)

        return df

    @staticmethod
    def _append_networks(row: pd.Series, text_col: str) -> str:
        """Helper to evaluate presence of transit modes and format the final text string."""
        # Start with existing tube lines if they are present
        base_text = str(row[text_col]).strip()
        lines = [base_text] if base_text else []

        # Check other counts and append network names accordingly
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

        # Join everything cleanly with a comma, or flag as None if totally empty
        return ", ".join(lines) if lines else "None"
