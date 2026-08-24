# ==============================================================================
# Bus Stop Network Diagram in R - overlaid on real OSM streets, with bus edges
# snapped to the road network and major train/tube stations labelled.
#
# Dependencies: install.packages(c("tidyverse", "sf", "viridis",
#                                   "osmdata", "dodgr", "ggrepel", "osmextract"))
#
# OSM street/station data is sourced from a single local Greater London OSM
# extract (via osmextract, downloaded once from Geofabrik and cached under
# OSM_CACHE_DIR_DEFAULT/_osmextract_cache) instead of live per-borough
# Overpass API calls - see download_osm_streets()/download_osm_stations()
# below. This avoids the 504 Gateway Timeouts larger boroughs (e.g. Barnet)
# were hitting on the public Overpass mirrors: after the one-time regional
# download, every borough is just a local spatial filter, no network calls.
#
# This is a copy of r_bus_map.R - see that file for the original
# straight-line / borough-outline-only version.
#
# Usage:
#   Sourced directly -> renders DEFAULT_BOROUGH_NAME once (back-compat).
#   Sourced by a driver script that sets RUN_ON_SOURCE <- FALSE first ->
#   only defines render_borough_bus_network(), which the driver can then
#   call once per borough, e.g.:
#
#     RUN_ON_SOURCE <- FALSE
#     source("pipes/infrastructure_map/r_bus_map_streets.R")
#     naptan_all <- readr::read_csv(NAPTAN_CSV_DEFAULT, show_col_types = FALSE)
#     borough_names <- sort(unique(naptan_all$BOROUGH))
#     for (b in borough_names) render_borough_bus_network(b)
# ==============================================================================

#options(download.file.method = "wininet")
#install.packages(c("tidyverse", "sf", "viridis", "osmdata", "dodgr", "ggrepel", "osmextract"))


suppressPackageStartupMessages({
  library(tidyverse)
  library(sf)
  library(viridis)
  library(osmdata)
  library(dodgr)
  library(ggrepel)
  library(osmextract)
})

# ============ DEFAULTS - override via render_borough_bus_network() args ============
GTFS_DIR_DEFAULT     <- "data/A_raw/infrastructure_map/itm_london_gtfs"
# NOTE: test.csv only contains City of London stops. For any other borough,
# pass naptan_csv = "data/C_silver/infrastructure_map/extraction_transport_stops.csv"
# (the full London-wide NaPTAN extract - see BOROUGH filtering below).
NAPTAN_CSV_DEFAULT   <- "data/C_silver/infrastructure_map/test.csv"
BOROUGH_SHP_DEFAULT  <- "data/A_raw/infrastructure/london_boroughs.shp"
DEFAULT_BOROUGH_NAME <- "City of London"
OUTPUT_DIR_DEFAULT   <- "."

# Edges at/above this quantile of trip_count are styled as "major" routes
# (thick glowing purple), everything else as "other" (thin blue).
MAJOR_ROUTE_QUANTILE_DEFAULT <- 0.75

# --- Dark dashboard-style palette (matches example_infra_page.PNG) ---
BG_COLOR       <- "#0a0e1a"
STREET_COLOR   <- "#28303f"
BOROUGH_COLOR  <- "#8b5cf6"
MAJOR_COLOR    <- "#b446f0"
OTHER_COLOR    <- "#2f8fe0"
STOP_COLOR     <- "#ff3b3b"
STATION_COLOR  <- "#ffffff"
TEXT_COLOR     <- "#e5e7eb"
SUBTEXT_COLOR  <- "#9ca3af"

# OSM data is extracted from a single local Greater London OSM file (see
# .oe_get_layer() below) and cached per-borough to disk so re-runs don't
# have to re-extract every time. Cache files are keyed per-borough.
OSM_CACHE_DIR_DEFAULT <- "data/A_raw/infrastructure_map"
# ==================================================


# Turns "Kingston upon Thames" -> "kingston_upon_thames" so it's safe to use
# in cache filenames and output filenames.
slugify_borough <- function(borough_name) {
  slug <- tolower(borough_name)
  slug <- gsub("[^a-z0-9]+", "_", slug)
  gsub("^_+|_+$", "", slug)
}


# Loads the borough shapefile and returns the WGS84 bbox for a single
# borough. Shared by the two download_osm_*() functions below so each can be
# called standalone (e.g. from its own Rscript subprocess) without needing
# the rest of render_borough_bus_network()'s state.
get_borough_bbox <- function(borough_name, borough_shp = BOROUGH_SHP_DEFAULT) {
  boroughs_all <- st_read(borough_shp, quiet = TRUE) %>%
    st_transform(crs = 4326)

  borough <- boroughs_all %>% filter(BOROUGH == borough_name)

  if (nrow(borough) == 0) {
    stop(sprintf("Borough '%s' not found in %s (BOROUGH column)", borough_name, borough_shp))
  }

  st_bbox(borough)
}


# Same as get_borough_bbox() above, but returns the borough polygon itself
# (WGS84), buffered outward slightly so the clipped street/station layers
# still include a bit of the surrounding road network right at the border -
# equivalent to dodgr_streetnet()'s old `expand` bbox argument. Buffering is
# done in a metric CRS (British National Grid) so buffer_m is a real distance.
get_borough_polygon <- function(borough_name, borough_shp = BOROUGH_SHP_DEFAULT, buffer_m = 300) {
  boroughs_all <- st_read(borough_shp, quiet = TRUE)

  borough <- boroughs_all %>% filter(BOROUGH == borough_name)
  if (nrow(borough) == 0) {
    stop(sprintf("Borough '%s' not found in %s (BOROUGH column)", borough_name, borough_shp))
  }

  borough %>%
    st_transform(crs = 27700) %>%   # British National Grid, units = metres
    st_buffer(buffer_m) %>%
    st_transform(crs = 4326) %>%
    st_geometry()
}


# Loads one region-wide OSM layer ("lines" or "points") from a single local
# Greater London extract. osmextract downloads the underlying .pbf/.gpkg
# from Geofabrik on first use and caches it under
# file.path(cache_dir, "_osmextract_cache") - every call after that (any
# borough, either layer) just reads the cached file back from disk, so there
# is only ever one real network request across an entire pipeline run.
.oe_get_layer <- function(layer, cache_dir, extra_tags) {
  osmextract_cache_dir <- file.path(cache_dir, "_osmextract_cache")
  dir.create(osmextract_cache_dir, recursive = TRUE, showWarnings = FALSE)

  osmextract::oe_get(
    place              = "Greater London",
    provider           = "geofabrik",
    layer              = layer,
    download_directory = osmextract_cache_dir,
    extra_tags         = extra_tags,
    quiet              = TRUE,
    force_download          = FALSE,
    force_vectortranslate    = FALSE
  )
}


# --- Loads (or extracts from the local cache) the OSM street network for a
#     single borough. Independent of download_osm_stations() below - each
#     caches to its own .rds file, so a problem with one (e.g. a bad borough
#     match) doesn't take out the other or anything already cached.
#     `overpass_url` is kept as an accepted-but-ignored argument for
#     backward compatibility with existing call sites/driver scripts. ---
download_osm_streets <- function(borough_name,
                                  borough_shp = BOROUGH_SHP_DEFAULT,
                                  cache_dir   = OSM_CACHE_DIR_DEFAULT,
                                  force       = FALSE,
                                  overpass_url = NULL) {
  slug        <- slugify_borough(borough_name)
  streets_rds <- file.path(cache_dir, sprintf("osm_streets_%s.rds", slug))
  dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)

  if (!force && file.exists(streets_rds)) {
    cat(sprintf("[streets] %s: already cached, skipping.\n", borough_name))
    return(invisible(streets_rds))
  }

  cat(sprintf("[streets] %s: extracting from local Greater London OSM extract...\n", borough_name))

  boundary <- get_borough_polygon(borough_name, borough_shp)
  lines    <- .oe_get_layer("lines", cache_dir, extra_tags = c("highway", "oneway", "maxspeed", "lanes"))

  streets_sf <- lines[!is.na(lines$highway), ]
  streets_sf <- sf::st_transform(streets_sf, 4326)
  streets_sf <- suppressWarnings(sf::st_intersection(streets_sf, boundary))
  # osmextract can return MULTILINESTRING geometries where osmdata returned
  # simple LINESTRINGs - dodgr::weight_streetnet() expects the latter.
  streets_sf <- suppressWarnings(sf::st_cast(streets_sf, "LINESTRING"))

  if (nrow(streets_sf) == 0) {
    stop(sprintf("[streets] %s: no street segments found after clipping - check BOROUGH name / shapefile match", borough_name))
  }

  saveRDS(streets_sf, streets_rds)
  cat(sprintf("[streets] %s: saved %d segments to %s\n", borough_name, nrow(streets_sf), streets_rds))

  invisible(streets_rds)
}


# --- Loads (or extracts from the local cache) OSM train/tube stations for a
#     single borough. See download_osm_streets() above for why this is
#     separate, and for the `overpass_url` back-compat note. ---
download_osm_stations <- function(borough_name,
                                   borough_shp = BOROUGH_SHP_DEFAULT,
                                   cache_dir   = OSM_CACHE_DIR_DEFAULT,
                                   force       = FALSE,
                                   overpass_url = NULL) {
  slug         <- slugify_borough(borough_name)
  stations_rds <- file.path(cache_dir, sprintf("osm_stations_%s.rds", slug))
  dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)

  if (!force && file.exists(stations_rds)) {
    cat(sprintf("[stations] %s: already cached, skipping.\n", borough_name))
    return(invisible(stations_rds))
  }

  cat(sprintf("[stations] %s: extracting from local Greater London OSM extract...\n", borough_name))

  boundary <- get_borough_polygon(borough_name, borough_shp)
  points   <- .oe_get_layer("points", cache_dir, extra_tags = c("railway", "public_transport"))

  is_station <- !is.na(points$railway) & points$railway %in% c("station", "halt")
  stations_raw <- points[is_station, ]
  stations_raw <- sf::st_transform(stations_raw, 4326)
  stations_raw <- suppressWarnings(sf::st_intersection(stations_raw, boundary))

  station_points <- stations_raw %>%
    filter(!is.na(name)) %>%
    select(name) %>%
    # collapse duplicate entrances/nodes sharing the same station name
    group_by(name) %>%
    summarise(geometry = st_centroid(st_union(geometry)), .groups = "drop") %>%
    st_as_sf()

  saveRDS(station_points, stations_rds)
  cat(sprintf("[stations] %s: saved %d stations to %s\n", borough_name, nrow(station_points), stations_rds))

  invisible(stations_rds)
}


# --- Renders the internal bus network map for a single borough. ---
render_borough_bus_network <- function(borough_name,
                                        gtfs_dir     = GTFS_DIR_DEFAULT,
                                        naptan_csv   = NAPTAN_CSV_DEFAULT,
                                        borough_shp  = BOROUGH_SHP_DEFAULT,
                                        output_dir   = OUTPUT_DIR_DEFAULT,
                                        cache_dir    = OSM_CACHE_DIR_DEFAULT,
                                        major_route_quantile = MAJOR_ROUTE_QUANTILE_DEFAULT) {

  slug       <- slugify_borough(borough_name)
  output_png <- file.path(output_dir, sprintf("bus_network_map_r_dark_%s.png", slug))

  cat(sprintf("\n=== Rendering borough: %s ===\n", borough_name))

  # --- 1. Load borough boundary and reproject to WGS84 (EPSG:4326) ---
  boroughs_all <- st_read(borough_shp, quiet = TRUE) %>%
    st_transform(crs = 4326)

  borough <- boroughs_all %>%
    filter(BOROUGH == borough_name)

  if (nrow(borough) == 0) {
    stop(sprintf("Borough '%s' not found in %s (BOROUGH column)", borough_name, borough_shp))
  }


  # --- 2. Load borough's stops from NaPTAN ---
  naptan_raw <- read_csv(naptan_csv, show_col_types = FALSE)

  # Different pipeline runs have emitted this file with different column
  # casing (ATCOCode/Longitude/Latitude vs atcoCode/lon/lat) - normalise so
  # the rest of the function can rely on one consistent set of names.
  rename_lookup <- c(ATCOCode = "atcoCode", Longitude = "lon", Latitude = "lat")
  for (canonical in names(rename_lookup)) {
    legacy <- rename_lookup[[canonical]]
    if (!canonical %in% names(naptan_raw) && legacy %in% names(naptan_raw)) {
      naptan_raw <- naptan_raw %>% rename(!!canonical := !!legacy)
    }
  }

  # Some NaPTAN extracts (e.g. test.csv) are already pre-filtered to a single
  # borough; the full London-wide extract is not, so filter explicitly here
  # whenever a BOROUGH column is present.
  naptan <- if ("BOROUGH" %in% names(naptan_raw)) {
    naptan_raw %>% filter(BOROUGH == borough_name)
  } else {
    naptan_raw
  }

  if (nrow(naptan) == 0) {
    stop(sprintf("No NaPTAN stops found for borough '%s' in %s", borough_name, naptan_csv))
  }

  borough_stop_ids <- as.character(naptan$ATCOCode)



  # --- 3. Load GTFS tables ---
  stop_times <- read_csv(file.path(gtfs_dir, "stop_times.txt"), col_types = cols(stop_id = "c", trip_id = "c"))
  trips      <- read_csv(file.path(gtfs_dir, "trips.txt"), col_types = cols(trip_id = "c", route_id = "c"))
  routes     <- read_csv(file.path(gtfs_dir, "routes.txt"), col_types = cols(route_id = "c"))
  stops      <- read_csv(file.path(gtfs_dir, "stops.txt"), col_types = cols(stop_id = "c"))


  # --- 4. Keep only trips that pass through the borough at all ---
  trips_touching_borough <- stop_times %>%
    filter(stop_id %in% borough_stop_ids) %>%
    pull(trip_id) %>%
    unique()

  st <- stop_times %>%
    filter(trip_id %in% trips_touching_borough) %>%
    arrange(trip_id, stop_sequence)


  # --- 5 & 6. Build consecutive edges per trip (INTERNAL ONLY) ---
  edges <- st %>%
    group_by(trip_id) %>%
    mutate(to_stop = lead(stop_id)) %>%
    rename(from_stop = stop_id) %>%
    filter(!is.na(to_stop)) %>%
    ungroup() %>%
    # >>> MODIFIED: BOTH ends must strictly be inside the borough <<<
    filter(from_stop %in% borough_stop_ids & to_stop %in% borough_stop_ids)


  # --- 7. Attach route info and count frequency per edge ---
  edges <- edges %>%
    left_join(trips %>% select(trip_id, route_id), by = "trip_id")

  edge_counts <- edges %>%
    group_by(from_stop, to_stop) %>%
    summarise(
      trip_count = n_distinct(trip_id),
      routes     = list(unique(route_id)),
      .groups    = "drop"
    )


  # --- 8. Attach coordinates ---
  coords <- stops %>% select(stop_id, stop_lat, stop_lon)

  edge_counts <- edge_counts %>%
    left_join(coords, by = c("from_stop" = "stop_id")) %>%
    rename(from_lat = stop_lat, from_lon = stop_lon) %>%
    left_join(coords, by = c("to_stop" = "stop_id")) %>%
    rename(to_lat = stop_lat, to_lon = stop_lon) %>%
    filter(!is.na(from_lon) & !is.na(to_lon) & !is.na(from_lat) & !is.na(to_lat))

  if (nrow(edge_counts) == 0) {
    stop(sprintf("No internal bus edges found for borough '%s' - nothing to plot", borough_name))
  }


  # --- 9. Pull the real OSM street network + stations for the borough
  #         (cached to disk). Each is downloaded separately via
  #         download_osm_streets()/download_osm_stations() - see those for
  #         why - here we just load whatever's on disk after either call. ---
  streets_sf  <- readRDS(download_osm_streets(borough_name, borough_shp, cache_dir))
  stations_sf <- readRDS(download_osm_stations(borough_name, borough_shp, cache_dir))

  cat(sprintf("Street segments loaded: %d\n", nrow(streets_sf)))
  cat(sprintf("Stations found: %d\n", nrow(stations_sf)))


  # --- 10. Build a routable graph from the street network and snap each bus
  #         edge to the shortest path along real streets ---
  cat("Building routable street graph...\n")
  graph <- weight_streetnet(streets_sf, wt_profile = "motorcar")
  verts <- dodgr_vertices(graph)

  route_edge <- function(from_lon, from_lat, to_lon, to_lat) {
    # dodgr requires named x/y columns to recognise a matrix as coordinates -
    # an unnamed matrix fails silently with "Unable to determine geographical
    # coordinates", which was previously being swallowed by tryCatch below.
    from_pt <- matrix(c(from_lon, from_lat), ncol = 2, dimnames = list(NULL, c("x", "y")))
    to_pt   <- matrix(c(to_lon, to_lat), ncol = 2, dimnames = list(NULL, c("x", "y")))

    path <- tryCatch(
      dodgr_paths(graph, from = from_pt, to = to_pt, vertices = TRUE),
      error = function(e) {
        cat(sprintf("  [routing error] %s\n", conditionMessage(e)))
        NULL
      }
    )

    vertex_ids <- tryCatch(path[[1]][[1]], error = function(e) NULL)

    if (is.null(vertex_ids) || length(vertex_ids) < 2) {
      # No route found (e.g. disconnected stop) - fall back to a straight line
      return(list(geom = st_linestring(rbind(c(from_lon, from_lat), c(to_lon, to_lat))), status = "fallback_no_path"))
    }

    pts <- verts[match(vertex_ids, verts$id), c("x", "y")]
    status <- if (length(vertex_ids) <= 2) "direct_2vertex" else "routed"
    list(geom = st_linestring(as.matrix(pts)), status = status)
  }

  cat(sprintf("Routing %d unique bus edges along streets...\n", nrow(edge_counts)))
  lines_list <- vector("list", nrow(edge_counts))
  status_vec <- character(nrow(edge_counts))
  for (i in seq_len(nrow(edge_counts))) {
    result <- route_edge(
      edge_counts$from_lon[i], edge_counts$from_lat[i],
      edge_counts$to_lon[i],   edge_counts$to_lat[i]
    )
    lines_list[[i]] <- result$geom
    status_vec[i] <- result$status
    if (i %% 50 == 0) cat(sprintf("  ...%d / %d\n", i, nrow(edge_counts)))
  }
  cat("Routing outcome breakdown:\n")
  print(table(status_vec))

  major_cutoff <- quantile(edge_counts$trip_count, major_route_quantile)

  edges_sf <- edge_counts %>%
    mutate(
      geometry   = st_sfc(lines_list, crs = 4326),
      route_tier = if_else(trip_count >= major_cutoff, "major", "other")
    ) %>%
    st_as_sf()

  cat(sprintf("Major routes (>= %.0f trips): %d / %d\n",
              major_cutoff, sum(edges_sf$route_tier == "major"), nrow(edges_sf)))

  # Only keep NaPTAN bus stops that are active in our internal network
  active_stop_ids <- unique(c(edge_counts$from_stop, edge_counts$to_stop))
  stops_sf <- naptan %>%
    filter(ATCOCode %in% active_stop_ids) %>%
    st_as_sf(coords = c("Longitude", "Latitude"), crs = 4326)

  # Keep only stations that actually fall within the borough for labelling
  stations_sf <- stations_sf %>%
    st_filter(borough)

  cat(sprintf("Internal stops in network: %d\n", nrow(stops_sf)))
  cat(sprintf("Internal trips counted: %d\n", length(unique(edges$trip_id))))
  cat(sprintf("Unique internal edges: %d\n", nrow(edge_counts)))
  cat(sprintf("Stations labelled: %d\n", nrow(stations_sf)))


  # --- 11. Plotting with ggplot2 - dark "connectivity dashboard" style ---
  major_edges <- edges_sf %>% filter(route_tier == "major")
  other_edges <- edges_sf %>% filter(route_tier == "other")

  network_map <- ggplot() +
    # Layer 1: Borough fill (near-black, just barely lighter than the page bg)
    geom_sf(data = borough, fill = "#0d1220", color = NA) +

    # Layer 2: Real OSM street network as a faint basemap
    geom_sf(data = streets_sf, color = STREET_COLOR, linewidth = 0.15, alpha = 0.55) +

    # Layer 3: Borough boundary, glowing purple outline (stacked translucent
    # strokes underneath a crisp top stroke fake a neon glow)
    geom_sf(data = borough, fill = NA, color = BOROUGH_COLOR, linewidth = 2.2, alpha = 0.08) +
    geom_sf(data = borough, fill = NA, color = BOROUGH_COLOR, linewidth = 1.3, alpha = 0.15) +
    geom_sf(data = borough, fill = NA, color = BOROUGH_COLOR, linewidth = 0.7, alpha = 0.95) +

    # Layer 4: "Other" bus routes - thin flat blue lines, snapped to streets
    geom_sf(data = other_edges, aes(color = "other"), linewidth = 0.45, alpha = 0.75, lineend = "round") +

    # Layer 5: "Major" bus routes - thick glowing purple lines
    geom_sf(data = major_edges, color = MAJOR_COLOR, linewidth = 3.2, alpha = 0.10, lineend = "round") +
    geom_sf(data = major_edges, color = MAJOR_COLOR, linewidth = 1.8, alpha = 0.18, lineend = "round") +
    geom_sf(data = major_edges, aes(color = "major"), linewidth = 0.9, alpha = 0.95, lineend = "round") +

    # Layer 6: Bus stops - small glowing red dots
    geom_sf(data = stops_sf, color = STOP_COLOR, size = 3, alpha = 0.12) +
    geom_sf(data = stops_sf, color = STOP_COLOR, size = 1.1, alpha = 0.9) +

    # Layer 7: Major train / tube stations, labelled
    geom_sf(data = stations_sf, color = "#0a0e1a", fill = STATION_COLOR, shape = 21, size = 2.2, stroke = 0.8) +
    geom_text_repel(
      data = stations_sf,
      aes(label = name, geometry = geometry),
      stat = "sf_coordinates",
      size = 3,
      fontface = "bold",
      color = STATION_COLOR,
      bg.color = BG_COLOR,
      bg.r = 0.15,
      max.overlaps = 20,
      segment.size = 0.3,
      segment.color = SUBTEXT_COLOR
    ) +

    # Discrete legend for route tiers, styled like the mockup's legend chip
    scale_color_manual(
      name   = NULL,
      values = c(major = MAJOR_COLOR, other = OTHER_COLOR),
      labels = c(major = "Major bus routes", other = "Other bus routes"),
      breaks = c("major", "other")
    ) +
    guides(color = guide_legend(override.aes = list(linewidth = 2.5, alpha = 1))) +

    # Clean, dark map style
    coord_sf(expand = FALSE) +
    theme_void() +
    labs(
      title = paste("Internal Bus Network -", borough_name),
      subtitle = "Bus routes snapped to real streets, with major stations labelled"
    ) +
    theme(
      plot.title = element_text(size = 16, face = "bold", color = TEXT_COLOR, hjust = 0.5, margin = margin(b = 4)),
      plot.subtitle = element_text(size = 11, color = SUBTEXT_COLOR, hjust = 0.5, margin = margin(b = 10)),
      legend.position = "bottom",
      legend.text = element_text(color = TEXT_COLOR, size = 10),
      plot.background = element_rect(fill = BG_COLOR, color = NA),
      panel.background = element_rect(fill = BG_COLOR, color = NA),
      plot.margin = margin(t = 10, r = 10, b = 10, l = 10)
    )

  # Save high-resolution PNG
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  ggsave(output_png, plot = network_map, dpi = 300, width = 10, height = 10)
  cat(sprintf("Saved map to %s\n", output_png))

  invisible(output_png)
}


# --- Driver: only auto-runs when this file is source()-d on its own. A
#     multi-borough driver script should set RUN_ON_SOURCE <- FALSE before
#     source()-ing this file, then call render_borough_bus_network() itself
#     once per borough. ---
if (!exists("RUN_ON_SOURCE") || isTRUE(RUN_ON_SOURCE)) {
  render_borough_bus_network(DEFAULT_BOROUGH_NAME)
}