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