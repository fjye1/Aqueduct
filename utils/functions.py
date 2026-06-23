import pandas as pd


def count_by_borough(df: pd.DataFrame, count_column_name: str) -> pd.DataFrame:
    """
    Groups by borough and returns a dataframe with a custom named count column.
    """
    df = df.copy()
    df["BOROUGH"] = df["BOROUGH"].fillna("Unknown / Outside London")

    summary = (
        df.groupby("BOROUGH")
        .size()
        .reset_index(name=count_column_name)
    )
    return summary


def standardise_names(series):
    return (series.astype(str)
            .str.lower()
            .str.replace(" and ", " & ", regex=False)
            .str.strip())