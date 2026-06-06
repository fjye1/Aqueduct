import pandas as pd

raw_csv = "Council_Budgets.xlsx"

def flattern_csv(file_path):
    df = pd.read_excel(file_path, sheet_name=3, header=None)

    print(f"Total rows: {len(df)}")
    print(f"Total cols: {len(df.columns)}")
    print("\n--- First 15 rows ---")
    print(df.iloc[:15].to_string())

    df = pd.read_excel(raw_csv, sheet_name=3, header=None)

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



# load into a dataset


# print("Loading file...")
#
# df_raw = pd.read_excel(
#     raw_csv,
#     sheet_name=3,
#     header=None
# )
#
# print("File loaded")
# print(f"Shape: {df_raw.shape}")
#
# print("\nExtracting header rows...")
#
# top_category = df_raw.iloc[7]
# sub_codes = df_raw.iloc[8]
# sub_names = df_raw.iloc[9]
#
# print("Top category example:", top_category.dropna().head(3).tolist())
# print("Sub codes example:", sub_codes.dropna().head(3).tolist())
# print("Sub names example:", sub_names.dropna().head(3).tolist())
#
# print("\nBuilding column names...")
#
# new_columns = []
#
# for cat, code, name in zip(top_category, sub_codes, sub_names):
#     if pd.isna(code):
#         new_columns.append(str(name))
#     else:
#         new_columns.append(f"{cat} | {name} ({code})")
#
# print("Sample columns:")
# print(new_columns[:5])
#
# print("\nCreating final dataframe...")
#
# df = df_raw.iloc[10:]
# df.columns = new_columns
# df = df.reset_index(drop=True)
#
# print("Done")
# print(f"Final shape: {df.shape}")
#
# print("\nPreview:")
# print(df.head())
# print(df.iloc[:15, :15])