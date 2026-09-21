# ==============================================================================
# Gold layer for lsoa_map: renders one PNG per London LSOA (~4,800 across
# Greater London) showing the bus routes that serve it and its open schools,
# by driving pipes/lsoa_map/r_lsoa_map.R (via Rscript) once per borough - see
# that script's header for why per-borough (not per-LSOA) is the unit of
# work, and why bus edges are drawn as straight lines rather than routed.
#
# Like infrastructure_map's D_gold.py, this pipeline's "gold" output is a set
# of images, not a BigQuery table - there's nothing to upload here.
# ==============================================================================

import subprocess
from pathlib import Path

PIPE_NAME = "lsoa_map"

R_SCRIPT_NAME = "r_lsoa_map.R"
IMAGES_DIRNAME = "images"
RSCRIPT_BIN = "Rscript"

LSOA_SHP_DIR_REL  = Path("data") / "A_raw" / "lsoa_map"
NAPTAN_CSV_REL    = Path("data") / "C_silver" / "infrastructure_map" / "extraction_transport_stops.csv"
GTFS_DIR_REL      = Path("data") / "A_raw" / "infrastructure_map" / "itm_london_gtfs"
SCHOOLS_CSV_REL   = Path("data") / "C_silver" / "education" / "extraction_school_location_data.csv"
POSTCODES_CSV_REL = Path("data") / "C_silver" / "postcodes" / "extraction_postcode_centroids.csv"
OSM_CACHE_DIR_REL = Path("data") / "A_raw" / "infrastructure_map"


def slugify_borough(borough_name: str) -> str:
    """Mirrors slugify_borough() in r_lsoa_map.R."""
    slug = "".join(c.lower() if c.isalnum() else "_" for c in borough_name)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def _r_string_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _discover_boroughs(lsoa_shp_dir: Path) -> list[str]:
    return sorted(p.stem for p in lsoa_shp_dir.glob("*.shp"))


def run_pipeline(PROJECT_ROOT: Path, borough_filter: list[str] | None = None, lsoa_limit: int | None = None):
    """
    borough_filter: if given, only render these boroughs (by name) instead of all 33.
    lsoa_limit: if given, only render the first N LSOAs per borough - handy for a
                quick smoke test of what the map style looks like before a full run.
    """
    pipe_dir   = PROJECT_ROOT / "pipes" / PIPE_NAME
    r_script   = pipe_dir / R_SCRIPT_NAME
    images_dir = pipe_dir / IMAGES_DIRNAME
    images_dir.mkdir(parents=True, exist_ok=True)

    lsoa_shp_dir  = PROJECT_ROOT / LSOA_SHP_DIR_REL
    naptan_csv    = PROJECT_ROOT / NAPTAN_CSV_REL
    gtfs_dir      = PROJECT_ROOT / GTFS_DIR_REL
    schools_csv   = PROJECT_ROOT / SCHOOLS_CSV_REL
    postcodes_csv = PROJECT_ROOT / POSTCODES_CSV_REL
    osm_cache_dir = PROJECT_ROOT / OSM_CACHE_DIR_REL

    boroughs = _discover_boroughs(lsoa_shp_dir)
    if borough_filter:
        boroughs = [b for b in boroughs if b in borough_filter]
    print(f"Found {len(boroughs)} borough(s) to render: {boroughs}")

    succeeded, failed = [], []

    for borough_name in boroughs:
        print(f"\n--- Rendering LSOA maps: {borough_name} ---")

        lsoa_limit_literal = str(lsoa_limit) if lsoa_limit is not None else "NULL"

        r_expr = (
            "RUN_ON_SOURCE <- FALSE; "
            f"source({_r_string_literal(r_script.as_posix())}); "
            "render_lsoa_maps_for_borough("
            f"borough_name = {_r_string_literal(borough_name)}, "
            f"lsoa_shp_dir = {_r_string_literal(lsoa_shp_dir.as_posix())}, "
            f"naptan_csv = {_r_string_literal(naptan_csv.as_posix())}, "
            f"gtfs_dir = {_r_string_literal(gtfs_dir.as_posix())}, "
            f"schools_csv = {_r_string_literal(schools_csv.as_posix())}, "
            f"postcodes_csv = {_r_string_literal(postcodes_csv.as_posix())}, "
            f"osm_cache_dir = {_r_string_literal(osm_cache_dir.as_posix())}, "
            f"output_dir = {_r_string_literal(images_dir.as_posix())}, "
            f"lsoa_limit = {lsoa_limit_literal}"
            ")"
        )

        result = subprocess.run(
            [RSCRIPT_BIN, "-e", r_expr],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        print(result.stdout)

        if result.returncode != 0:
            print(f"  [ERROR] Failed to render {borough_name}:\n{result.stderr}")
            failed.append(borough_name)
        else:
            succeeded.append(borough_name)

    print(f"\nDone. {len(succeeded)} borough(s) rendered, {len(failed)} failed.")
    if failed:
        print(f"Failed boroughs (re-run to retry - already-rendered LSOAs are skipped): {failed}")


if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    run_pipeline(PROJECT_ROOT)
