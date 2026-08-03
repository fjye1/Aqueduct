from pathlib import Path

# market_pressure_index
# from pipes.market_pressure_index.B_bronze import run_pipeline
# from pipes.market_pressure_index.C_silver import run_pipeline

# # council_Budget
# from pipes.council_budget.B_bronze import run_pipeline
# from pipes.council_budget.C_silver import run_pipeline

# Housing
# from pipes.housing.B_bronze import run_pipeline
# from pipes.housing.C_silver import run_pipeline
# from pipes.housing.D_gold import run_pipeline

#Infrastructure
# from pipes.infrastructure.B_bronze import run_pipeline
# from pipes.infrastructure.C_silver import run_pipeline
# from pipes.infrastructure.D_gold import run_pipeline

#Education
# from pipes.education.B_bronze import run_pipeline
# from pipes.education.C_silver import run_pipeline
# from pipes.education.D_gold import run_pipeline

#Police
# from pipes.police.B_bronze import run_pipeline
# from pipes.police.C_silver import run_pipeline
# from pipes.police.D_gold import run_pipeline



# Infrastructure_map
# from pipes.infrastructure_map.B_bronze import run_pipeline
# from pipes.infrastructure_map.C_silver import run_pipeline
#
# PROJECT_ROOT = Path(__file__).resolve().parent
#
# run_pipeline(PROJECT_ROOT)








"""
Build a bus-stop network diagram on a borough map.

Data needed (all already gathered):
  - GTFS folder: stops.txt, stop_times.txt, trips.txt, routes.txt
  - NaPTAN CSV filtered to your borough's stops (needs ATCOCode, Latitude, Longitude)
  - Borough boundary as GeoJSON / shapefile

Edit the CONFIG block below, then run: python build_bus_network.py
"""

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

# ============ CONFIG - edit these ============
GTFS_DIR = "data/A_raw/infrastructure_map/itm_london_gtfs"                              # folder containing GTFS .txt files
NAPTAN_CSV = "data/C_silver/infrastructure_map/test.csv"          # your borough-filtered NaPTAN stops
BOROUGH_SHAPE = "data/A_raw/infrastructure/london_boroughs.shp" # your borough polygon
OUTPUT_PNG = "bus_network_map.png"
# ================================================


# --- 1. Load borough boundary and reproject to WGS84 (lat/lon) if needed ---
BOROUGH_NAME = 'City of London'  # <-- set this to whichever borough you're mapping

boroughs_all = gpd.read_file(BOROUGH_SHAPE)
if boroughs_all.crs is not None and boroughs_all.crs.to_epsg() != 4326:
    boroughs_all = boroughs_all.to_crs(epsg=4326)

# check the actual column name first if this errors — likely 'NAME' or similar
borough = boroughs_all[boroughs_all["BOROUGH"] == BOROUGH_NAME]

# --- 2. Load your borough's stops from NaPTAN ---
naptan = pd.read_csv(NAPTAN_CSV)
borough_stop_ids = set(naptan["ATCOCode"].astype(str))

# --- 3. Load GTFS tables ---
stop_times = pd.read_csv(f"{GTFS_DIR}/stop_times.txt", dtype={"stop_id": str, "trip_id": str})
trips = pd.read_csv(f"{GTFS_DIR}/trips.txt", dtype={"trip_id": str, "route_id": str})
routes = pd.read_csv(f"{GTFS_DIR}/routes.txt", dtype={"route_id": str})
stops = pd.read_csv(f"{GTFS_DIR}/stops.txt", dtype={"stop_id": str})

# --- 4. Keep only trips that pass through the borough at all ---
trips_touching_borough = stop_times.loc[
    stop_times["stop_id"].isin(borough_stop_ids), "trip_id"
].unique()
st = stop_times[stop_times["trip_id"].isin(trips_touching_borough)].sort_values(
    ["trip_id", "stop_sequence"]
)

# --- 5. Build an edge for every consecutive stop pair within each trip ---
edge_rows = []
for trip_id, grp in st.groupby("trip_id"):
    stop_seq = grp.sort_values("stop_sequence")["stop_id"].tolist()
    for a, b in zip(stop_seq[:-1], stop_seq[1:]):
        edge_rows.append((trip_id, a, b))

edges = pd.DataFrame(edge_rows, columns=["trip_id", "from_stop", "to_stop"])

# --- 6. Keep edges where AT LEAST ONE end is inside the borough ---
#     (this keeps the "last hop before leaving" / "first hop after entering" edges,
#     rather than silently dropping them)
edges = edges[
    edges["from_stop"].isin(borough_stop_ids) | edges["to_stop"].isin(borough_stop_ids)
    ]

# flag which edges actually leave the borough, so we can style them differently
edges["crosses_boundary"] = ~(
        edges["from_stop"].isin(borough_stop_ids) & edges["to_stop"].isin(borough_stop_ids)
)

# --- 7. Attach route info and count how many trips use each edge ---
edges = edges.merge(trips[["trip_id", "route_id"]], on="trip_id", how="left")
edge_counts = (
    edges.groupby(["from_stop", "to_stop"])
    .agg(trip_count=("trip_id", "nunique"), routes=("route_id", lambda x: sorted(set(x))))
    .reset_index()
)

# --- 8. Attach coordinates ---
coords = stops.set_index("stop_id")[["stop_lat", "stop_lon"]]
edge_counts = edge_counts.join(coords, on="from_stop").rename(
    columns={"stop_lat": "from_lat", "stop_lon": "from_lon"}
)
edge_counts = edge_counts.join(coords, on="to_stop").rename(
    columns={"stop_lat": "to_lat", "stop_lon": "to_lon"}
)

print(f"Stops in borough: {len(borough_stop_ids)}")
print(f"Trips touching borough: {len(trips_touching_borough)}")
print(f"Unique edges (stop-to-stop connections): {len(edge_counts)}")

# --- 9. Plot: borough outline, stops, and edges weighted by frequency ---
fig, ax = plt.subplots(figsize=(10, 10))
borough.boundary.plot(ax=ax, color="black", linewidth=1.2)

max_count = edge_counts["trip_count"].max() if len(edge_counts) else 1
for _, row in edge_counts.iterrows():
    ax.plot(
        [row["from_lon"], row["to_lon"]],
        [row["from_lat"], row["to_lat"]],
        linewidth=0.5 + 3 * (row["trip_count"] / max_count),
        color="steelblue",
        alpha=0.6,
        zorder=2,
    )

stops_gdf = gpd.GeoDataFrame(
    naptan,
    geometry=gpd.points_from_xy(naptan["Longitude"], naptan["Latitude"]),
    crs="EPSG:4326",
)
stops_gdf.plot(ax=ax, color="crimson", markersize=15, zorder=3)

ax.set_title("Bus stop network")
ax.set_axis_off()
plt.tight_layout()
plt.savefig(OUTPUT_PNG, dpi=200)
print(f"Saved map to {OUTPUT_PNG}")
