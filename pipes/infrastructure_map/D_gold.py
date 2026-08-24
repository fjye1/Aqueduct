# ==============================================================================
# Gold layer for infrastructure_map: renders one internal bus-network map PNG
# per London borough by driving pipes/infrastructure_map/r_bus_map_streets.R
# (via Rscript) for every borough found in the full NaPTAN extract.
#
# Unlike the other pipes' D_gold.py, this pipeline's "gold" output is a set
# of images, not a BigQuery table - there's nothing to upload here.
# ==============================================================================

import subprocess
from pathlib import Path

import pandas as pd

PIPE_NAME = "infrastructure_map"

R_SCRIPT_NAME = "r_bus_map_streets.R"
IMAGES_DIRNAME = "images"
RSCRIPT_BIN = "Rscript"

NAPTAN_CSV_REL   = Path("data") / "C_silver" / "infrastructure_map" / "extraction_transport_stops.csv"
BOROUGH_SHP_REL  = Path("data") / "A_raw" / "infrastructure" / "london_boroughs.shp"
GTFS_DIR_REL     = Path("data") / "A_raw" / "infrastructure_map" / "itm_london_gtfs"
OSM_CACHE_DIR_REL = Path("data") / "A_raw" / "infrastructure_map"

# If a borough's PNG already exists in the images dir, skip re-rendering it.
# Handy for resuming a 30-borough run after a partial failure without
# re-paying the Overpass download + street-routing cost for boroughs that
# already succeeded (OSM data itself is still cached separately by the R
# script regardless of this flag).
SKIP_EXISTING = True


def slugify_borough(borough_name: str) -> str:
    """Mirrors slugify_borough() in r_bus_map_streets.R."""
    slug = "".join(c.lower() if c.isalnum() else "_" for c in borough_name)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def _r_string_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _discover_boroughs(naptan_csv: Path) -> list[str]:
    df = pd.read_csv(naptan_csv, usecols=["BOROUGH"])
    return sorted(df["BOROUGH"].dropna().unique().tolist())


def run_pipeline(PROJECT_ROOT: Path):
    pipe_dir     = PROJECT_ROOT / "pipes" / PIPE_NAME
    r_script     = pipe_dir / R_SCRIPT_NAME
    images_dir   = pipe_dir / IMAGES_DIRNAME
    images_dir.mkdir(parents=True, exist_ok=True)

    naptan_csv  = PROJECT_ROOT / NAPTAN_CSV_REL
    borough_shp = PROJECT_ROOT / BOROUGH_SHP_REL
    gtfs_dir    = PROJECT_ROOT / GTFS_DIR_REL
    cache_dir   = PROJECT_ROOT / OSM_CACHE_DIR_REL

    boroughs = _discover_boroughs(naptan_csv)
    print(f"Found {len(boroughs)} boroughs in {naptan_csv.name}: {boroughs}")

    succeeded, skipped, failed = [], [], []

    for borough_name in boroughs:
        target_png = images_dir / f"{borough_name}.png"

        if SKIP_EXISTING and target_png.exists():
            print(f"\n--- Skipping {borough_name} (already rendered) ---")
            skipped.append(borough_name)
            continue

        print(f"\n--- Rendering bus network map: {borough_name} ---")

        r_expr = (
            "RUN_ON_SOURCE <- FALSE; "
            f"source({_r_string_literal(r_script.as_posix())}); "
            "render_borough_bus_network("
            f"borough_name = {_r_string_literal(borough_name)}, "
            f"gtfs_dir = {_r_string_literal(gtfs_dir.as_posix())}, "
            f"naptan_csv = {_r_string_literal(naptan_csv.as_posix())}, "
            f"borough_shp = {_r_string_literal(borough_shp.as_posix())}, "
            f"output_dir = {_r_string_literal(images_dir.as_posix())}, "
            f"cache_dir = {_r_string_literal(cache_dir.as_posix())}"
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
            continue

        # R writes bus_network_map_r_dark_<slug>.png - rename to the plain
        # borough name as requested.
        slug_png = images_dir / f"bus_network_map_r_dark_{slugify_borough(borough_name)}.png"
        if slug_png.exists():
            slug_png.replace(target_png)
            print(f"  Saved {target_png}")
            succeeded.append(borough_name)
        else:
            print(f"  [WARN] Expected output not found: {slug_png}")
            failed.append(borough_name)

    print(
        f"\nDone. {len(succeeded)} rendered, {len(skipped)} skipped "
        f"(already existed), {len(failed)} failed."
    )
    if failed:
        print(f"Failed boroughs: {failed}")
