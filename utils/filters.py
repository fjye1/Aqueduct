import pandas as pd
from pyproj import Transformer
import geopandas as gpd

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


# TODO build test for this function
def london_borough_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Rule 1: Check the values found in 'ons_code'(name you defined for this column above)
    # match the predefined list found in LONDON_BOROUGHS
    ons_codes = LONDON_BOROUGHS_UK
    df = df[df['ons_code'].isin(ons_codes)]

    # # Rule 2: Check the LONDON_BOROUGHS for date logic example
    # # (Assuming clean_and_cast already converted this column to datetime)
    # df = df[df['created_date'] >= '2026-01-01']

    return df


# TODO build test for this function
def date_filter(df: pd.DataFrame) -> pd.DataFrame:
    a_df = df[df['date'].between('2021-01-01', '2025-12-31')]
    # Return the date if it is the 1st of jan
    df = a_df[
        (a_df["date"].dt.month == 1) &
        (a_df["date"].dt.day == 1)]

    return df


def os_to_lat_lon(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts OS Easting and Northing to Lat/Lon (EPSG:4326).
    Automatically detects columns based on common naming conventions or positions.
    """
    df = df.copy()

    # Lists of common names for Easting (X) and Northing (Y)
    possible_x = ["easting", "x", "X"]
    possible_y = ["northing", "y", "Y"]

    # Try to find a matching column name in the DataFrame
    x_col = next((col for col in possible_x if col in df.columns), None)
    y_col = next((col for col in possible_y if col in df.columns), None)

    # Fallback: If no common names match, default to the first two columns
    if x_col is None or y_col is None:
        x_col = df.columns[0]
        y_col = df.columns[1]

    # Initialize the transformer (always_xy=True ensures output is lon, lat)
    transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

    # Perform the vectorized transformation
    df["lon"], df["lat"] = transformer.transform(
        df[x_col].values,
        df[y_col].values
    )


    return df


def get_borough_from_lat_lon(df: pd.DataFrame) -> pd.DataFrame:
    """
    Performs a spatial join to find the London borough for each lat/lon point.
    Safely drops shapefile clutter without disturbing any original columns.
    """
    # 1. Convert the input DataFrame into a temporary GeoDataFrame
    stops = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326"
    )

    # 2. Load the boroughs shapefile
    boroughs = gpd.read_file("data/A_raw/infrastructure/london_boroughs.shp")

    # Ensure the shapefile is in the exact same coordinate system
    if boroughs.crs != "EPSG:4326":
        boroughs = boroughs.to_crs("EPSG:4326")

    # 3. Perform the spatial join
    joined = gpd.sjoin(stops, boroughs, how="left", predicate="within")

    # 4. Explicitly drop ONLY the junk columns brought in by the shapefile
    # This ensures columns like X, Y, lat, lon, etc., are never touched
    shapefile_junk = [
        "geometry", "index_right", "NUMBER_", "CODE", "HECTARES",
        "DESCRIPT0", "X_right", "Y_right", "AREA", "OBJECTID",
        "FILE_NAME", "Shape__Are", "Shape__Len", "GlobalID", "year_name"
    ]

    # Only drop columns that actually exist in the joined dataframe to prevent KeyErrors
    columns_to_drop = [col for col in shapefile_junk if col in joined.columns]
    joined = joined.drop(columns=columns_to_drop)

    # Convert back to a standard DataFrame and return
    return pd.DataFrame(joined)