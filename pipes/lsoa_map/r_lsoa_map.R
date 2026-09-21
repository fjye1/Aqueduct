# ==============================================================================
# LSOA Map in R - one dark-themed PNG per LSOA, showing the bus routes that
# serve it (from the same GTFS/NaPTAN sources infrastructure_map uses),
# snapped to the real street network via dodgr, plus the open schools that
# fall inside it.
#
# Dependencies: install.packages(c("tidyverse", "sf", "viridis", "ggrepel", "dodgr"))
#
# Bus edges ARE snapped to streets via dodgr, same as infrastructure_map's
# r_bus_map_streets.R - but the routable graph is built and every edge
# routed ONCE PER BOROUGH (not once per LSOA), then reused for every LSOA in
# that borough. That's the same cost infrastructure_map already pays per
# borough today; doing it per-LSOA instead would multiply that cost by
# ~150x (LSOAs per borough) for no benefit, since the graph and the
# borough-wide edge set don't change between LSOAs in the same borough.
#
# Also unlike infrastructure_map's per-borough "internal edges only" rule
# (both stop ends must be inside the region), an edge here is kept if EITHER
# end falls inside the LSOA (buffered slightly) - most LSOAs are small
# enough that a strict internal-only rule would leave nearly every map
# empty, so this instead shows routes that actually serve the area.
#
# Usage:
#   Sourced directly -> renders a single test LSOA (back-compat/smoke test).
#   Sourced by a driver script that sets RUN_ON_SOURCE <- FALSE first ->
#   only defines render_lsoa_maps_for_borough(), which the driver calls once
#   per borough (each call loops every LSOA in that borough internally), e.g.:
#
#     RUN_ON_SOURCE <- FALSE
#     source("pipes/lsoa_map/r_lsoa_map.R")
#     render_lsoa_maps_for_borough("Barnet")
# ==============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(sf)
  library(viridis)
  library(ggrepel)
  library(dodgr)
})

# ============ DEFAULTS - override via render_lsoa_maps_for_borough() args ============
LSOA_SHP_DIR_DEFAULT   <- "data/A_raw/lsoa_map"
NAPTAN_CSV_DEFAULT     <- "data/C_silver/infrastructure_map/extraction_transport_stops.csv"
GTFS_DIR_DEFAULT       <- "data/A_raw/infrastructure_map/itm_london_gtfs"
SCHOOLS_CSV_DEFAULT    <- "data/C_silver/education/extraction_school_location_data.csv"
POSTCODES_CSV_DEFAULT  <- "data/C_silver/postcodes/extraction_postcode_centroids.csv"
OSM_CACHE_DIR_DEFAULT  <- "data/A_raw/infrastructure_map"
OUTPUT_DIR_DEFAULT     <- "pipes/lsoa_map/images"
DEFAULT_BOROUGH_NAME   <- "City of London"

# Context buffer around each LSOA polygon (metres) - wide enough to catch a
# bus route or school just across the LSOA line, without pulling in the
# whole neighbourhood.
BUFFER_M_DEFAULT <- 200

# Edges at/above this quantile of trip_count (computed once per borough) are
# styled as "major" routes, everything else as "other".
MAJOR_ROUTE_QUANTILE_DEFAULT <- 0.75

# Only label schools individually when there aren't too many in frame -
# ggrepel gets unreadable past this many labels in a small image.
MAX_SCHOOL_LABELS <- 8

# Street label count scales with the LSOA's own area rather than being
# fixed - a tiny LSOA and a sprawling one both need "enough labels to
# orient yourself", which isn't the same number of streets. Based on the
# actual area distribution (median ~0.2 km^2, 95th pct ~0.83 km^2):
# below STREET_LABEL_AREA_BASE_KM2 you get the floor (10); above it, labels
# scale up at STREET_LABEL_SLOPE per km^2, capped at STREET_LABEL_MAX so the
# rare very large (mostly park/industrial) LSOAs don't get flooded with labels.
STREET_LABEL_MIN <- 10
STREET_LABEL_MAX <- 20
STREET_LABEL_AREA_BASE_KM2 <- 0.1
STREET_LABEL_SLOPE <- 15

# Postcode district shading/outlines are approximate (Voronoi-dissolved from
# unit centroids, grouped by each postcode's own ONS-assigned LSOA - see
# .load_borough_data()) and are ALWAYS drawn, however many districts an LSOA
# touches (typically 1-2, occasionally a dozen or more in dense commercial
# areas) - every map should have the same postcode layer present, never an
# all-or-nothing drop. What's capped is the TEXT LABEL, same pattern as
# MAX_SCHOOL_LABELS: past this many districts, only the largest (by area)
# get a code label, so the layer never goes fully unlabelled or fully absent.
MAX_POSTCODE_DISTRICT_LABELS <- 8

# --- Dark dashboard-style palette (matches infrastructure_map's style) ---
BG_COLOR       <- "#0a0e1a"
STREET_COLOR   <- "#3a4354"
STREET_LABEL_COLOR <- "#9aa5b6"
LSOA_COLOR     <- "#7c6a99"
DISTRICT_COLOR   <- "#8b96ab"
DISTRICT_LABEL_COLOR <- "#a9b3c4"
# Cycled across districts within one LSOA (by draw order) to give each a
# subtly different shaded fill, so neighbouring districts read as distinct
# areas rather than one uniform tint over the whole frame.
DISTRICT_SHADE_PALETTE <- c("#2d3348", "#2a3d42", "#3a3348", "#26384a")
MAJOR_COLOR    <- "#b446f0"
OTHER_COLOR    <- "#2f8fe0"
STOP_COLOR     <- "#ff3b3b"
STATION_COLOR  <- "#ffffff"
SCHOOL_COLOR   <- "#22c55e"
TARGET_COLOR   <- "#fbbf24"
TEXT_COLOR     <- "#e5e7eb"
SUBTEXT_COLOR  <- "#9ca3af"

# Shared legend, rendered identically on every LSOA regardless of whether
# that particular LSOA happens to have (e.g.) a station in frame - every
# level below is always drawn as its own (possibly empty) layer in
# .render_one_lsoa() so the legend never changes shape *for these entries*.
# "Searched location" is NOT included here - it's only added (in
# .render_one_lsoa()) when a target_lon/target_lat is actually supplied for
# that render, since otherwise it's a legend key for something that never
# appears on any of these maps (today's bulk pre-render has no per-property
# input - see render_lsoa_maps_for_borough()'s `targets` argument).
BASE_LEGEND_LEVELS <- c("LSOA boundary", "Postcode district", "Major bus route", "Other bus route", "Bus stop", "Station", "School")
BASE_LEGEND_COLORS <- c(
  "LSOA boundary"     = LSOA_COLOR,
  "Postcode district" = DISTRICT_COLOR,
  "Major bus route"   = MAJOR_COLOR,
  "Other bus route"   = OTHER_COLOR,
  "Bus stop"          = STOP_COLOR,
  "Station"           = STATION_COLOR,
  "School"            = SCHOOL_COLOR
)
# Matched positionally to BASE_LEGEND_LEVELS - controls what glyph each
# legend key actually shows (line vs point), independent of any one layer's
# own drawing style.
BASE_LEGEND_OVERRIDE_AES <- list(
  linetype  = c(2,   3,   1,   1,   0,   0,   0),
  linewidth = c(0.8, 0.9, 1.0, 0.8, 1,   1,   1),
  shape     = c(NA,  NA,  NA,  NA,  19,  15,  17),
  size      = c(1,   1,   1,   1,   2.5, 2.5, 2.8)
)

TARGET_LEGEND_LEVEL <- "Searched location"
TARGET_LEGEND_COLOR <- c("Searched location" = TARGET_COLOR)
TARGET_LEGEND_OVERRIDE_AES <- list(linetype = 0, linewidth = 1, shape = 18, size = 3.2)

ROUTE_PROFILE_DEFAULT <- "motorcar"
# ==================================================


# Turns "Kingston upon Thames" -> "kingston_upon_thames". Mirrors
# infrastructure_map's r_bus_map_streets.R::slugify_borough().
slugify_borough <- function(borough_name) {
  slug <- tolower(borough_name)
  slug <- gsub("[^a-z0-9]+", "_", slug)
  gsub("^_+|_+$", "", slug)
}


# --- Loads every table shared across all LSOAs in one borough: the borough's
#     LSOA polygons, its NaPTAN stops, the GTFS-derived internal bus edges,
#     the cached OSM street/station extracts, and its open schools. Doing
#     this once per borough (instead of once per LSOA) is what keeps ~4,800
#     LSOA renders tractable - see file header. ---
.load_borough_data <- function(borough_name, lsoa_shp_dir, naptan_csv, gtfs_dir,
                                schools_csv, postcodes_csv, osm_cache_dir, major_route_quantile) {

  slug <- slugify_borough(borough_name)

  # --- LSOA polygons for this borough ---
  shp_path <- file.path(lsoa_shp_dir, paste0(borough_name, ".shp"))
  lsoas <- st_read(shp_path, quiet = TRUE) %>% st_transform(crs = 4326)
  borough_code <- lsoas$lad22cd[1]

  # --- NaPTAN stops for this borough ---
  naptan_raw <- read_csv(naptan_csv, show_col_types = FALSE)
  rename_lookup <- c(ATCOCode = "atcoCode", Longitude = "lon", Latitude = "lat")
  for (canonical in names(rename_lookup)) {
    legacy <- rename_lookup[[canonical]]
    if (!canonical %in% names(naptan_raw) && legacy %in% names(naptan_raw)) {
      naptan_raw <- naptan_raw %>% rename(!!canonical := !!legacy)
    }
  }
  naptan <- naptan_raw %>% filter(BOROUGH == borough_name)

  stops_sf <- naptan %>%
    filter(!is.na(Longitude), !is.na(Latitude)) %>%
    st_as_sf(coords = c("Longitude", "Latitude"), crs = 4326, remove = FALSE)

  # --- Cached OSM street/station extracts (from infrastructure_map's
  #     download step) - used both as the routing graph below and as the
  #     basemap in .render_one_lsoa() ---
  streets_rds  <- file.path(osm_cache_dir, sprintf("osm_streets_%s.rds", slug))
  stations_rds <- file.path(osm_cache_dir, sprintf("osm_stations_%s.rds", slug))
  streets_sf  <- if (file.exists(streets_rds)) readRDS(streets_rds) else NULL
  stations_sf <- if (file.exists(stations_rds)) readRDS(stations_rds) else NULL

  # --- GTFS-derived bus edges touching this borough, routed along real
  #     streets via dodgr (see file header) ---
  borough_stop_ids <- as.character(naptan$ATCOCode)
  edges_sf <- st_sf(from_stop = character(), to_stop = character(), trip_count = integer(),
                     route_tier = character(), geometry = st_sfc(crs = 4326))

  if (length(borough_stop_ids) > 0) {
    stop_times <- read_csv(file.path(gtfs_dir, "stop_times.txt"), col_types = cols(stop_id = "c", trip_id = "c"))
    trips      <- read_csv(file.path(gtfs_dir, "trips.txt"), col_types = cols(trip_id = "c", route_id = "c"))
    gtfs_stops <- read_csv(file.path(gtfs_dir, "stops.txt"), col_types = cols(stop_id = "c"))

    trips_touching_borough <- stop_times %>%
      filter(stop_id %in% borough_stop_ids) %>%
      pull(trip_id) %>%
      unique()

    st_seq <- stop_times %>%
      filter(trip_id %in% trips_touching_borough) %>%
      arrange(trip_id, stop_sequence)

    edges <- st_seq %>%
      group_by(trip_id) %>%
      mutate(to_stop = lead(stop_id)) %>%
      rename(from_stop = stop_id) %>%
      filter(!is.na(to_stop)) %>%
      ungroup() %>%
      filter(from_stop %in% borough_stop_ids & to_stop %in% borough_stop_ids)

    if (nrow(edges) > 0) {
      edge_counts <- edges %>%
        group_by(from_stop, to_stop) %>%
        summarise(trip_count = n_distinct(trip_id), .groups = "drop")

      coords <- gtfs_stops %>% select(stop_id, stop_lat, stop_lon)

      edge_counts <- edge_counts %>%
        left_join(coords, by = c("from_stop" = "stop_id")) %>%
        rename(from_lat = stop_lat, from_lon = stop_lon) %>%
        left_join(coords, by = c("to_stop" = "stop_id")) %>%
        rename(to_lat = stop_lat, to_lon = stop_lon) %>%
        filter(!is.na(from_lon) & !is.na(to_lon) & !is.na(from_lat) & !is.na(to_lat))

      if (nrow(edge_counts) > 0) {
        major_cutoff <- quantile(edge_counts$trip_count, major_route_quantile)

        if (!is.null(streets_sf) && nrow(streets_sf) > 0) {
          cat(sprintf("  Building routable street graph for %s...\n", borough_name))
          graph <- weight_streetnet(streets_sf, wt_profile = ROUTE_PROFILE_DEFAULT)
          verts <- dodgr_vertices(graph)

          route_edge <- function(from_lon, from_lat, to_lon, to_lat) {
            from_pt <- matrix(c(from_lon, from_lat), ncol = 2, dimnames = list(NULL, c("x", "y")))
            to_pt   <- matrix(c(to_lon, to_lat), ncol = 2, dimnames = list(NULL, c("x", "y")))

            path <- tryCatch(
              dodgr_paths(graph, from = from_pt, to = to_pt, vertices = TRUE),
              error = function(e) NULL
            )
            vertex_ids <- tryCatch(path[[1]][[1]], error = function(e) NULL)

            if (is.null(vertex_ids) || length(vertex_ids) < 2) {
              return(st_linestring(rbind(c(from_lon, from_lat), c(to_lon, to_lat))))
            }
            pts <- verts[match(vertex_ids, verts$id), c("x", "y")]
            st_linestring(as.matrix(pts))
          }

          cat(sprintf("  Routing %d unique bus edges along streets...\n", nrow(edge_counts)))
          lines_list <- vector("list", nrow(edge_counts))
          for (i in seq_len(nrow(edge_counts))) {
            lines_list[[i]] <- route_edge(
              edge_counts$from_lon[i], edge_counts$from_lat[i],
              edge_counts$to_lon[i], edge_counts$to_lat[i]
            )
          }
        } else {
          cat(sprintf("  [WARN] No cached street network for %s - falling back to straight-line edges.\n", borough_name))
          lines_list <- map(seq_len(nrow(edge_counts)), function(i) {
            st_linestring(rbind(
              c(edge_counts$from_lon[i], edge_counts$from_lat[i]),
              c(edge_counts$to_lon[i], edge_counts$to_lat[i])
            ))
          })
        }

        edges_sf <- edge_counts %>%
          mutate(
            geometry   = st_sfc(lines_list, crs = 4326),
            route_tier = if_else(trip_count >= major_cutoff, "major", "other")
          ) %>%
          select(from_stop, to_stop, trip_count, route_tier, geometry) %>%
          st_as_sf()
      }
    }
  }

  # --- Open schools in this borough ---
  schools_raw <- read_csv(schools_csv, show_col_types = FALSE)
  schools_borough <- schools_raw %>%
    filter(borough_name == !!borough_name, status == "Open",
           !is.na(easting), !is.na(northing))

  schools_sf <- st_sf(school_name = character(), geometry = st_sfc(crs = 4326))
  if (nrow(schools_borough) > 0) {
    schools_sf <- schools_borough %>%
      st_as_sf(coords = c("easting", "northing"), crs = 27700) %>%
      st_transform(crs = 4326) %>%
      select(school_name, geometry)
  }

  # --- Postcode district shapes for this borough. There's no official
  #     postcode boundary product (postcodes are sets of delivery points,
  #     not areas), so this approximates one: take every live unit-postcode
  #     centroid in the borough, Voronoi-tessellate them (each cell = the
  #     space closer to that point than to any other), then dissolve cells
  #     that share BOTH the same postcode DISTRICT (the outward code, e.g.
  #     "EC4Y" from "EC4Y 0AA" - one level coarser than sector, e.g. "EC4Y 0")
  #     AND the same ONS-assigned LSOA into one polygon. District rather
  #     than sector because sector-level fragments (an earlier version of
  #     this) turned out too numerous/busy in dense areas even after
  #     confining them to their own LSOA - grouping one level coarser
  #     roughly halves the median fragment count with no other change.
  #
  #     The LSOA condition matters on its own too: a unit postcode gets a
  #     clean 1:1 "best fit" LSOA assignment from ONS, but a whole district
  #     (or sector) aggregates many units and routinely spans several LSOAs
  #     (LSOAs are sized for ~1,500 residents; a district covers far more).
  #     Dissolving by district alone would produce one sprawling shape per
  #     district that cuts across LSOA lines with no regard for them.
  #     Dissolving by (LSOA, district) instead means a district that spans
  #     3 LSOAs becomes 3 separate fragments - each built only from
  #     postcodes ONS actually assigns to that LSOA, so each fragment is
  #     naturally contained within it. The trade-off: what's shown is "this
  #     LSOA's share of district X", not district X's true full extent.
  #
  #     Built once per borough, like everything else here, and split out
  #     per-LSOA (by the lsoa21cd column, not spatial clipping) in
  #     .render_one_lsoa(). ---
  postcode_districts_sf <- st_sf(lsoa21cd = character(), postcode_district = character(), geometry = st_sfc(crs = 4326))
  postcodes_borough <- read_csv(postcodes_csv, show_col_types = FALSE) %>%
    filter(lad25cd == borough_code, !is.na(easting), !is.na(northing))

  if (nrow(postcodes_borough) > 0) {
    pc_pts <- postcodes_borough %>%
      mutate(postcode_district = sub(" .*", "", postcode_sector)) %>%
      st_as_sf(coords = c("easting", "northing"), crs = 27700, remove = FALSE)

    voronoi_cells <- st_voronoi(st_union(pc_pts)) %>% st_collection_extract("POLYGON")
    voronoi_sf <- st_sf(geometry = voronoi_cells)

    postcode_districts_sf <- st_join(voronoi_sf, pc_pts[c("postcode_district", "lsoa21cd")], join = st_intersects, left = FALSE) %>%
      group_by(lsoa21cd, postcode_district) %>%
      summarise(geometry = st_union(geometry), .groups = "drop") %>%
      st_as_sf() %>%
      st_transform(crs = 4326)
  }

  list(
    lsoas                 = lsoas,
    stops_sf              = stops_sf,
    edges_sf              = edges_sf,
    streets_sf            = streets_sf,
    stations_sf           = stations_sf,
    schools_sf            = schools_sf,
    postcode_districts_sf = postcode_districts_sf
  )
}


# --- Renders a single LSOA's map from already-loaded borough data. ---
.render_one_lsoa <- function(lsoa_row, borough_data, output_dir, buffer_m,
                              target_lon = NULL, target_lat = NULL) {
  lsoa_code <- lsoa_row$lsoa21cd[1]
  lsoa_name <- lsoa_row$lsoa21nm[1]
  borough_name <- lsoa_row$lad22nm[1]

  target_png <- file.path(output_dir, sprintf("%s.png", lsoa_code))
  has_target <- !is.null(target_lon) && !is.null(target_lat)

  area <- lsoa_row %>%
    st_transform(crs = 27700) %>%
    st_buffer(buffer_m) %>%
    st_transform(crs = 4326)
  area_geom <- st_geometry(area)
  bbox <- st_bbox(area)

  lsoa_area_km2 <- as.numeric(st_area(st_transform(lsoa_row, 27700))) / 1e6
  street_label_cap <- min(STREET_LABEL_MAX, max(STREET_LABEL_MIN,
    round(STREET_LABEL_MIN + (lsoa_area_km2 - STREET_LABEL_AREA_BASE_KM2) * STREET_LABEL_SLOPE)))

  in_area <- function(sf_obj) {
    if (is.null(sf_obj) || nrow(sf_obj) == 0) return(sf_obj)
    suppressWarnings(sf_obj[st_intersects(sf_obj, area_geom, sparse = FALSE)[, 1], ])
  }

  stops_in_area <- in_area(borough_data$stops_sf)
  active_ids <- if (nrow(stops_in_area) > 0) unique(as.character(stops_in_area$ATCOCode)) else character()
  n_stops_real <- nrow(stops_in_area)

  edges_in_area <- borough_data$edges_sf
  if (nrow(edges_in_area) > 0) {
    edges_in_area <- edges_in_area %>%
      filter(from_stop %in% active_ids | to_stop %in% active_ids)
  }

  streets_in_area  <- in_area(borough_data$streets_sf)
  stations_in_area <- in_area(borough_data$stations_sf)
  schools_in_area  <- in_area(borough_data$schools_sf)
  n_schools_real <- if (is.null(schools_in_area)) 0 else nrow(schools_in_area)

  # Selected by the postcode's own ONS-assigned LSOA (see .load_borough_data()'s
  # comment), not spatial clipping - every fragment here is guaranteed built
  # only from postcodes officially belonging to this LSOA. Always kept and
  # drawn in full, however many there are; only the text label is capped
  # further down (MAX_POSTCODE_DISTRICT_LABELS), so the layer is never
  # dropped outright.
  postcode_districts_in_area <- borough_data$postcode_districts_sf %>% filter(lsoa21cd == !!lsoa_code)
  if (nrow(postcode_districts_in_area) > MAX_POSTCODE_DISTRICT_LABELS) {
    cat(sprintf("  [NOTE] %s: %d postcode districts (> %d labelled) - shading/outlines shown for all, only the largest are labelled.\n",
                lsoa_code, nrow(postcode_districts_in_area), MAX_POSTCODE_DISTRICT_LABELS))
  }

  major_edges <- edges_in_area %>% filter(route_tier == "major")
  other_edges <- edges_in_area %>% filter(route_tier == "other")

  label_schools <- nrow(schools_in_area) > 0 && nrow(schools_in_area) <= MAX_SCHOOL_LABELS

  # --- Pick a handful of named streets to label, favouring the longest
  #     (usually the most "primary") segments in frame so the map reads as
  #     an actual place rather than an abstract polygon. ---
  street_labels <- st_sf(name = character(), geometry = st_sfc(crs = 4326))
  if (!is.null(streets_in_area) && nrow(streets_in_area) > 0 && "name" %in% names(streets_in_area)) {
    named_streets <- streets_in_area %>% filter(!is.na(name), name != "")
    if (nrow(named_streets) > 0) {
      street_labels <- named_streets %>%
        mutate(.len = st_length(geometry)) %>%
        group_by(name) %>%
        slice_max(order_by = .len, n = 1, with_ties = FALSE) %>%
        ungroup() %>%
        arrange(desc(.len)) %>%
        slice_head(n = street_label_cap) %>%
        select(name, geometry)
    }
  }

  # --- The searched postcode/property location, only present (and only
  #     added to the legend) when this specific render actually has one -
  #     see render_lsoa_maps_for_borough()'s `targets` argument and
  #     BASE_LEGEND_LEVELS's comment above for why. ---
  if (has_target) {
    target_sf <- st_sf(geometry = st_sfc(st_point(c(target_lon, target_lat)), crs = 4326))
  }

  # Placeholder empty sf frames for any layer with nothing in this LSOA, so
  # every geom_sf() call below always runs (a 0-row layer draws nothing but
  # still registers its legend level) - that's what keeps the legend
  # identical across every LSOA. See BASE_LEGEND_LEVELS/BASE_LEGEND_COLORS.
  empty_lines  <- st_sf(geometry = st_sfc(crs = 4326))
  if (nrow(other_edges) == 0) other_edges <- empty_lines
  if (nrow(major_edges) == 0) major_edges <- empty_lines
  # NOTE: point-type placeholders use an off-frame dummy point (clipped out
  # by coord_sf() below), not a genuinely empty (0-row) layer - an empty sf
  # column has no determinable point/line/polygon type, which makes GeomSf's
  # legend key fall back to a nonsense glyph (a literal "a") instead of the
  # shape set in BASE_LEGEND_OVERRIDE_AES. Line-type layers (edges, sectors)
  # are fine empty since their geometry type is still known from the source data.
  off_frame_point <- st_sfc(st_point(c(0, 0)), crs = 4326)
  if (is.null(stops_in_area) || nrow(stops_in_area) == 0) stops_in_area <- st_sf(ATCOCode = NA_character_, geometry = off_frame_point)
  if (is.null(stations_in_area) || nrow(stations_in_area) == 0) stations_in_area <- st_sf(name = NA_character_, geometry = off_frame_point)
  if (is.null(schools_in_area) || nrow(schools_in_area) == 0) schools_in_area <- st_sf(school_name = NA_character_, geometry = off_frame_point)
  if (is.null(postcode_districts_in_area) || nrow(postcode_districts_in_area) == 0) postcode_districts_in_area <- st_sf(lsoa21cd = character(), postcode_district = character(), geometry = st_sfc(crs = 4326))

  # Cycle a small palette across districts (by draw order) so adjacent ones
  # shade differently and read as distinct areas, not one uniform tint.
  postcode_districts_in_area$shade_color <- if (nrow(postcode_districts_in_area) > 0) {
    DISTRICT_SHADE_PALETTE[((seq_len(nrow(postcode_districts_in_area)) - 1) %% length(DISTRICT_SHADE_PALETTE)) + 1]
  } else {
    character(0)
  }

  # --- Every label source (street/station/school names) is combined into
  #     ONE geom_text_repel() layer below, added last so it draws on top of
  #     the bus routes, and so ggrepel's overlap-avoidance runs jointly
  #     across all of them - repelling labels only within their own
  #     separate layers (the old approach) still lets e.g. a station name
  #     collide with a school name from a different layer. ---
  label_parts <- list()
  if (nrow(street_labels) > 0) {
    label_parts[["street"]] <- street_labels %>%
      transmute(label = name, label_color = STREET_LABEL_COLOR, label_face = "italic", label_size = 2.6, geometry = geometry)
  }
  if (nrow(stations_in_area) > 0 && "name" %in% names(stations_in_area)) {
    named_stations <- stations_in_area %>% filter(!is.na(name))
    if (nrow(named_stations) > 0) {
      label_parts[["station"]] <- named_stations %>%
        transmute(label = name, label_color = STATION_COLOR, label_face = "bold", label_size = 2.8, geometry = geometry)
    }
  }
  if (label_schools) {
    label_parts[["school"]] <- schools_in_area %>%
      transmute(label = school_name, label_color = SCHOOL_COLOR, label_face = "plain", label_size = 2.6, geometry = geometry)
  }
  if (nrow(postcode_districts_in_area) > 0) {
    label_parts[["district"]] <- postcode_districts_in_area %>%
      mutate(.area = st_area(geometry)) %>%
      arrange(desc(.area)) %>%
      slice_head(n = MAX_POSTCODE_DISTRICT_LABELS) %>%
      transmute(label = postcode_district, label_color = DISTRICT_LABEL_COLOR, label_face = "bold", label_size = 2.6, geometry = geometry)
  }

  label_points <- st_sf(label = character(), label_color = character(), label_face = character(),
                         label_size = numeric(), geometry = st_sfc(crs = 4326))
  if (length(label_parts) > 0) {
    label_points <- bind_rows(label_parts) %>% st_as_sf()
  }

  p <- ggplot() +
    geom_sf(data = lsoa_row, fill = "#0d1220", color = NA)

  if (!is.null(streets_in_area) && nrow(streets_in_area) > 0) {
    p <- p + geom_sf(data = streets_in_area, color = STREET_COLOR, linewidth = 0.3, alpha = 0.85)
  }

  # --- Every layer below maps `color` to one of BASE_LEGEND_LEVELS (plus
  #     "Searched location" when has_target) so a single shared scale/legend
  #     covers every symbol type (see the override.aes built further down
  #     for what glyph each one renders as). The LSOA
  #     boundary is intentionally understated (thin, dashed, muted) - most
  #     users don't know what an LSOA is, so it's context, not a headline
  #     feature. Bus routes are toned down slightly from their first pass
  #     for the same reason: readability of the whole map over any one layer. ---
  p <- p +
    geom_sf(data = lsoa_row, aes(color = "LSOA boundary"), fill = NA, linewidth = 0.7, linetype = "dashed", alpha = 0.65) +
    geom_sf(data = postcode_districts_in_area, aes(fill = I(shade_color)), color = NA, alpha = 0.55) +
    geom_sf(data = postcode_districts_in_area, aes(color = "Postcode district"), fill = NA, linewidth = 0.9, linetype = "dotted", alpha = 0.85) +
    geom_sf(data = other_edges, aes(color = "Other bus route"), linewidth = 0.4, alpha = 0.6, lineend = "round") +
    geom_sf(data = major_edges, aes(color = "Major bus route"), linewidth = 2.2, alpha = 0.07, lineend = "round", show.legend = FALSE) +
    geom_sf(data = major_edges, aes(color = "Major bus route"), linewidth = 0.85, alpha = 0.85, lineend = "round") +
    geom_sf(data = stops_in_area, aes(color = "Bus stop"), size = 3, alpha = 0.15, show.legend = FALSE) +
    geom_sf(data = stops_in_area, aes(color = "Bus stop"), size = 1.1, alpha = 0.9) +
    geom_sf(data = stations_in_area, aes(color = "Station"), shape = 15, size = 2.2) +
    geom_sf(data = schools_in_area, aes(color = "School"), shape = 17, size = 2.4)

  if (has_target) {
    p <- p +
      geom_sf(data = target_sf, aes(color = "Searched location"), shape = 18, size = 3.2, show.legend = FALSE) +
      geom_sf(data = target_sf, aes(color = "Searched location"), shape = 5, size = 5.5, stroke = 1)
  }

  if (nrow(label_points) > 0) {
    p <- p + geom_text_repel(
      data = label_points,
      aes(label = label, geometry = geometry, color = I(label_color), fontface = I(label_face), size = I(label_size)),
      stat = "sf_coordinates", bg.color = BG_COLOR, bg.r = 0.12,
      max.overlaps = 60, segment.size = 0.3, segment.color = SUBTEXT_COLOR
    )
  }

  # Legend only gains the "Searched location" entry when this render
  # actually has one - see BASE_LEGEND_LEVELS's comment above.
  if (has_target) {
    legend_levels <- c(TARGET_LEGEND_LEVEL, BASE_LEGEND_LEVELS)
    legend_colors <- c(TARGET_LEGEND_COLOR, BASE_LEGEND_COLORS)
    legend_override <- list(
      linetype  = c(TARGET_LEGEND_OVERRIDE_AES$linetype, BASE_LEGEND_OVERRIDE_AES$linetype),
      linewidth = c(TARGET_LEGEND_OVERRIDE_AES$linewidth, BASE_LEGEND_OVERRIDE_AES$linewidth),
      shape     = c(TARGET_LEGEND_OVERRIDE_AES$shape, BASE_LEGEND_OVERRIDE_AES$shape),
      size      = c(TARGET_LEGEND_OVERRIDE_AES$size, BASE_LEGEND_OVERRIDE_AES$size)
    )
  } else {
    legend_levels <- BASE_LEGEND_LEVELS
    legend_colors <- BASE_LEGEND_COLORS
    legend_override <- BASE_LEGEND_OVERRIDE_AES
  }

  p <- p +
    scale_color_manual(
      name = "Legend",
      values = legend_colors,
      breaks = legend_levels,
      limits = legend_levels,
      drop = FALSE
    ) +
    guides(color = guide_legend(override.aes = legend_override)) +
    coord_sf(xlim = c(bbox["xmin"], bbox["xmax"]), ylim = c(bbox["ymin"], bbox["ymax"]), expand = FALSE) +
    theme_void() +
    labs(
      title = borough_name,
      subtitle = "Bus routes and schools nearby",
      caption = sprintf("LSOA %s (%s)", lsoa_code, lsoa_name)
    ) +
    theme(
      plot.title = element_text(size = 14, face = "bold", color = TEXT_COLOR, hjust = 0.5, margin = margin(b = 2)),
      plot.subtitle = element_text(size = 9.5, color = SUBTEXT_COLOR, hjust = 0.5, margin = margin(b = 8)),
      plot.caption = element_text(size = 7, color = SUBTEXT_COLOR, hjust = 0.5, margin = margin(t = 8)),
      legend.position = "right",
      legend.title = element_text(color = TEXT_COLOR, size = 9, face = "bold"),
      legend.text = element_text(color = TEXT_COLOR, size = 8),
      plot.background = element_rect(fill = BG_COLOR, color = NA),
      panel.background = element_rect(fill = BG_COLOR, color = NA),
      plot.margin = margin(t = 8, r = 8, b = 8, l = 8)
    )

  ggsave(target_png, plot = p, dpi = 200, width = 7.5, height = 6)

  list(
    lsoa_code = lsoa_code, png = target_png,
    n_edges = nrow(edges_in_area), n_stops = n_stops_real, n_schools = n_schools_real
  )
}


# --- Driver: renders every LSOA in one borough (or just `lsoa_limit` of
#     them, for a quick smoke test), skipping any PNG that already exists so
#     a partial run can resume without re-paying the borough-wide GTFS/OSM
#     load cost.
#
#     `targets`: named list of lsoa_code -> c(lon, lat) for the searched
#     postcode/property marker. This is a per-property concept, not a
#     per-borough one - there's no real "the" property for a whole batch
#     run of ~150 LSOAs, so it's opt-in and only draws a marker for LSOAs
#     that have an entry here. Left NULL, no LSOA gets a marker (today's
#     bulk pre-render has no property/postcode input to draw one from -
#     see the note where this is called from D_gold.py). ---
render_lsoa_maps_for_borough <- function(borough_name,
                                          lsoa_shp_dir  = LSOA_SHP_DIR_DEFAULT,
                                          naptan_csv    = NAPTAN_CSV_DEFAULT,
                                          gtfs_dir      = GTFS_DIR_DEFAULT,
                                          schools_csv   = SCHOOLS_CSV_DEFAULT,
                                          postcodes_csv = POSTCODES_CSV_DEFAULT,
                                          osm_cache_dir = OSM_CACHE_DIR_DEFAULT,
                                          output_dir    = OUTPUT_DIR_DEFAULT,
                                          buffer_m      = BUFFER_M_DEFAULT,
                                          major_route_quantile = MAJOR_ROUTE_QUANTILE_DEFAULT,
                                          lsoa_limit    = NULL,
                                          lsoa_codes_filter = NULL,
                                          targets       = NULL) {

  slug <- slugify_borough(borough_name)
  borough_output_dir <- file.path(output_dir, slug)
  dir.create(borough_output_dir, recursive = TRUE, showWarnings = FALSE)

  cat(sprintf("\n=== Loading borough data: %s ===\n", borough_name))
  borough_data <- .load_borough_data(
    borough_name, lsoa_shp_dir, naptan_csv, gtfs_dir, schools_csv, postcodes_csv, osm_cache_dir, major_route_quantile
  )

  lsoa_codes <- borough_data$lsoas$lsoa21cd
  if (!is.null(lsoa_codes_filter)) lsoa_codes <- intersect(lsoa_codes, lsoa_codes_filter)
  if (!is.null(lsoa_limit)) lsoa_codes <- head(lsoa_codes, lsoa_limit)

  cat(sprintf("Rendering %d LSOA(s) in %s...\n", length(lsoa_codes), borough_name))

  rendered <- 0
  skipped  <- 0
  failed   <- character()

  for (code in lsoa_codes) {
    target_png <- file.path(borough_output_dir, sprintf("%s.png", code))
    if (file.exists(target_png)) {
      skipped <- skipped + 1
      next
    }

    lsoa_row <- borough_data$lsoas %>% filter(lsoa21cd == code)

    target_xy <- if (!is.null(targets)) targets[[code]] else NULL

    result <- tryCatch(
      .render_one_lsoa(lsoa_row, borough_data, borough_output_dir, buffer_m,
                        target_lon = target_xy[1], target_lat = target_xy[2]),
      error = function(e) {
        cat(sprintf("  [ERROR] %s: %s\n", code, conditionMessage(e)))
        NULL
      }
    )

    if (is.null(result)) {
      failed <- c(failed, code)
    } else {
      rendered <- rendered + 1
      cat(sprintf("  [%d/%d] %s -> %s (edges=%d, stops=%d, schools=%d)\n",
                  rendered + skipped, length(lsoa_codes), code, basename(result$png),
                  result$n_edges, result$n_stops, result$n_schools))
    }
  }

  cat(sprintf("\n%s done: %d rendered, %d skipped (already existed), %d failed.\n",
              borough_name, rendered, skipped, length(failed)))
  if (length(failed) > 0) cat(sprintf("Failed LSOAs: %s\n", paste(failed, collapse = ", ")))

  invisible(list(rendered = rendered, skipped = skipped, failed = failed))
}


# --- Only auto-runs when this file is source()-d on its own - a driver
#     script should set RUN_ON_SOURCE <- FALSE before source()-ing this
#     file, then call render_lsoa_maps_for_borough() itself. ---
if (!exists("RUN_ON_SOURCE") || isTRUE(RUN_ON_SOURCE)) {
  render_lsoa_maps_for_borough(DEFAULT_BOROUGH_NAME, lsoa_limit = 1)
}
