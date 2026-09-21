# Exports every railway station/halt in Greater London (tube, rail, DLR, overground,
# Elizabeth line...) from the already-downloaded Geofabrik extract that
# infrastructure_map cached, so Python can use them.
#
# Uses the whole-London extract rather than the per-borough osm_stations_*.rds files:
# those were only built for 30 of the 33 boroughs (Barking & Dagenham, Hammersmith &
# Fulham and Kensington & Chelsea are missing) and are clipped at each borough edge,
# which would make "nearest station" wrong near boundaries.
#
# Read-only: same place/layer/extra_tags as infrastructure_map's cache, so osmextract
# reuses the existing .gpkg instead of re-downloading or rewriting it.
# Usage: Rscript r_export_stations.R <cache_dir> <out_csv>

suppressPackageStartupMessages({
  library(sf)
  library(dplyr)
  library(osmextract)
})

args      <- commandArgs(trailingOnly = TRUE)
cache_dir <- file.path(args[1], "_osmextract_cache")
out_csv   <- args[2]

pts <- osmextract::oe_get(
  place              = "Greater London",
  provider           = "geofabrik",
  layer              = "points",
  download_directory = cache_dir,
  extra_tags         = c("railway", "public_transport"),
  query              = "SELECT * FROM points WHERE railway IN ('station', 'halt') AND name IS NOT NULL",
  force_download        = FALSE,
  force_vectortranslate = FALSE,
  quiet              = TRUE
)
cat(sprintf("Read %d station/halt nodes\n", nrow(pts)))

pts <- st_transform(pts, 4326)
xy  <- st_coordinates(pts)
stations <- data.frame(name = pts$name, lon = xy[, 1], lat = xy[, 2], stringsAsFactors = FALSE) %>%
  filter(name != "") %>%
  distinct(name, lon = round(lon, 4), lat = round(lat, 4))

dir.create(dirname(out_csv), recursive = TRUE, showWarnings = FALSE)
write.csv(stations, out_csv, row.names = FALSE)
cat(sprintf("Wrote %d stations to %s\n", nrow(stations), out_csv))
