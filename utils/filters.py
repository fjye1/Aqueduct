import pandas as pd

LONDON_BOROUGHS_UK = [
    "K02000001",
    "E09000002",
    "E09000003",
    "E09000004",
    "E09000005",
    "E09000006",
    "E09000007",
    "E09000001",
    "E09000008",
    "E09000009",
    "E09000010",
    "E09000011",
    "E09000012",
    "E09000013",
    "E09000014",
    "E09000015",
    "E09000016",
    "E09000017",
    "E09000018",
    "E09000019",
    "E09000020",
    "E09000021",
    "E09000022",
    "E09000023",
    "E09000024",
    "E09000025",
    "E09000026",
    "E09000027",
    "E09000028",
    "E09000029",
    "E09000030",
    "E09000031",
    "E09000032",
    "E09000033"
]

def london_borough_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Rule 1: Check the values found in 'ons_code'(name you defined for this column above)
    # match the predefined list found in LONDON_BOROUGHS
    ons_codes = LONDON_BOROUGHS_UK
    df = df[df['ons_code'].isin(ons_codes)]

    # # Rule 2: Check the LONDON_BOROUGHS for date logic example
    # # (Assuming clean_and_cast already converted this column to datetime)
    # df = df[df['created_date'] >= '2026-01-01']

    return df

def date_filter(df: pd.DataFrame) -> pd.DataFrame:

    df = df[df['date'] >= '2024-01-01']

    return df