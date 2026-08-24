# ==============================================================================
# Pre-downloads street network + station data for every London borough using
# a LOCAL OSM extract (via r_bus_map_streets_local.R / osmextract) instead of
# live Overpass API calls. Each borough is cached to its own .rds file under
# data/A_raw/infrastructure_map (osm_streets_<slug>.rds / osm_stations_<slug>.rds).
#
# The first call downloads a single Greater London .pbf from Geofabrik
# (a few hundred MB, one-time). Every borough after that is a local spatial
# filter against that cached file - no further network calls, so there's
# nothing left to time out or rate-limit.
#
# Still runs each borough/layer in its own Rscript subprocess so one bad
# borough (e.g. a bad shapefile match) can't take down the rest of the run.
# Re-running this script is safe/cheap: already-cached boroughs are skipped.
# ==============================================================================

import subprocess
from pathlib import Path

import pandas as pd

PIPE_NAME = "infrastructure_map"
R_SCRIPT_NAME = "r_bus_map_streets.R"
RSCRIPT_BIN = "Rscript"

NAPTAN_CSV_REL    = Path("data") / "C_silver" / "infrastructure_map" / "extraction_transport_stops.csv"
BOROUGH_SHP_REL   = Path("data") / "A_raw" / "infrastructure" / "london_boroughs.shp"
OSM_CACHE_DIR_REL = Path("data") / "A_raw" / "infrastructure_map"


def _r_string_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _discover_boroughs(naptan_csv: Path) -> list[str]:
    df = pd.read_csv(naptan_csv, usecols=["BOROUGH"])
    return sorted(df["BOROUGH"].dropna().unique().tolist())


def _download_one(r_script: Path, project_root: Path, fn_name: str, borough_name: str,
                   borough_shp: Path, cache_dir: Path) -> bool:
    r_expr = (
        "RUN_ON_SOURCE <- FALSE; "
        f"source({_r_string_literal(r_script.as_posix())}); "
        f"{fn_name}("
        f"borough_name = {_r_string_literal(borough_name)}, "
        f"borough_shp = {_r_string_literal(borough_shp.as_posix())}, "
        f"cache_dir = {_r_string_literal(cache_dir.as_posix())}"
        ")"
    )

    result = subprocess.run(
        [RSCRIPT_BIN, "-e", r_expr],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    print(result.stdout)

    if result.returncode == 0:
        return True

    print(f"  [ERROR] {fn_name}({borough_name}) failed:\n{result.stderr}")
    return False


def run_download(PROJECT_ROOT: Path):
    pipe_dir = PROJECT_ROOT / "pipes" / PIPE_NAME
    r_script = pipe_dir / R_SCRIPT_NAME

    naptan_csv  = PROJECT_ROOT / NAPTAN_CSV_REL
    borough_shp = PROJECT_ROOT / BOROUGH_SHP_REL
    cache_dir   = PROJECT_ROOT / OSM_CACHE_DIR_REL

    boroughs = _discover_boroughs(naptan_csv)
    print(f"Found {len(boroughs)} boroughs in {naptan_csv.name}: {boroughs}")
    print("Note: the first download below will pull the full Greater London "
          "OSM extract (one-time, a few hundred MB) - this one will take a while, "
          "every borough after it should be fast (local filtering only).")

    streets_failed, stations_failed = [], []

    for borough_name in boroughs:
        print(f"\n--- {borough_name}: streets ---")
        if not _download_one(r_script, PROJECT_ROOT, "download_osm_streets", borough_name, borough_shp, cache_dir):
            streets_failed.append(borough_name)

        print(f"\n--- {borough_name}: stations ---")
        if not _download_one(r_script, PROJECT_ROOT, "download_osm_stations", borough_name, borough_shp, cache_dir):
            stations_failed.append(borough_name)

    print(
        f"\nDone. {len(boroughs) - len(streets_failed)}/{len(boroughs)} street downloads ok, "
        f"{len(boroughs) - len(stations_failed)}/{len(boroughs)} station downloads ok."
    )
    if streets_failed:
        print(f"Failed street downloads (re-run this script to retry - already-cached boroughs are skipped): {streets_failed}")
    if stations_failed:
        print(f"Failed station downloads (re-run this script to retry - already-cached boroughs are skipped): {stations_failed}")


if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    run_download(PROJECT_ROOT)