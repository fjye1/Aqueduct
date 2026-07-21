import pandas as pd
from pyproj import Transformer
import geopandas as gpd

CRIME_BUCKETS = {
    # Violent & Serious Crime
    "violent-crime": "Violent & Serious Crime",
    "possession-of-weapons": "Violent & Serious Crime",
    "robbery": "Violent & Serious Crime",

    # Property & Theft Crime
    "burglary": "Property & Theft Crime",
    "vehicle-crime": "Property & Theft Crime",
    "bicycle-theft": "Property & Theft Crime",
    "shoplifting": "Property & Theft Crime",
    "theft-from-the-person": "Property & Theft Crime",
    "other-theft": "Property & Theft Crime",

    # Quality of Life & Public Order
    "anti-social-behaviour": "Quality of Life & Public Order",
    "public-order": "Quality of Life & Public Order",
    "criminal-damage-arson": "Quality of Life & Public Order",
    "drugs": "Quality of Life & Public Order",

    # Other / Catch-all
    "other-crime": "Other",
    "all-crime": "Other"
}

LONDON_BOROUGHS_UK = [
    "K02000001", "E09000002", "E09000003", "E09000004", "E09000005",
    "E09000006", "E09000007", "E09000001", "E09000008", "E09000009",
    "E09000010", "E09000011", "E09000012", "E09000013", "E09000014",
    "E09000015", "E09000016", "E09000017", "E09000018", "E09000019",
    "E09000020", "E09000021", "E09000022", "E09000023", "E09000024",
    "E09000025", "E09000026", "E09000027", "E09000028", "E09000029",
    "E09000030", "E09000031", "E09000032", "E09000033"
]

# Borough names list using "and" exclusively
LONDON_BOROUGH_NAMES_UK = [
    "City of London", "Barking and Dagenham", "Barnet", "Bexley", "Brent",
    "Bromley", "Camden", "Croydon", "Ealing", "Enfield",
    "Greenwich", "Hackney", "Hammersmith and Fulham", "Haringey", "Harrow",
    "Havering", "Hillingdon", "Hounslow", "Islington", "Kensington and Chelsea",
    "Kingston upon Thames", "Lambeth", "Lewisham", "Merton", "Newham",
    "Redbridge", "Richmond upon Thames", "Southwark", "Sutton", "Tower Hamlets",
    "Waltham Forest", "Wandsworth", "Westminster"
]


# TODO build test for this function
def london_borough_filter(df: pd.DataFrame, filter_by_ons_code: bool = True) -> pd.DataFrame:
    """
    Filters the DataFrame for London boroughs.

    :param df: Input school DataFrame
    :param filter_by_code: If True, filters using ONS codes via the 'ons_code' column.
                          If False, filters using names via the 'LA (name)' column.
    """
    if filter_by_ons_code:
        # Filter using the alphanumeric ONS/GSS codes
        df = df[df['ons_code'].isin(LONDON_BOROUGHS_UK)]
    else:
        # Filter using the string names (Assumes 'LA (name)' matches your GIAS dataset)
        df = df[df['borough_name'].isin(LONDON_BOROUGH_NAMES_UK)]

    # # Rule 2: Check the LONDON_BOROUGHS for date logic example
    # # (Assuming clean_and_cast already converted this column to datetime)
    # df = df[df['created_date'] >= '2026-01-01']

    return df





def melt_year_columns(df, var_name="year", value_name="net_additions"):
    """
    Reshape wide year columns (e.g. '2021', '2022', ...) into a long
    'year' / value column pair. Any column whose name is purely numeric
    digits is treated as a year column and gets melted; everything else
    is kept as an id column.
    """
    year_cols = [c for c in df.columns if str(c).isdigit()]
    id_vars = [c for c in df.columns if c not in year_cols]

    melted = df.melt(
        id_vars=id_vars,
        value_vars=year_cols,
        var_name=var_name,
        value_name=value_name,
    )

    # optional but recommended: year as an int, not a string
    melted[var_name] = melted[var_name].astype(int)

    return melted

def _ensure_year_column(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize each housing table to have a clean integer 'year' column,
    without touching the shared 'year_name' field used elsewhere in the pipeline.
    """
    df = df.copy()

    if table_name == "net_housing_additions":
        # Already melted — 'year' exists and should already be int, but be defensive
        df["year"] = df["year"].astype(int)

    elif table_name == "average_house_price":
        # 'date' is 01/01/year — derive year from it, ignore the placeholder year_name ("9")
        df["date"] = pd.to_datetime(df["date"])
        df["year"] = df["date"].dt.year

    elif "year_name" in df.columns:
        # housing_stock, affordable_stock_additions, council_tax_bands
        df["year"] = df["year_name"].astype(int)

    else:
        raise ValueError(
            f"Don't know how to derive 'year' for table '{table_name}' — "
            f"columns present: {list(df.columns)}"
        )

    return df


def merge_housing_data(dfs: dict, on=("ons_code", "year"), how="left") -> pd.DataFrame:
    on = list(on) if not isinstance(on, str) else [on]
    table_names = list(dfs.keys())

    # Normalize year column per table before merging
    prepared = {name: _ensure_year_column(name, df) for name, df in dfs.items()}

    def _merge_pair(right_name, left, right):
        return left.merge(right, on=on, how=how, suffixes=("", f"_{right_name}"))

    result = prepared[table_names[0]]
    for name in table_names[1:]:
        result = _merge_pair(name, result, prepared[name])

    return result



def merge_school_and_ofsted(dfs: dict, on="unique_reference_number", how="left") -> pd.DataFrame:
    left = dfs["school_location_data"]
    right = dfs["school_ofsted_inspection"]
    return left.merge(right, on=on, how=how, suffixes=("", "_ofsted"))


# TODO build test for this function
def date_filter(df: pd.DataFrame) -> pd.DataFrame:
    a_df = df[df['date'].between('2021-01-01', '2025-12-31')]
    # Return the date if it is the 1st of jan
    df = a_df[
        (a_df["date"].dt.month == 1) &
        (a_df["date"].dt.day == 1)]

    return df

def year_filter(df: pd.DataFrame) -> pd.DataFrame:
    a_df = df[df['year'].between('2023', '2026')]
    df = a_df
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


def process_crime_df(df):
    """
    Takes a raw crime DataFrame and appends
    our custom analytical category.
    """
    # 1. Map the 'category' column to CRIME_BUCKETS.
    # 2. .fillna('Other') replaces anything not found in the dictionary.
    df["analytical_category"] = (
        df["category"]
        .map(CRIME_BUCKETS)
        .fillna("Other")
    )

    return df

def pivot_raw_police_categories(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Pivots on the 14 raw categories (not analytical_category), so each
    category keeps its own annualised_rate column and nothing gets summed
    away. Also returns a static category -> analytical_category lookup
    so that grouping info isn't lost, just relocated out of the grain table.
    """
    df = df.copy()

    # 1. Slugify raw category names -> column-safe strings
    #    e.g. "criminal-damage-arson" -> "criminal_damage_arson"
    df["category_slug"] = (
        df["category"]
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )

    # 2. Category -> analytical_category lookup (one row per raw category,
    #    since this mapping is static and doesn't vary by year/borough)
    category_lookup = (
        df[["category", "category_slug", "analytical_category"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    # 3. Pivot: one row per year/borough, one annualised_rate column per raw category
    wide = df.pivot_table(
        index=["year", "borough"],
        columns="category_slug",
        values="annualised_rate",
    )
    wide.columns = [f"{c}_annualised_rate" for c in wide.columns]
    wide = wide.reset_index()

    return wide, category_lookup