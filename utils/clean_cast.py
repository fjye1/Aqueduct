import numpy as np
import pandas as pd

# TODO build Test for this function very big test
def clean_and_cast(series, col_type, col_name=None):
    """Clean and cast a pandas Series to the specified type.

    Invalid values become pd.NA / NaT.
    Prints unexpected values that fail conversion.
    """
    original = series.copy()

    # Standardise nulls
    series = (
        series.astype(str)
        .str.strip()
        .replace(
            {
                "": pd.NA,
                "nan": pd.NA,
                "None": pd.NA,
                "null": pd.NA,
                "[x]": pd.NA,
                "[c]": pd.NA,
                "[z]": pd.NA,
                "-": pd.NA,
            }
        )
    )

    # ── STRING ────────────────────────────────────────────────
    if col_type == "STRING":
        return series

    # ── INTEGER ───────────────────────────────────────────────
    elif col_type == "INTEGER":
        # Robust string cleaning: clear out pd.NA temporarily to keep string regex clean
        cleaned = (
            series.fillna("")
            .astype(str)
            .str.replace(r"[^\d.-]", "", regex=True)
        )
        cleaned = cleaned.replace({"": np.nan, "nan": np.nan})

        # Coerce to numbers (this guarantees a clean float64/int64 array, never 'object')
        numeric = pd.to_numeric(cleaned, errors="coerce")

        # Track items that failed parsing entirely (excluding intentional nulls)
        bad_mask = (
            numeric.isna()
            & original.notna()
            & ~original.isin(
                ["", "nan", "None", "null", "[x]", "[c]", "[z]", "-"]
            )
        )
        if bad_mask.any():
            print(
                f"[DEBUG] INTEGER parsing failed to read these raw values in {col_name}: "
                f"{original[bad_mask].unique()}"
            )

        # Defensive wrapper to catch exact bad values if the cast breaks
        try:
            return numeric.astype("Int64")
        except Exception as e:
            print(
                f"\n[CRITICAL DEBUG] .astype('Int64') failed for column '{col_name}'."
            )
            print(f"-> Pandas series dtype after parsing: {numeric.dtype}")

            # Check if there are decimal entries (e.g., 12.5) preventing integer assignment
            decimals = numeric[numeric.notna() & (numeric % 1 != 0)]
            if not decimals.empty:
                print(
                    f"-> Found fractional decimal values causing failure: {decimals.unique()[:10]}"
                )
                print(
                    "   (Tip: Change type to FLOAT or round values before converting to INTEGER)"
                )

            if numeric.dtype == "object":
                print(
                    f"-> Series remained an object array. Sample values: {numeric.unique()[:10]}"
                )
            raise e

    # ── FLOAT ─────────────────────────────────────────────────
    elif col_type == "FLOAT":
        cleaned = (
            series.fillna("")
            .astype(str)
            .str.replace(r"[^\d.-]", "", regex=True)
        )
        cleaned = cleaned.replace({"": np.nan, "nan": np.nan})

        numeric = pd.to_numeric(cleaned, errors="coerce")

        bad_mask = (
            numeric.isna()
            & original.notna()
            & ~original.isin(
                ["", "nan", "None", "null", "[x]", "[c]", "[z]", "-"]
            )
        )
        if bad_mask.any():
            print(
                f"[DEBUG] FLOAT parsing failed to read these raw values in {col_name}: "
                f"{original[bad_mask].unique()}"
            )
        return numeric

    # ── DATE / DATETIME / TIMESTAMP ───────────────────────────
    elif col_type in ("DATE", "DATETIME", "TIMESTAMP"):
        try:
            parsed = pd.to_datetime(series, errors="coerce")
            bad_mask = (
                parsed.isna()
                & original.notna()
                & ~original.isin(
                    ["", "nan", "None", "null", "[x]", "[c]", "[z]", "-"]
                )
            )
            if bad_mask.any():
                print(
                    f"[DEBUG] {col_type} cast failed in {col_name}: "
                    f"{original[bad_mask].unique()}"
                )
            return parsed
        except Exception as e:
            print(
                f"\n[CRITICAL DEBUG] Crash during {col_type} conversion on column '{col_name}'"
            )
            raise e

    # ── TIME ──────────────────────────────────────────────────
    elif col_type == "TIME":
        try:
            parsed = pd.to_datetime(
                series, format="%H:%M:%S", errors="coerce"
            ).dt.time
            bad_mask = (
                parsed.isna()
                & original.notna()
                & ~original.isin(
                    ["", "nan", "None", "null", "[x]", "[c]", "[z]", "-"]
                )
            )
            if bad_mask.any():
                print(
                    f"[DEBUG] TIME cast failed in {col_name}: "
                    f"{original[bad_mask].unique()}"
                )
            return parsed
        except Exception as e:
            print(
                f"\n[CRITICAL DEBUG] Crash during TIME conversion on column '{col_name}'"
            )
            raise e

    # ── FALLBACK ──────────────────────────────────────────────
    else:
        print(
            f"[DEBUG] Unknown column type '{col_type}' "
            f"for column '{col_name}'"
        )
        return series