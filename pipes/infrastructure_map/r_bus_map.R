# ==============================================================================
# Bus Stop Network Diagram in R
# Dependencies: install.packages(c("tidyverse", "sf", "viridis"))
# ==============================================================================

#options(download.file.method = "wininet")
#install.packages(c("tidyverse", "sf", "viridis"))


suppressPackageStartupMessages({
  library(tidyverse)
  library(sf)
  library(viridis)
})

# ============ CONFIG - Corrected for R ============
GTFS_DIR     <- "data/A_raw/infrastructure_map/itm_london_gtfs"
NAPTAN_CSV   <- "data/C_silver/infrastructure_map/test.csv"
BOROUGH_SHP  <- "data/A_raw/infrastructure/london_boroughs.shp"
BOROUGH_NAME <- "City of London"
OUTPUT_PNG   <- "bus_network_map_r.png"
# ==================================================


# --- 1. Load borough boundary and reproject to WGS84 (EPSG:4326) ---
boroughs_all <- st_read(BOROUGH_SHP, quiet = TRUE) %>%
  st_transform(crs = 4326)

borough <- boroughs_all %>%
  filter(BOROUGH == BOROUGH_NAME)


# --- 2. Load borough's stops from NaPTAN ---
naptan <- read_csv(NAPTAN_CSV, show_col_types = FALSE)
borough_stop_ids <- as.character(naptan$ATCOCode)


# --- 3. Load GTFS tables ---
stop_times <- read_csv(file.path(GTFS_DIR, "stop_times.txt"), col_types = cols(stop_id = "c", trip_id = "c"))
trips      <- read_csv(file.path(GTFS_DIR, "trips.txt"), col_types = cols(trip_id = "c", route_id = "c"))
routes     <- read_csv(file.path(GTFS_DIR, "routes.txt"), col_types = cols(route_id = "c"))
stops      <- read_csv(file.path(GTFS_DIR, "stops.txt"), col_types = cols(stop_id = "c"))


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


# --- 8. Attach coordinates & build sf LINESTRING geometries (Vectorized / Fast) ---
coords <- stops %>% select(stop_id, stop_lat, stop_lon)

edge_counts <- edge_counts %>%
  left_join(coords, by = c("from_stop" = "stop_id")) %>%
  rename(from_lat = stop_lat, from_lon = stop_lon) %>%
  left_join(coords, by = c("to_stop" = "stop_id")) %>%
  rename(to_lat = stop_lat, to_lon = stop_lon) %>%
  filter(!is.na(from_lon) & !is.na(to_lon) & !is.na(from_lat) & !is.na(to_lat))

# Fast matrix-based LINESTRING generation (prevents console hanging)
orig <- as.matrix(edge_counts[, c("from_lon", "from_lat")])
dest <- as.matrix(edge_counts[, c("to_lon", "to_lat")])

lines_list <- lapply(seq_len(nrow(edge_counts)), function(i) {
  st_linestring(rbind(orig[i, ], dest[i, ]))
})

edges_sf <- edge_counts %>%
  mutate(geometry = st_sfc(lines_list, crs = 4326)) %>%
  st_as_sf()

# Only keep NaPTAN bus stops that are active in our internal network
active_stop_ids <- unique(c(edge_counts$from_stop, edge_counts$to_stop))
stops_sf <- naptan %>%
  filter(ATCOCode %in% active_stop_ids) %>%
  st_as_sf(coords = c("Longitude", "Latitude"), crs = 4326)

cat(sprintf("Internal stops in network: %d\n", nrow(stops_sf)))
cat(sprintf("Internal trips counted: %d\n", length(unique(edges$trip_id))))
cat(sprintf("Unique internal edges: %d\n", nrow(edge_counts)))


# --- 9. Plotting with ggplot2 ---
network_map <- ggplot() +
  # Layer 1: Borough Polygon & Outline
  geom_sf(data = borough, fill = "#f8f9fa", color = "#1a1a1a", size = 0.8) +

  # Layer 2: Internal Network Edges (Line width & color mapped to trip_count)
  geom_sf(
    data = edges_sf,
    aes(size = trip_count, color = trip_count),
    alpha = 0.7
  ) +

  # Layer 3: Internal Bus Stops
  geom_sf(data = stops_sf, color = "red", size = 1.2, alpha = 0.8) +

  # Aesthetic Adjustments
  scale_size_continuous(range = c(0.4, 2.5), name = "Trip Frequency") +
  scale_color_viridis_c(option = "plasma", direction = -1, name = "Trip Frequency") +

  # Clean map style
  theme_void() +
  labs(
    title = paste("Internal Bus Network -", BOROUGH_NAME),
    subtitle = "Showing only connections where both stops are inside the borough"
  ) +
  theme(
    plot.title = element_text(size = 16, face = "bold", hjust = 0.5, margin = margin(b = 4)),
    plot.subtitle = element_text(size = 11, color = "grey40", hjust = 0.5, margin = margin(b = 10)),
    legend.position = "right",
    plot.background = element_rect(fill = "white", color = NA)
  )

# Save high-resolution PNG
ggsave(OUTPUT_PNG, plot = network_map, dpi = 300, width = 10, height = 10)
cat(sprintf("Saved map to %s\n", OUTPUT_PNG))