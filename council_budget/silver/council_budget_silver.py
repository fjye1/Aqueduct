import pandas as pd


def find_headers(file_path):
    df = pd.read_excel(file_path, sheet_name=3, header=None)

    print(f"Total rows: {len(df)}")
    print(f"Total cols: {len(df.columns)}")
    print("\n--- First 15 rows ---")
    print(df.iloc[:15].to_string())

def flattern_csv(file_path):
    df = pd.read_excel(file_path, sheet_name=3, header=None)

    # Extract the multi header columns
    row_category = df.iloc[7].ffill()  # forward fill blanks
    row_code = df.iloc[8].ffill()  # forward fill blanks
    row_name = df.iloc[9]

    # Build flattened column names - always category_code_name
    flat_columns = []
    for cat, code, name in zip(row_category, row_code, row_name):
        cat = str(cat).strip().lower().replace(" ", "_")
        code = str(code).strip().replace(".0", "")  # removes trailing .0 from numeric codes
        name = str(name).strip().lower().replace(" ", "_")

        col = f"{cat}_{code}_{name}"
        flat_columns.append(col)

    # Apply to actual data (everything after row 10)
    data = df.iloc[10:].reset_index(drop=True)
    data.columns = flat_columns

    print(data.columns.tolist())

    # Save
    data.to_csv("flattened_output.csv", index=False)
    data.to_excel("flattened_output.xlsx", index=False)