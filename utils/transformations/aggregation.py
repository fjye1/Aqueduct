import functools
from pathlib import Path

import pandas as pd
import numpy as np

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

                        filter_vals = f_val if isinstance(f_val, list) else [f_val]

                        # 1. Filter out the subset data dynamically using .isin()
                        sub_df = processed_df[processed_df[f_col].isin(filter_vals)].copy()

                    # 2. Build and apply aggregations. One grouped aggregation per requested
                    #    operation, since a single source column (e.g. ofsted_phase) can have
                    #    multiple named ops (e.g. several count_where's) needing distinct outputs.
                    sub_agg = None
                    all_new_cols = []  # <-- declare before the loop, not after

                    for src_col, ops in cond_meta.get("aggregations", {}).items():
                        if src_col not in sub_df.columns:
                            continue

                        op_list = ops if isinstance(ops, list) else [ops]

                        for op in op_list:
                            op_name = op["operation"]
                            output_name = op["output_name"]
                            all_new_cols.append(output_name)  # <-- track it here, every iteration

                            if op_name == "ofsted_average":
                                func = MetricAggregator._calculate_ofsted_average
                            elif op_name == "count_where":
                                target_value = op["value"]
                                func = lambda x, val=target_value: (x == val).sum()
                            else:
                                func = op_name

                            result = (
                                sub_df.groupby(group_by_col)[src_col]
                                .agg(func)
                                .reset_index(name=output_name)
                            )

                            sub_agg = result if sub_agg is None else pd.merge(
                                sub_agg, result, on=group_by_col, how="outer"
                            )

                    if sub_agg is None:
                        sub_agg = pd.DataFrame(columns=[group_by_col])

                    # 4. Handle the dynamic row counting element if requested
                    if "count_column_name" in cond_meta:
                        count_col_name = cond_meta["count_column_name"]
                        counts = sub_df.groupby(group_by_col).size().reset_index(name=count_col_name)
                        sub_agg = pd.merge(sub_agg, counts, on=group_by_col, how="outer")

                    # 5. Merge the completed subset metrics back into the main pipeline dataframe
                    processed_df = pd.merge(processed_df, sub_agg, on=group_by_col, how="left")

                    # 6. Safely clean up resulting missing NaN values with 0

                    if "count_column_name" in cond_meta:
                        all_new_cols.append(cond_meta["count_column_name"])

                    processed_df[all_new_cols] = processed_df[all_new_cols].fillna(0)

        # =========================================================================
        #  Row-wise Column Summing (flat addition, no grouping)
        #
        #  Different from the sum_columns branch inside conditional_aggregations:
        #  that one sums raw per-school columns THEN groups by borough. This one
        #  just adds together columns that are ALREADY at borough grain (e.g. two
        #  count columns produced above), row by row. No groupby involved.
        # =========================================================================
        if "sum_columns" in source_config:
            sum_rules = source_config["sum_columns"]

            if isinstance(sum_rules, dict):
                sum_rules = [sum_rules]

            for rule in sum_rules:
                inputs = rule["inputs"]
                output_name = rule["output_name"]

                missing = [c for c in inputs if c not in processed_df.columns]
                if missing:
                    raise KeyError(
                        f"sum_columns: cannot compute '{output_name}', "
                        f"missing input column(s): {missing}"
                    )

                processed_df[output_name] = processed_df[inputs].sum(axis=1)

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

        # =========================================================================
        #  Ratio / Percentage calculations (two columns -> one % column)
        #
        #  Different from calculate_deviation: this compares two columns WITHIN
        #  the same row (e.g. independent_school_count vs total_school_count).
        #  calculate_deviation compares one column against the dataset's own
        #  average across rows. Run this BEFORE calculate_deviation if you want
        #  to see how a ratio produced here stacks up against the London-wide
        #  average of that ratio (see calculate_deviation config below).
        # =========================================================================
        if "calculate_ratio" in source_config:
            ratio_rules = source_config["calculate_ratio"]

            if isinstance(ratio_rules, dict):
                ratio_rules = [ratio_rules]

            for calc_meta in ratio_rules:
                processed_df = MetricAggregator._compute_ratio_percentage(processed_df, calc_meta)

        # Step 4: Custom Math - Average and Deviation
        if "calculate_deviation" in source_config:
            dev_rules = source_config["calculate_deviation"]

            # Same convention as filter_out / conditional_aggregations: allow a
            # single dict for one deviation calc, or a list for several.
            if isinstance(dev_rules, dict):
                dev_rules = [dev_rules]

            for calc_meta in dev_rules:
                processed_df = MetricAggregator._compute_deviation(processed_df, calc_meta)

        # Step 4b: Custom Math - Year-on-Year Change
        if "calculate_yoy_change" in source_config:
            yoy_rules = source_config["calculate_yoy_change"]

            if isinstance(yoy_rules, dict):
                yoy_rules = [yoy_rules]

            for calc_meta in yoy_rules:
                processed_df = MetricAggregator._compute_yoy_change(processed_df, calc_meta)



        # Step 5: Handle Column Renaming
        if "rename_cols" in source_config:
            processed_df = processed_df.rename(columns=source_config["rename_cols"])

        # Safety net: force any column that should be numeric back to a real
        # numeric dtype before upload. Custom aggregation/ratio functions in
        # this file can produce object-dtype columns if they ever mix numpy
        # floats with pd.NA/None (e.g. via .replace(0, pd.NA) or returning
        # pd.NA from a custom agg) — pyarrow/BigQuery cannot infer a type for
        # that and the load fails. This does not invent or alter any real
        # values: to_numeric only converts values that are already unambiguous
        # numbers; anything else is left as-is (see errors= choice below).
        for col in processed_df.columns:
            if processed_df[col].dtype == "object" and col != "borough_name":
                try:
                    processed_df[col] = pd.to_numeric(processed_df[col])
                except (ValueError, TypeError):
                    pass  # genuinely non-numeric column (e.g. free text) — leave untouched
        # Step 6: Column Filtering
        if "keep_cols" in source_config:
            allowed_cols = list(source_config["keep_cols"])
            if "calculate_deviation" in source_config:
                dev_rules = source_config["calculate_deviation"]
                if isinstance(dev_rules, dict):
                    dev_rules = [dev_rules]
                for calc_meta in dev_rules:
                    allowed_cols.extend([calc_meta["new_avg_col"], calc_meta["new_dev_col"]])

        if "calculate_yoy_change" in source_config:
            yoy_rules = source_config["calculate_yoy_change"]
            if isinstance(yoy_rules, dict):
                yoy_rules = [yoy_rules]
            for calc_meta in yoy_rules:
                allowed_cols.append(calc_meta["output_col"])
        cols_to_keep = [c for c in allowed_cols if c in processed_df.columns]
        processed_df = processed_df[cols_to_keep]
        # TEMPORARY: skeleton join fans this table out to one row per school
        # (2,000 rows) even though every value in a row is a borough-level
        # aggregate, so all schools in a borough carry identical rows. Collapsing
        # here to enforce borough-grain output.
        #
        # NOTE: subset=None (default) means "duplicate across every column" —
        # deliberately NOT just borough_name, so if the skeleton join is ever
        # changed to bring in school-level data too, this will start leaving
        # genuinely different rows per borough instead of silently discarding
        # them.
        #
        # TODO: remove this once we rework the join to operate at the intended
        # grain (school-level in future).
        processed_df = processed_df.drop_duplicates()



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
        target = calc_meta["target_col"]
        avg_col = calc_meta["new_avg_col"]
        dev_col = calc_meta["new_dev_col"]
        group_by = calc_meta.get("group_by")  # None if not specified

        if target not in df.columns:
            return df

        if group_by:
            # Per-group average (e.g. one avg per year) instead of one global avg
            group_avg = df.groupby(group_by)[target].transform("mean")
            df[avg_col] = group_avg
            df[dev_col] = ((df[target] - group_avg) / group_avg) * 100
        else:
            # Existing behavior — unchanged for configs with no group_by
            global_avg = df[target].mean()
            df[dev_col] = ((df[target] - global_avg) / global_avg) * 100

        return df

    @staticmethod
    def _compute_ratio_percentage(df: pd.DataFrame, calc_meta: dict) -> pd.DataFrame:
        """Computes (numerator / denominator) * 100 as a new column."""
        numerator_col = calc_meta["numerator_col"]
        denominator_col = calc_meta["denominator_col"]
        output_col = calc_meta["output_col"]

        if numerator_col not in df.columns or denominator_col not in df.columns:
            return df

        # Use np.nan, not pd.NA, to guard against divide-by-zero. np.nan is
        # numpy-native so it keeps this column float64 throughout — pd.NA
        # silently upcasts the column to dtype "object" the moment it's
        # introduced via .replace(), which is exactly what broke the
        # BigQuery/pyarrow load on avg_quality_of_education previously, and
        # is doing the same thing here via a different code path.
        denominator = df[denominator_col].replace(0, np.nan)

        df[output_col] = (df[numerator_col] / denominator) * 100

        return df

    @staticmethod
    def _compute_yoy_change(df: pd.DataFrame, calc_meta: dict) -> pd.DataFrame:
        """
        Computes change vs. the previous year, within each group (e.g. per borough).

        calc_meta keys:
            target_col   - the column to compare year over year
            group_col    - the column identifying the entity (e.g. 'ons_code' or 'borough_name')
            year_col     - the column identifying the year (e.g. 'year')
            output_col   - name for the resulting % change column
        """
        target_col = calc_meta["target_col"]
        group_col = calc_meta["group_col"]
        year_col = calc_meta["year_col"]
        output_col = calc_meta["output_col"]

        if target_col not in df.columns or group_col not in df.columns or year_col not in df.columns:
            return df

        # Sort so each group's rows are in year order before diffing —
        # .diff()/.pct_change() operate on row ORDER, not on the year value itself,
        # so an unsorted dataframe would compare rows in whatever order they
        # happened to arrive from the merge, not chronological order.
        df = df.sort_values([group_col, year_col])

        df[output_col] = df.groupby(group_col)[target_col].pct_change() * 100

        return df

    @staticmethod
    def _calculate_ofsted_average(series: pd.Series) -> float:
        """Cleans Ofsted grading data, keeping only numeric values between 1 and 4, then averages them."""
        numeric_series = pd.to_numeric(series, errors="coerce")
        valid_scores = numeric_series[numeric_series.between(1, 4)]

        # Use float("nan") rather than pd.NA — np.nan is a native numpy float
        # and keeps the resulting column a clean float64 dtype when .agg()
        # combines results across groups. pd.NA is not numpy-native and
        # silently downgrades the whole column to dtype "object" the moment
        # it's mixed with real numpy.float64 values, which is exactly what
        # broke the BigQuery/pyarrow load.
        return valid_scores.mean() if not valid_scores.empty else float("nan")


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
