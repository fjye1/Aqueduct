# ==============================================================================
# Gold layer for lsoa_nearby: per-LSOA "Transport & schools nearby" data + a
# simple HTML card per LSOA (buses list, schools list + small map, nearest
# station). Replaces drawing bus routes on a map, which read as a route guide
# and could mislead someone planning a journey.
#
# Tables (data/D_gold/lsoa_nearby/, also sent to BigQuery - dry run by default):
#   gold_lsoa_nearby_centres.csv   reference point used for every distance
#   gold_lsoa_nearby_buses.csv     one row per (LSOA, bus number)
#   gold_lsoa_nearby_schools.csv   nearest schools per LSOA and phase group
#   gold_lsoa_nearby_station.csv   nearest station + estimated walk time
# Cards (data/D_gold/lsoa_nearby/cards/<borough>/<lsoa>.html, maps alongside).
#
# The reference point is the LSOA's representative point (guaranteed inside the
# polygon). Nothing here is property-specific: "your property" distances need a
# point per search - the point-based helpers below are written so a postcode
# centroid can be dropped in instead.
# ==============================================================================

import base64
import html
import subprocess
from datetime import datetime
from pathlib import Path
from string import Template

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer

from utils.big_query.import_big_query import load_into_bigquery

PIPE_NAME = "lsoa_nearby"
PROJECT_ID = "roomreview-487913"
LAYER = "gold_layer_lsoa"
DRY_RUN = True  # Set to False when you want to upload

R_MAP_SCRIPT = "r_schools_map.R"
RSCRIPT_BIN = "Rscript"

LSOA_SHP_DIR_REL = Path("data") / "A_raw" / "lsoa_map"
OSM_GPKG_REL = (Path("data") / "A_raw" / "infrastructure_map" / "_osmextract_cache"
                / "geofabrik_greater-london-latest.gpkg")

M_PER_MILE = 1609.344

BUS_STOP_BUFFER_M = 200          # a bus "serves the area" if it has a stop this close to the LSOA boundary
SCHOOLS_PER_PHASE = 3            # nearest N per phase group
MAX_SCHOOL_DISTANCE_M = 3 * M_PER_MILE
# GIAS gives independent schools no phase, and a nearest-3 list would fill up with them in wealthier
# areas - so v1 lists state-funded mainstream schools only. Flip to include them (their phase would
# then need deriving from statutory ages).
INCLUDE_INDEPENDENT = False
WALK_CIRCUITY = 1.3              # straight-line -> rough walking distance
WALK_M_PER_MIN = 80              # ~4.8 km/h
MAX_BUSES_SHOWN = 8              # on the card; the table keeps every route

# A school in both groups (all-through) counts for each.
PHASE_GROUPS = {"Primary": ["Primary", "All-through"], "Secondary": ["Secondary", "All-through"]}

TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True)
TO_WGS = Transformer.from_crs(27700, 4326, always_xy=True)


def _silver(project_root: Path, name: str) -> Path:
    return project_root / "data" / "C_silver" / PIPE_NAME / f"extraction_{name}.csv"


def _gold_dir(project_root: Path) -> Path:
    out = project_root / "data" / "D_gold" / PIPE_NAME
    out.mkdir(parents=True, exist_ok=True)
    return out


def _save_and_upload(project_root: Path, df: pd.DataFrame, table: str):
    df.to_csv(_gold_dir(project_root) / f"gold_lsoa_nearby_{table}.csv", index=False)
    print(f"  saved {table}: {len(df)} rows")
    load_into_bigquery(project_id=PROJECT_ID, layer=LAYER, table_name=f"lsoa_nearby_{table}",
                       df=df, dry_run=DRY_RUN)


def _load_lsoas(project_root: Path, borough_filter=None) -> gpd.GeoDataFrame:
    frames = []
    for shp in sorted((project_root / LSOA_SHP_DIR_REL).glob("*.shp")):
        if borough_filter and shp.stem not in borough_filter:
            continue
        frames.append(gpd.read_file(shp)[["lsoa21cd", "lsoa21nm", "lad22nm", "geometry"]])
    gdf = pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(gdf, geometry="geometry", crs=frames[0].crs)


def _build_centres(lsoas: gpd.GeoDataFrame) -> pd.DataFrame:
    rp = lsoas.geometry.representative_point()
    lon, lat = TO_WGS.transform(rp.x.to_numpy(), rp.y.to_numpy())
    return pd.DataFrame({
        "lsoa_code": lsoas["lsoa21cd"].to_numpy(), "lsoa_name": lsoas["lsoa21nm"].to_numpy(),
        "borough_name": lsoas["lad22nm"].to_numpy(),
        "easting": rp.x.to_numpy(), "northing": rp.y.to_numpy(), "lon": lon, "lat": lat,
    })


def _build_buses(project_root: Path, lsoas: gpd.GeoDataFrame, centres: pd.DataFrame) -> pd.DataFrame:
    routes = pd.read_csv(_silver(project_root, "bus_routes"), dtype={"route_id": str})
    sr = pd.read_csv(_silver(project_root, "bus_stop_routes"), dtype={"stop_id": str, "route_id": str})

    stops = sr[["stop_id", "stop_name", "stop_lat", "stop_lon"]].drop_duplicates("stop_id").reset_index(drop=True)
    x, y = TO_BNG.transform(stops["stop_lon"].to_numpy(), stops["stop_lat"].to_numpy())
    stops["stop_e"], stops["stop_n"] = x, y
    stops_gdf = gpd.GeoDataFrame(stops[["stop_id", "stop_name", "stop_e", "stop_n"]],
                                 geometry=gpd.points_from_xy(x, y), crs=27700)

    buffered = lsoas[["lsoa21cd", "geometry"]].copy()
    buffered["geometry"] = buffered.geometry.buffer(BUS_STOP_BUFFER_M)
    pairs = gpd.sjoin(stops_gdf, buffered, how="inner", predicate="within")
    pairs = pd.DataFrame(pairs.drop(columns=["geometry", "index_right"]))
    c = centres[["lsoa_code", "easting", "northing"]]
    pairs = pairs.merge(c, left_on="lsoa21cd", right_on="lsoa_code")
    pairs["dist_m"] = np.hypot(pairs["stop_e"] - pairs["easting"], pairs["stop_n"] - pairs["northing"])

    m = pairs[["lsoa21cd", "stop_id", "stop_name", "dist_m"]].merge(sr[["stop_id", "route_id", "trip_count"]], on="stop_id")
    m = m.merge(routes[["route_id", "route_short_name"]], on="route_id")

    # One row per bus number; the label comes from whichever variant runs most in the area.
    per_variant = m.groupby(["lsoa21cd", "route_short_name", "route_id"], as_index=False)["trip_count"].sum()
    best = (per_variant.sort_values("trip_count", ascending=False)
            .drop_duplicates(["lsoa21cd", "route_short_name"])[["lsoa21cd", "route_short_name", "route_id"]]
            .merge(routes[["route_id", "destination_label", "agency_name", "is_night"]], on="route_id"))
    totals = m.groupby(["lsoa21cd", "route_short_name"], as_index=False)["trip_count"].sum().rename(
        columns={"trip_count": "trips_in_area"})
    idx = m.groupby(["lsoa21cd", "route_short_name"])["dist_m"].idxmin()
    near = m.loc[idx, ["lsoa21cd", "route_short_name", "stop_name", "dist_m"]].rename(
        columns={"stop_name": "nearest_stop_name", "dist_m": "nearest_stop_m"})

    out = totals.merge(best.drop(columns="route_id"), on=["lsoa21cd", "route_short_name"]).merge(
        near, on=["lsoa21cd", "route_short_name"])
    out["nearest_stop_m"] = out["nearest_stop_m"].round(0).astype(int)
    out["rank"] = out.groupby("lsoa21cd")["trips_in_area"].rank(method="first", ascending=False).astype(int)
    out = out.rename(columns={"lsoa21cd": "lsoa_code"}).sort_values(["lsoa_code", "rank"]).reset_index(drop=True)
    return out[["lsoa_code", "rank", "route_short_name", "destination_label", "agency_name", "is_night",
                "trips_in_area", "nearest_stop_name", "nearest_stop_m"]]


def _build_schools(project_root: Path, centres: pd.DataFrame) -> pd.DataFrame:
    sch = pd.read_csv(_silver(project_root, "schools"))
    sch = sch[~sch["is_special"]]
    if not INCLUDE_INDEPENDENT:
        sch = sch[~sch["is_independent"]]
    rows = []
    for group, phases in PHASE_GROUPS.items():
        s = sch[sch["phase"].isin(phases)].reset_index(drop=True)
        if s.empty:
            continue
        for start in range(0, len(centres), 500):
            c = centres.iloc[start:start + 500]
            d = np.hypot(c["easting"].to_numpy()[:, None] - s["easting"].to_numpy()[None, :],
                         c["northing"].to_numpy()[:, None] - s["northing"].to_numpy()[None, :])
            order = np.argsort(d, axis=1)[:, :SCHOOLS_PER_PHASE]
            for i, code in enumerate(c["lsoa_code"].to_numpy()):
                rank = 0
                for j in order[i]:
                    if d[i, j] > MAX_SCHOOL_DISTANCE_M:
                        break
                    rank += 1
                    r = s.iloc[j]
                    rows.append({
                        "lsoa_code": code, "phase_group": group, "rank_in_group": rank,
                        "school_name": r["school_name"], "phase": r["phase"],
                        "is_independent": bool(r["is_independent"]), "address": r["address"],
                        "distance_m": round(float(d[i, j])), "distance_miles": round(float(d[i, j]) / M_PER_MILE, 2),
                        "school_easting": r["easting"], "school_northing": r["northing"],
                    })
    return pd.DataFrame(rows)


def _build_station(project_root: Path, centres: pd.DataFrame) -> pd.DataFrame:
    st = pd.read_csv(_silver(project_root, "stations"))
    se, sn = TO_BNG.transform(st["lon"].to_numpy(), st["lat"].to_numpy())
    d = np.hypot(centres["easting"].to_numpy()[:, None] - np.asarray(se)[None, :],
                 centres["northing"].to_numpy()[:, None] - np.asarray(sn)[None, :])
    j = d.argmin(axis=1)
    dist = d[np.arange(len(centres)), j]
    return pd.DataFrame({
        "lsoa_code": centres["lsoa_code"].to_numpy(),
        "station_name": st["name"].to_numpy()[j],
        "distance_m": dist.round().astype(int),
        "walk_minutes_est": np.maximum(1, np.round(dist * WALK_CIRCUITY / WALK_M_PER_MIN)).astype(int),
    })


def build_gold_tables(project_root: Path, borough_filter=None):
    lsoas = _load_lsoas(project_root, borough_filter)
    centres = _build_centres(lsoas)
    print(f"  {len(centres)} LSOAs")
    _save_and_upload(project_root, centres, "centres")
    _save_and_upload(project_root, _build_buses(project_root, lsoas, centres), "buses")
    _save_and_upload(project_root, _build_schools(project_root, centres), "schools")
    _save_and_upload(project_root, _build_station(project_root, centres), "station")


# ----------------------------------------------------------------------------
# Cards
# ----------------------------------------------------------------------------

CARD_CSS = """
*{box-sizing:border-box}
body{margin:0;padding:24px;background:#e9edf3;font-family:'Segoe UI',system-ui,-apple-system,Arial,sans-serif;color:#0f172a}
.card{max-width:1040px;margin:0 auto;background:#f7f9fc;border-radius:16px;overflow:hidden;box-shadow:0 6px 24px rgba(15,23,42,.12)}
.head{background:#0f1d3a;color:#fff;padding:18px 24px;display:flex;align-items:center;gap:16px}
.head .ico{width:46px;height:46px;border:2px solid #fff;border-radius:11px;display:flex;align-items:center;justify-content:center}
.head h1{margin:0;font-size:22px;font-weight:700}
.head p{margin:3px 0 0;font-size:13px;color:#b8c4dc}
.body{display:grid;grid-template-columns:1fr 1.15fr;gap:24px;padding:20px 24px 8px}
h2{margin:0 0 12px;font-size:17px}
.row{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid #e3e8f0;border-radius:12px;padding:10px 14px;margin-bottom:9px}
.badge{min-width:46px;height:46px;border-radius:23px;background:#d9262c;color:#fff;font-weight:700;font-size:16px;display:flex;align-items:center;justify-content:center;padding:0 8px}
.dest{flex:1;font-size:15px;line-height:1.25}
.chev{color:#94a3b8;font-size:22px}
.more{font-size:13px;color:#64748b;margin:2px 2px 10px}
.station{display:flex;align-items:center;gap:14px;background:#e6edf8;border-radius:12px;padding:12px 14px;margin-top:8px}
.station .lbl{font-size:12px;color:#64748b}
.station .nm{font-size:17px;font-weight:700}
.station .wk{font-size:13px;color:#334155}
.map img{width:100%;display:block;border-radius:12px}
.group{font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin:14px 0 7px}
.school{display:flex;align-items:center;gap:12px;background:#fff;border:1px solid #e3e8f0;border-radius:10px;padding:9px 12px;margin-bottom:7px}
.school .nm{font-size:14.5px;line-height:1.2}
.school .sub{font-size:12px;color:#64748b;margin-top:2px}
.school .grow{flex:1}
.school .mi{font-size:13.5px;color:#334155;white-space:nowrap}
.empty{font-size:14px;color:#64748b;background:#fff;border:1px dashed #cbd5e1;border-radius:12px;padding:14px}
.foot{padding:6px 24px 18px;font-size:12px;color:#64748b;line-height:1.45}
"""

CARD_TEMPLATE = Template("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Transport &amp; schools nearby - $lsoa_code</title>
<style>$css</style></head><body>
<div class="card">
  <div class="head">
    <div class="ico"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8"><rect x="4" y="3" width="16" height="15" rx="3"/><path d="M4 11h16M8 21v-3M16 21v-3"/><circle cx="8" cy="14.5" r="1" fill="#fff"/><circle cx="16" cy="14.5" r="1" fill="#fff"/></svg></div>
    <div><h1>Transport &amp; schools nearby</h1><p>$subtitle</p></div>
  </div>
  <div class="body">
    <div>
      <h2>Buses serving the area</h2>
      $buses_html
      $station_html
    </div>
    <div>
      <h2>Schools nearby</h2>
      $schools_html
    </div>
  </div>
  <div class="foot">$footnote</div>
</div></body></html>
""")

_TRIANGLE = ('<svg width="20" height="20" viewBox="0 0 20 20"><path d="M10 3 L18 17 H2 Z" fill="#22c55e"/></svg>')
_STATION_ICON = ('<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#0f1d3a" stroke-width="1.7">'
                 '<rect x="4" y="3" width="16" height="14" rx="3"/><path d="M4 11h16M8 21l2-4M16 21l-2-4"/></svg>')


def _esc(v) -> str:
    return html.escape("" if pd.isna(v) else str(v))


def _buses_html(buses: pd.DataFrame) -> str:
    if buses.empty:
        return '<div class="empty">No bus stops within about 200 m of this area.</div>'
    day = buses[~buses["is_night"]].sort_values("rank")
    night_n = int(buses["is_night"].sum())
    shown = day.head(MAX_BUSES_SHOWN)
    rows = "".join(
        f'<div class="row"><div class="badge">{_esc(r.route_short_name)}</div>'
        f'<div class="dest">{_esc(r.destination_label)}</div><div class="chev">&rsaquo;</div></div>'
        for r in shown.itertuples())
    extra = []
    if len(day) > len(shown):
        extra.append(f"+ {len(day) - len(shown)} more routes")
    if night_n:
        extra.append(f"{night_n} night bus{'es' if night_n != 1 else ''} also serve{'' if night_n != 1 else 's'} this area")
    return rows + (f'<div class="more">{" &middot; ".join(extra)}</div>' if extra else "")


def _station_html(station: pd.Series | None) -> str:
    if station is None:
        return ""
    return (f'<div class="station">{_STATION_ICON}<div><div class="lbl">Nearest station</div>'
            f'<div class="nm">{_esc(station["station_name"])}</div>'
            f'<div class="wk">about {int(station["walk_minutes_est"])} min walk</div></div></div>')


def _schools_html(schools: pd.DataFrame, map_b64: str | None) -> str:
    out = ""
    if map_b64:
        out += f'<div class="map"><img alt="Map of nearby schools" src="data:image/png;base64,{map_b64}"></div>'
    if schools.empty:
        return out + '<div class="empty">No schools found within 3 miles.</div>'
    for group in PHASE_GROUPS:
        g = schools[schools["phase_group"] == group].sort_values("rank_in_group")
        if g.empty:
            continue
        out += f'<div class="group">{group}</div>'
        for r in g.itertuples():
            sub = " &middot; ".join(p for p in [_esc(r.phase), _esc(r.address)] if p)
            out += (f'<div class="school">{_TRIANGLE}<div class="grow"><div class="nm">{_esc(r.school_name)}</div>'
                    f'<div class="sub">{sub}</div></div><div class="mi">{r.distance_miles:.1f} miles</div></div>')
    return out


def _feed_note(project_root: Path) -> str:
    p = project_root / "data" / "B_bronze" / PIPE_NAME / "ingestion_feed_info.csv"
    if not p.exists():
        return ""
    fi = pd.read_csv(p, dtype=str).iloc[0]
    end = fi.get("feed_end_date")
    try:
        return f" Bus timetable data valid to {datetime.strptime(end, '%Y%m%d').strftime('%d %b %Y')}."
    except (TypeError, ValueError):
        return ""


def build_card_html(project_root: Path, centre: pd.Series, buses, schools, station, map_png: Path | None) -> str:
    map_b64 = base64.b64encode(map_png.read_bytes()).decode() if map_png and map_png.exists() else None
    subtitle = f"{_esc(centre['lsoa_name'])} &middot; useful connections and local schools at a glance"
    footnote = ("Buses shown have a stop within about 200 m of this area. Distances are in a straight line from the "
                "centre of the area, and walk times are estimates - check live times before you travel."
                + _feed_note(project_root))
    return CARD_TEMPLATE.substitute(
        lsoa_code=_esc(centre["lsoa_code"]), css=CARD_CSS, subtitle=subtitle,
        buses_html=_buses_html(buses), station_html=_station_html(station),
        schools_html=_schools_html(schools, map_b64), footnote=footnote)


def _r_literal(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def render_cards(project_root: Path, borough_filter=None, lsoa_limit=None, lsoa_codes=None):
    """lsoa_limit: first N LSOAs per borough (smoke test). lsoa_codes: explicit list, overrides lsoa_limit."""
    gold = _gold_dir(project_root)
    centres = pd.read_csv(gold / "gold_lsoa_nearby_centres.csv")
    buses = pd.read_csv(gold / "gold_lsoa_nearby_buses.csv")
    schools = pd.read_csv(gold / "gold_lsoa_nearby_schools.csv")
    stations = pd.read_csv(gold / "gold_lsoa_nearby_station.csv").set_index("lsoa_code")

    if borough_filter:
        centres = centres[centres["borough_name"].isin(borough_filter)]
    selected = []
    for borough, grp in centres.groupby("borough_name", sort=True):
        codes = list(grp["lsoa_code"])
        if lsoa_codes:
            codes = [c for c in codes if c in lsoa_codes]
        elif lsoa_limit:
            codes = codes[:lsoa_limit]
        if codes:
            selected.append((borough, codes))

    maps_dir = gold / "maps"
    cards_dir = gold / "cards"
    r_script = project_root / "pipes" / PIPE_NAME / R_MAP_SCRIPT

    for borough, codes in selected:
        print(f"\n--- {borough}: {len(codes)} card(s) ---")
        codes_r = "c(" + ", ".join(_r_literal(c) for c in codes) + ")"
        r_expr = (
            "RUN_ON_SOURCE <- FALSE; "
            f"source({_r_literal(r_script.as_posix())}); "
            "render_schools_maps_for_borough("
            f"borough_name = {_r_literal(borough)}, lsoa_codes = {codes_r}, "
            f"centres_csv = {_r_literal((gold / 'gold_lsoa_nearby_centres.csv').as_posix())}, "
            f"schools_csv = {_r_literal((gold / 'gold_lsoa_nearby_schools.csv').as_posix())}, "
            f"output_dir = {_r_literal(maps_dir.as_posix())}, "
            f"gpkg_path = {_r_literal((project_root / OSM_GPKG_REL).as_posix())})"
        )
        res = subprocess.run([RSCRIPT_BIN, "-e", r_expr], cwd=project_root, capture_output=True, text=True)
        print(res.stdout)
        if res.returncode != 0:
            print(f"  [ERROR] map render failed for {borough}:\n{res.stderr}")

        slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in borough)
        while "__" in slug:
            slug = slug.replace("__", "_")
        slug = slug.strip("_")
        (cards_dir / slug).mkdir(parents=True, exist_ok=True)
        for code in codes:
            centre = centres[centres["lsoa_code"] == code].iloc[0]
            st = stations.loc[code] if code in stations.index else None
            doc = build_card_html(
                project_root, centre,
                buses[buses["lsoa_code"] == code], schools[schools["lsoa_code"] == code], st,
                maps_dir / slug / f"{code}.png")
            (cards_dir / slug / f"{code}.html").write_text(doc, encoding="utf-8")
            print(f"  card -> {slug}/{code}.html")


def run_pipeline(project_root: Path, borough_filter=None, lsoa_limit=None, lsoa_codes=None):
    build_gold_tables(project_root, borough_filter)
    render_cards(project_root, borough_filter, lsoa_limit, lsoa_codes)


if __name__ == "__main__":
    run_pipeline(Path(__file__).resolve().parents[2])
