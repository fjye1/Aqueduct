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

# Only label schools/streets individually when there aren't too many in
# frame - ggrepel gets unreadable past this many labels in a small image.
MAX_SCHOOL_LABELS <- 8
MAX_STREET_LABELS <- 6

# --- Dark dashboard-style palette (matches infrastructure_map's style) ---
BG_COLOR       <- "#0a0e1a"
STREET_COLOR   <- "#3a4354"
STREET_LABEL_COLOR <- "#9aa5b6"
LSOA_COLOR     <- "#7c6a99"
MAJOR_COLOR    <- "#b446f0"
OTHER_COLOR    <- "#2f8fe0"
STOP_COLOR     <- "#ff3b3b"
STATION_COLOR  <- "#ffffff"
SCHOOL_COLOR   <- "#22c55e"
TARGET_COLOR   <- "#fbbf24"
TEXT_COLOR     <- "#e5e7eb"
SUBTEXT_COLOR  <- "#9ca3af"

# Single shared legend, rendered identically on every LSOA regardless of
# whether that particular LSOA happens to have (e.g.) a station in frame -
# every level below is always drawn as its own (possibly empty) layer in
# .render_one_lsoa() so the legend never changes shape.
LEGEND_LEVELS <- c("Searched location", "LSOA boundary", "Major bus route", "Other bus route", "Bus stop", "Station", "School")
LEGEND_COLORS <- c(
  "Searched location" = TARGET_COLOR,
  "LSOA boundary"     = LSOA_COLOR,
  "Major bus route"   = MAJOR_COLOR,
  "Other bus route"   = OTHER_COLOR,
  "Bus stop"          = STOP_COLOR,
  "Station"           = STATION_COLOR,
  "School"            = SCHOOL_COLOR
)
# Matched positionally to LEGEND_LEVELS - controls what glyph each legend
# key actually shows (line vs point), independent of any one layer's style.
LEGEND_OVERRIDE_AES <- list(
  linetype  = c(0,   2,   1,   1,   0,   0,   0),
  linewidth = c(1,   0.8, 1.0, 0.8, 1,   1,   1),
  shape     = c(18,  NA,  NA,  NA,  19,  15,  17),
  size      = c(3.2, 1,   1,   1,   2.5, 2.5, 2.8)
)

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
                                schools_csv, osm_cache_dir, major_route_quantile) {

  slug <- slugify_borough(borough_name)

  # --- LSOA polygons for this borough ---
  shp_path <- file.path(lsoa_shp_dir, paste0(borough_name, ".shp"))
  lsoas <- st_read(shp_path, quiet = TRUE) %>% st_transform(crs = 4326)

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

  list(
    lsoas       = lsoas,
    stops_sf    = stops_sf,
    edges_sf    = edges_sf,
    streets_sf  = streets_sf,
    stations_sf = stations_sf,
    schools_sf  = schools_sf
  )
}


# --- Renders a single LSOA's map from already-loaded borough data. ---
.render_one_lsoa <- function(lsoa_row, borough_data, output_dir, buffer_m,
                              target_lon = NULL, target_lat = NULL) {
  lsoa_code <- lsoa_row$lsoa21cd[1]
  lsoa_name <- lsoa_row$lsoa21nm[1]
  borough_name <- lsoa_row$lad22nm[1]

  target_png <- file.path(output_dir, sprintf("%s.png", lsoa_code))

  area <- lsoa_row %>%
    st_transform(crs = 27700) %>%
    st_buffer(buffer_m) %>%
    st_transform(crs = 4326)
  area_geom <- st_geometry(area)
  bbox <- st_bbox(area)

  in_area <- function(sf_obj) {
    if (is.null(sf_obj) || nrow(sf_obj) == 0) return(sf_obj)
    suppressWarnings(sf_obj[st_intersects(sf_obj, area_geom, sparse = FALSE)[, 1], ])
  }

  stops_in_area <- in_area(borough_data$stops_sf)
  active_ids <- if (nrow(stops_in_area) > 0) unique(as.character(stops_in_area$ATCOCode)) else character()

  edges_in_area <- borough_data$edges_sf
  if (nrow(edges_in_area) > 0) {
    edges_in_area <- edges_in_area %>%
      filter(from_stop %in% active_ids | to_stop %in% active_ids)
  }

  streets_in_area  <- in_area(borough_data$streets_sf)
  stations_in_area <- in_area(borough_data$stations_sf)
  schools_in_area  <- in_area(borough_data$schools_sf)

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
        slice_head(n = MAX_STREET_LABELS) %>%
        select(name, geometry)
    }
  }

  # --- The searched postcode/property location, if one was passed in for
  #     this render (see render_lsoa_maps_for_borough()'s target_lon/
  #     target_lat args). When there isn't one, use a placeholder point well
  #     outside the visible frame (coord_sf() below clips it out) rather
  #     than a genuinely empty layer - an empty sf layer has no discernible
  #     point/line geometry type, so its legend key falls back to a plain
  #     box instead of the diamond used everywhere else for this level. ---
  target_sf <- st_sf(geometry = st_sfc(st_point(c(0, 0)), crs = 4326))
  if (!is.null(target_lon) && !is.null(target_lat)) {
    target_sf <- st_sf(geometry = st_sfc(st_point(c(target_lon, target_lat)), crs = 4326))
  }

  # Placeholder empty sf frames for any layer with nothing in this LSOA, so
  # every geom_sf() call below always runs (a 0-row layer draws nothing but
  # still registers its legend level) - that's what keeps the legend
  # identical across every LSOA. See LEGEND_LEVELS/LEGEND_COLORS.
  empty_lines  <- st_sf(geometry = st_sfc(crs = 4326))
  if (nrow(other_edges) == 0) other_edges <- empty_lines
  if (nrow(major_edges) == 0) major_edges <- empty_lines
  if (is.null(stops_in_area) || nrow(stops_in_area) == 0) stops_in_area <- st_sf(geometry = st_sfc(crs = 4326))
  if (is.null(stations_in_area) || nrow(stations_in_area) == 0) stations_in_area <- st_sf(name = character(), geometry = st_sfc(crs = 4326))
  if (is.null(schools_in_area) || nrow(schools_in_area) == 0) schools_in_area <- st_sf(school_name = character(), geometry = st_sfc(crs = 4326))

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

  # --- Every layer below maps `color` to one of LEGEND_LEVELS so a single
  #     shared scale/legend covers every symbol type (see
  #     LEGEND_OVERRIDE_AES for what glyph each one renders as). The LSOA
  #     boundary is intentionally understated (thin, dashed, muted) - most
  #     users don't know what an LSOA is, so it's context, not a headline
  #     feature. Bus routes are toned down slightly from their first pass
  #     for the same reason: readability of the whole map over any one layer. ---
  p <- p +
    geom_sf(data = lsoa_row, aes(color = "LSOA boundary"), fill = NA, linewidth = 0.7, linetype = "dashed", alpha = 0.65) +
    geom_sf(data = other_edges, aes(color = "Other bus route"), linewidth = 0.4, alpha = 0.6, lineend = "round") +
    geom_sf(data = major_edges, aes(color = "Major bus route"), linewidth = 2.2, alpha = 0.07, lineend = "round", show.legend = FALSE) +
    geom_sf(data = major_edges, aes(color = "Major bus route"), linewidth = 0.85, alpha = 0.85, lineend = "round") +
    geom_sf(data = stops_in_area, aes(color = "Bus stop"), size = 3, alpha = 0.15, show.legend = FALSE) +
    geom_sf(data = stops_in_area, aes(color = "Bus stop"), size = 1.1, alpha = 0.9) +
    geom_sf(data = stations_in_area, aes(color = "Station"), shape = 15, size = 2.2) +
    geom_sf(data = schools_in_area, aes(color = "School"), shape = 17, size = 2.4) +
    geom_sf(data = target_sf, aes(color = "Searched location"), shape = 18, size = 3.2, show.legend = FALSE) +
    geom_sf(data = target_sf, aes(color = "Searched location"), shape = 5, size = 5.5, stroke = 1)

  if (nrow(label_points) > 0) {
    p <- p + geom_text_repel(
      data = label_points,
      aes(label = label, geometry = geometry, color = I(label_color), fontface = I(label_face), size = I(label_size)),
      stat = "sf_coordinates", bg.color = BG_COLOR, bg.r = 0.12,
      max.overlaps = 60, segment.size = 0.3, segment.color = SUBTEXT_COLOR
    )
  }

  p <- p +
    scale_color_manual(
      name = "Legend",
      values = LEGEND_COLORS,
      breaks = LEGEND_LEVELS,
      limits = LEGEND_LEVELS,
      drop = FALSE
    ) +
    guides(color = guide_legend(override.aes = LEGEND_OVERRIDE_AES)) +
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

  ggsave(target_png, plot = p, dpi = 150, width = 7.5, height = 6)

  list(
    lsoa_code = lsoa_code, png = target_png,
    n_edges = nrow(edges_in_area), n_stops = nrow(stops_in_area), n_schools = nrow(schools_in_area)
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
    borough_name, lsoa_shp_dir, naptan_csv, gtfs_dir, schools_csv, osm_cache_dir, major_route_quantile
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
