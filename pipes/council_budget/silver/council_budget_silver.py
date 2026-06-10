import pandas as pd

from utils.clean_cast import clean_and_cast





def flatten_drop(
    file_path: str,
    data_row_start: int,
    data_row_end: int,
    columns: list[dict],
    output_name: str,
) -> pd.DataFrame:
    """Select specific columns from a bronze CSV, clean them,

    cast them to defined types, and output a silver table.

    Parameters
    ----------
    file_path : str
        Source CSV file.
    data_row_start : int
        Row number where data begins (0-indexed).
    data_row_end : int
        Row number where data ends (exclusive).
    columns : list[dict]
        List of dictionaries defining 'col', 'name', and 'type'.
    output_name : str
        Output filename without extension.
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

    # 6. Save the Silver Table
    output_file = f"{output_name}_silver.csv"
    df.to_csv(output_file, index=False)

    print(
        f"Saved {len(df)} rows x {len(df.columns)} columns -> {output_file}"
    )

    return df