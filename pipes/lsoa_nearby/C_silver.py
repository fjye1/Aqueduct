import re
from pathlib import Path

import pandas as pd

PIPE_NAME = "lsoa_nearby"
OUTPUT_NAME = "extraction"

EDU_SILVER_REL = Path("data") / "C_silver" / "education" / "extraction_school_location_data.csv"

# Services that are in the timetable but aren't part of the ordinary bus network
# a resident would use to plan a journey.
EXCLUDED_AGENCY_KEYWORDS = ("replacement", "hotel hoppa", "golden tours", "big bus", "tootbus", "original tour")

# GIAS "PhaseOfEducation (name)" -> the groups used on the card.
PHASE_MAP = {
    "Primary": "Primary",
    "Middle deemed primary": "Primary",
    "Secondary": "Secondary",
    "Middle deemed secondary": "Secondary",
    "All-through": "All-through",
    "Nursery": "Nursery",
    "16 plus": "16 plus",
}


def clean_destination(name) -> str:
    """Tidy a GTFS stop name into something that reads as a place, e.g. 'Hounslow Bus Station, Stop A'."""
    n = str(name)
    n = re.sub(r"[\s,(-]*\(?\bStop\s+[A-Z0-9]{1,3}\)?\s*$", "", n, flags=re.I)
    return re.sub(r"\s+", " ", n).strip(" ,-")


def clean_locality(name) -> str:
    n = re.sub(r"\s+", " ", str(name)).strip()
    return "Kingston" if n.lower() == "kingston upon thames" else n


def _bronze(project_root: Path, name: str) -> Path:
    return project_root / "data" / "B_bronze" / PIPE_NAME / f"ingestion_{name}.csv"


def _out(project_root: Path, name: str) -> Path:
    out = project_root / "data" / "C_silver" / PIPE_NAME / f"{OUTPUT_NAME}_{name}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def build_bus_tables(project_root: Path):
    routes = pd.read_csv(_bronze(project_root, "bus_routes"), dtype=str)
    patterns = pd.read_csv(_bronze(project_root, "bus_route_patterns"), dtype=str)
    patterns["n_trips"] = patterns["n_trips"].astype(int)
    stops = pd.read_csv(_bronze(project_root, "bus_stops"), dtype=str)
    stop_routes = pd.read_csv(_bronze(project_root, "bus_stop_routes"), dtype={"stop_id": str, "route_id": str})

    print("  bus agencies in the feed:")
    print(routes.groupby("agency_name").size().sort_values(ascending=False).to_string())

    agency_lower = routes["agency_name"].fillna("").str.lower()
    excluded = agency_lower.apply(lambda a: any(k in a for k in EXCLUDED_AGENCY_KEYWORDS))
    print(f"  excluding {int(excluded.sum())} non-standard routes "
          f"({sorted(routes[excluded]['agency_name'].dropna().unique())})")
    routes = routes[~excluded].copy()

    # Route ends: the most common first/last stop pair, direction-agnostic (A->B and B->A count together).
    # Named by NaPTAN locality (e.g. "Epsom"), not stop name - stop names carry no town, so a bare
    # "Waterloo Road" could be Waterloo or Epsom. Stop name is only the fallback.
    stop_names = stops.set_index("stop_id")["stop_name"].map(clean_destination)
    localities = pd.read_csv(_bronze(project_root, "bus_stop_localities"), dtype=str).set_index("stop_id")["locality"]
    names = localities.dropna().map(clean_locality).reindex(stop_names.index).combine_first(stop_names)
    print(f"  route ends named by locality: {int(localities.reindex(stop_names.index).notna().sum())} of {len(stop_names)} stops")
    patterns = patterns[patterns["route_id"].isin(routes["route_id"])].copy()
    patterns["end_a"] = patterns["first_stop_id"].map(names)
    patterns["end_b"] = patterns["last_stop_id"].map(names)
    patterns = patterns.dropna(subset=["end_a", "end_b"])
    ends = patterns[["end_a", "end_b"]].apply(lambda r: tuple(sorted(r)), axis=1, result_type="expand")
    patterns["terminus_a"], patterns["terminus_b"] = ends[0], ends[1]
    best = (patterns.groupby(["route_id", "terminus_a", "terminus_b"], as_index=False)["n_trips"].sum()
            .sort_values("n_trips", ascending=False).drop_duplicates("route_id"))

    routes = routes.merge(best[["route_id", "terminus_a", "terminus_b"]], on="route_id", how="left")
    routes["is_night"] = routes["route_short_name"].str.match(r"^N\d")
    routes["destination_label"] = routes.apply(
        lambda r: "" if pd.isna(r["terminus_a"]) else
        (f"Local service in {r['terminus_a']}" if r["terminus_a"] == r["terminus_b"]
         else f"{r['terminus_a']} ↔ {r['terminus_b']}"), axis=1)
    routes = routes[routes["destination_label"] != ""]
    routes.to_csv(_out(project_root, "bus_routes"), index=False)
    print(f"  kept {len(routes)} bus routes with a destination label")

    stop_routes = stop_routes[stop_routes["route_id"].isin(routes["route_id"])]
    stop_routes = stop_routes.merge(stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]], on="stop_id", how="left")
    stop_routes.to_csv(_out(project_root, "bus_stop_routes"), index=False)
    print(f"  bus (stop, route) pairs: {len(stop_routes)}")


def build_schools(project_root: Path):
    edu = pd.read_csv(project_root / EDU_SILVER_REL)
    addr = pd.read_csv(_bronze(project_root, "school_addresses"), dtype=str)
    edu["urn"] = edu["unique_reference_number"].astype(str)
    df = edu.merge(addr, on="urn", how="left")

    df = df[df["status"].fillna("").str.startswith("Open")].dropna(subset=["easting", "northing"]).copy()
    print("  phase_of_education values:", df["phase_of_education"].value_counts(dropna=False).to_dict())

    df["phase"] = df["phase_of_education"].map(PHASE_MAP).fillna("Other")
    type_lower = df["type_of_establishment"].fillna("").str.lower()
    df["is_special"] = type_lower.str.contains("special|pupil referral|alternative provision")
    df["is_independent"] = df["establishment_group"].fillna("").str.contains("Independent", case=False)

    def address(r):
        street = r["street"] if pd.notna(r["street"]) else ""
        pc = r["postcode"] if pd.notna(r["postcode"]) else ""
        return ", ".join(p for p in [street, pc] if p)

    df["address"] = df.apply(address, axis=1)
    keep = ["urn", "school_name", "phase", "is_special", "is_independent", "type_of_establishment",
            "address", "postcode", "easting", "northing", "lsoa_code", "borough_name"]
    df[keep].to_csv(_out(project_root, "schools"), index=False)
    print(f"  open schools: {len(df)} | by phase: {df['phase'].value_counts().to_dict()}")


def build_stations(project_root: Path):
    df = pd.read_csv(_bronze(project_root, "stations"))
    df = df.dropna(subset=["name", "lon", "lat"]).drop_duplicates(["name", "lon", "lat"])
    df.to_csv(_out(project_root, "stations"), index=False)
    print(f"  stations: {len(df)}")


def run_pipeline(project_root: Path):
    print("--- Bus routes / destinations ---")
    build_bus_tables(project_root)
    print("--- Schools ---")
    build_schools(project_root)
    print("--- Stations ---")
    build_stations(project_root)
