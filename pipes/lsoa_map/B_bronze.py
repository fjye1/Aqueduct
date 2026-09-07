import geopandas as gpd
from pathlib import Path

# Path relative to this script's own location
shp_path = Path(__file__).parent / "Barnet.shp"

print(shp_path.exists())        # should print True
print(list(shp_path.parent.iterdir()))  # lists everything in that folder
gdf = gpd.read_file(shp_path)
print(gdf.columns.tolist())
print(gdf)