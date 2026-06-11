from datetime import datetime
from os import path
from typing import Callable, Optional

import pandas as pd

from utils.clean_cast import clean_and_cast


def column_row_extractor(
        file_path: path,
        pipe_name: str,
        data_row_start: int,
        data_row_end: int,
        columns: list[dict],
        output_name: str,
        function_filter: Optional[Callable[[pd.DataFrame], pd.DataFrame]] = None,

) -> pd.DataFrame:
    """Select specific columns from a bronze CSV, clean them,

    cast them to defined types, and output a silver table.

    Parameters
    ----------
    file_path : path
        Source CSV file.
    data_row_start : int
        Row number where data begins (0-indexed).
    data_row_end : int
        Row number where data ends (exclusive).
    columns : list[dict]
        List of dictionaries defining 'col', 'name', and 'type'.
    output_name : str
        Output filename without extension.
    function_filter : Optional[Callable[[pd.DataFrame], pd.DataFrame]], optional
        A custom function to filter the rows (e.g., matching specific dates
        or column values) before saving. Must accept and return a DataFrame.
    """
    print(f"Loading {file_path}")

    # 1. Extract targeting details from your columns list
    col_indices = [col["col"] for col in columns]
    col_names = [col["name"] for col in columns]
    rename_map = {col["col"]: col["name"] for col in columns}

    # 2. Calculate exact number of rows to pull
    nrows = data_row_end - data_row_start

    # 3. Memory Optimization: Only stream required rows/columns from disk
    df = pd.read_csv(
        file_path,
        header=None,
        skiprows=data_row_start,
        nrows=nrows,
        usecols=col_indices,
    )

    # 4. Map the multi-index headers back to your custom names
    df = df.rename(columns=rename_map)

    # Ensure final column ordering matches your input list layout
    df = df[col_names]

    print(f"Loaded {len(df)} rows x {len(df.columns)} columns")

    # 5. Clean and cast columns in place
    for col_def in columns:
        col_name = col_def["name"]
        col_type = col_def.get("type", "STRING")

        print(
            f"Processing column {col_def['col']} -> {col_name} ({col_type})"
        )

        # Utilizing your external cleaning utility function
        df[col_name] = clean_and_cast(
            series=df[col_name],
            col_type=col_type,
            col_name=col_name,
        )
    # 6. Apply Custom Filtering
    if function_filter:
        initial_rows = len(df)
        df = function_filter(df)
        print(f"Filtered dataframe: {initial_rows} rows -> {len(df)} rows")

    # 7. Save the Silver Table
    output_file = f"{output_name}.csv"
    date = datetime.now().strftime("%Y-%m-%d")
    df.to_csv(f"data/C_silver/{pipe_name}/{output_name}-{date}.csv", index=False)

    print(
        f"Saved {len(df)} rows x {len(df.columns)} columns -> {output_file}"
    )

    return df
