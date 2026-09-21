import subprocess
from pathlib import Path

import pandas as pd

PIPE_NAME = "lsoa_nearby"
OUTPUT_NAME = "ingestion"

GTFS_DIR_REL = Path("data") / "A_raw" / "infrastructure_map" / "itm_london_gtfs"
OSM_CACHE_DIR_REL = Path("data") / "A_raw" / "infrastructure_map"
EDU_BRONZE_REL = Path("data") / "B_bronze" / "education" / "ingestion_school_location_data_2026.csv"
NAPTAN_RAW_REL = Path("data") / "A_raw" / "infrastructure_map" / "Stops.csv"

R_EXPORT_SCRIPT = "r_export_stations.R"
RSCRIPT_BIN = "Rscript"

# stop_times.txt is ~1.3GB / 15.7M rows - streamed in chunks and reduced to
# what's actually needed, rather than copied into a second giant bronze file.
CHUNK_ROWS = 2_000_000

# Excerpt of the education bronze file: the raw export has real headers in its
# first data row (columns are col_0..col_N), so positions are used.
EDU_COLUMNS = {0: "urn", 18: "phase_of_education", 56: "street", 57: "locality", 59: "town", 61: "postcode"}


def _bronze_dir(project_root: Path) -> Path:
    out = project_root / "data" / "B_bronze" / PIPE_NAME
    out.mkdir(parents=True, exist_ok=True)
    return out


def ingest_gtfs(project_root: Path):
    gtfs = project_root / GTFS_DIR_REL
    out = _bronze_dir(project_root)

    agency = pd.read_csv(gtfs / "agency.txt", dtype=str, usecols=["agency_id", "agency_name"])
    routes = pd.read_csv(gtfs / "routes.txt", dtype=str)
    routes = routes[routes["route_type"] == "3"].merge(agency, on="agency_id", how="left")
    routes = routes[["route_id", "route_short_name", "agency_id", "agency_name"]]
    routes.to_csv(out / f"{OUTPUT_NAME}_bus_routes.csv", index=False)
    print(f"  bus routes: {len(routes)}")

    trips = pd.read_csv(gtfs / "trips.txt", dtype=str, usecols=["route_id", "trip_id"])
    trips = trips[trips["route_id"].isin(routes["route_id"])]
    trip_route = pd.Series(trips["route_id"].to_numpy(), index=trips["trip_id"].to_numpy())
    print(f"  bus trips: {len(trip_route)}")

    counts, firsts, lasts = [], [], []
    reader = pd.read_csv(
        gtfs / "stop_times.txt",
        usecols=["trip_id", "stop_id", "stop_sequence"],
        dtype={"trip_id": str, "stop_id": str, "stop_sequence": "int32"},
        chunksize=CHUNK_ROWS,
    )
    for i, chunk in enumerate(reader, start=1):
        chunk["route_id"] = chunk["trip_id"].map(trip_route)
        chunk = chunk.dropna(subset=["route_id"])
        counts.append(chunk.groupby(["stop_id", "route_id"]).size().rename("trip_count").reset_index())
        seq = chunk.groupby("trip_id")["stop_sequence"]
        firsts.append(chunk.loc[seq.idxmin(), ["trip_id", "stop_id", "stop_sequence"]])
        lasts.append(chunk.loc[seq.idxmax(), ["trip_id", "stop_id", "stop_sequence"]])
        print(f"  stop_times chunk {i} done ({i * CHUNK_ROWS:,} rows read)")

    stop_routes = pd.concat(counts).groupby(["stop_id", "route_id"], as_index=False)["trip_count"].sum()
    stop_routes.to_csv(out / f"{OUTPUT_NAME}_bus_stop_routes.csv", index=False)
    print(f"  distinct (stop, route) pairs: {len(stop_routes)}")

    # A trip can straddle a chunk boundary, so keep the earliest/latest record per trip overall.
    first = (pd.concat(firsts).sort_values("stop_sequence")
             .drop_duplicates("trip_id", keep="first")
             .rename(columns={"stop_id": "first_stop_id"})[["trip_id", "first_stop_id"]])
    last = (pd.concat(lasts).sort_values("stop_sequence")
            .drop_duplicates("trip_id", keep="last")
            .rename(columns={"stop_id": "last_stop_id"})[["trip_id", "last_stop_id"]])
    ends = first.merge(last, on="trip_id")
    ends["route_id"] = ends["trip_id"].map(trip_route)
    patterns = (ends.groupby(["route_id", "first_stop_id", "last_stop_id"]).size()
                .rename("n_trips").reset_index())
    patterns.to_csv(out / f"{OUTPUT_NAME}_bus_route_patterns.csv", index=False)
    print(f"  route patterns: {len(patterns)}")

    stops = pd.read_csv(gtfs / "stops.txt", dtype=str, usecols=["stop_id", "stop_name", "stop_lat", "stop_lon"])
    needed = set(stop_routes["stop_id"]) | set(patterns["first_stop_id"]) | set(patterns["last_stop_id"])
    stops = stops[stops["stop_id"].isin(needed)]
    stops.to_csv(out / f"{OUTPUT_NAME}_bus_stops.csv", index=False)
    print(f"  bus stops: {len(stops)}")

    pd.read_csv(gtfs / "feed_info.txt", dtype=str).to_csv(out / f"{OUTPUT_NAME}_feed_info.csv", index=False)


def ingest_stop_localities(project_root: Path):
    """NaPTAN locality per bus stop. GTFS stop names have no town, so 'Waterloo Road' could be
    Waterloo or Epsom - the locality is what makes a route's ends unambiguous."""
    out = _bronze_dir(project_root)
    stops = pd.read_csv(out / f"{OUTPUT_NAME}_bus_stops.csv", dtype=str, usecols=["stop_id"])
    naptan = pd.read_csv(project_root / NAPTAN_RAW_REL, dtype=str, encoding="latin-1",
                         usecols=["ATCOCode", "LocalityName", "ParentLocalityName", "Town"])
    naptan = naptan.rename(columns={"ATCOCode": "stop_id", "LocalityName": "locality",
                                    "ParentLocalityName": "parent_locality", "Town": "town"})
    naptan = naptan[naptan["stop_id"].isin(stops["stop_id"])].drop_duplicates("stop_id")
    naptan.to_csv(out / f"{OUTPUT_NAME}_bus_stop_localities.csv", index=False)
    print(f"  stop localities: {len(naptan)} of {len(stops)} bus stops")


def ingest_school_addresses(project_root: Path):
    out = _bronze_dir(project_root)
    raw = pd.read_csv(project_root / EDU_BRONZE_REL, usecols=list(EDU_COLUMNS), dtype=str)
    raw.columns = [f"col_{c}" for c in EDU_COLUMNS]
    df = raw.iloc[1:].copy()  # first data row is the header row of the original spreadsheet
    df.columns = list(EDU_COLUMNS.values())
    df.to_csv(out / f"{OUTPUT_NAME}_school_addresses.csv", index=False)
    print(f"  school addresses: {len(df)}")


def export_stations(project_root: Path):
    out_csv = _bronze_dir(project_root) / f"{OUTPUT_NAME}_stations.csv"
    r_script = project_root / "pipes" / PIPE_NAME / R_EXPORT_SCRIPT
    result = subprocess.run(
        [RSCRIPT_BIN, str(r_script), str(project_root / OSM_CACHE_DIR_REL), str(out_csv)],
        cwd=project_root, capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"Station export failed:\n{result.stderr}")


def run_pipeline(project_root: Path):
    print("--- GTFS bus data ---")
    ingest_gtfs(project_root)
    print("--- Stop localities (NaPTAN) ---")
    ingest_stop_localities(project_root)
    print("--- School addresses ---")
    ingest_school_addresses(project_root)
    print("--- Stations (from OSM caches) ---")
    export_stations(project_root)
