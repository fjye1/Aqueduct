# ==============================================================================
# Small dark "schools nearby" map for the lsoa_nearby card: faint street
# basemap, the listed schools as green triangles with names, and a blue marker
# for the point the distances are measured from (LSOA centre by default, or
# "Your property" once a real property/postcode point is supplied).
#
# Deliberately NOT the busy lsoa_map renderer - no routes, boundaries or postcode
# shading, just enough to orient a reader. Reads the OSM street caches built by
# infrastructure_map (read-only).
#
#   RUN_ON_SOURCE <- FALSE
#   source("pipes/lsoa_nearby/r_schools_map.R")
#   render_schools_maps_for_borough("Kingston upon Thames", c("E01002969"), ...)
# ==============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(sf)
  library(ggrepel)
})

# Whole-London extract cached by infrastructure_map (read-only). Read with a spatial filter per
# map, so streets are there even where a school sits across a borough line (infrastructure_map's
# per-borough street caches are clipped at each borough edge, and missing for 3 boroughs).
OSM_GPKG_DEFAULT <- "data/A_raw/infrastructure_map/_osmextract_cache/geofabrik_greater-london-latest.gpkg"

BG_COLOR     <- "#0f1626"
STREET_COLOR <- "#2b3446"
SCHOOL_COLOR <- "#22c55e"
CENTRE_COLOR <- "#3b82f6"
TEXT_COLOR   <- "#e5e7eb"

MIN_HALF_WIDTH_M <- 500    # never zoom in tighter than this, even for one nearby school
ASPECT           <- 1.6    # width / height of the output image

slugify_borough <- function(borough_name) {
  slug <- tolower(borough_name)
  slug <- gsub("[^a-z0-9]+", "_", slug)
  gsub("^_+|_+$", "", slug)
}

# Frame (in metres, EPSG:27700) that contains every point, padded, at ASPECT.
.frame_for <- function(xy, pad_m) {
  xmin <- min(xy[, 1]) - pad_m; xmax <- max(xy[, 1]) + pad_m
  ymin <- min(xy[, 2]) - pad_m; ymax <- max(xy[, 2]) + pad_m
  w <- max(xmax - xmin, 2 * MIN_HALF_WIDTH_M)
  h <- max(ymax - ymin, 2 * MIN_HALF_WIDTH_M / ASPECT)
  if (w / h < ASPECT) w <- h * ASPECT else h <- w / ASPECT
  cx <- (xmin + xmax) / 2; cy <- (ymin + ymax) / 2
  c(xmin = cx - w / 2, xmax = cx + w / 2, ymin = cy - h / 2, ymax = cy + h / 2)
}

render_schools_maps_for_borough <- function(borough_name,
                                            lsoa_codes,
                                            centres_csv,
                                            schools_csv,
                                            output_dir,
                                            gpkg_path     = OSM_GPKG_DEFAULT,
                                            centre_label  = "Area centre",
                                            pad_m         = 350) {

  slug    <- slugify_borough(borough_name)
  out_dir <- file.path(output_dir, slug)
  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

  centres <- read_csv(centres_csv, show_col_types = FALSE) %>% filter(lsoa_code %in% lsoa_codes)
  schools <- read_csv(schools_csv, show_col_types = FALSE) %>% filter(lsoa_code %in% lsoa_codes)

  for (code in centres$lsoa_code) {
    ctr <- centres %>% filter(lsoa_code == code)
    sch <- schools %>% filter(lsoa_code == code) %>%
      distinct(school_name, school_easting, school_northing)

    pts <- rbind(c(ctr$easting, ctr$northing),
                 if (nrow(sch) > 0) cbind(sch$school_easting, sch$school_northing))
    fr  <- .frame_for(pts, pad_m)

    frame_poly <- st_as_sfc(st_bbox(
      c(xmin = fr[["xmin"]], ymin = fr[["ymin"]], xmax = fr[["xmax"]], ymax = fr[["ymax"]]),
      crs = st_crs(27700)))

    p <- ggplot()

    streets_in <- tryCatch(
      st_read(gpkg_path, query = "SELECT * FROM lines WHERE highway IS NOT NULL",
              wkt_filter = st_as_text(st_geometry(st_transform(frame_poly, 4326))), quiet = TRUE),
      error = function(e) { cat(sprintf("  [WARN] streets read failed for %s: %s\n", code, conditionMessage(e))); NULL }
    )
    if (!is.null(streets_in) && nrow(streets_in) > 0) {
      streets_in <- st_sf(geometry = st_geometry(st_transform(streets_in, 27700)))
      p <- p + geom_sf(data = streets_in, color = STREET_COLOR, linewidth = 0.3)
    }

    if (nrow(sch) > 0) {
      sch_sf <- sch %>%
        st_as_sf(coords = c("school_easting", "school_northing"), crs = 27700, remove = FALSE) %>%
        mutate(label = str_wrap(school_name, 18))
      p <- p +
        geom_sf(data = sch_sf, color = SCHOOL_COLOR, shape = 17, size = 3.6) +
        geom_text_repel(
          data = sch_sf, aes(label = label, geometry = geometry), stat = "sf_coordinates",
          size = 2.9, color = TEXT_COLOR, bg.color = BG_COLOR, bg.r = 0.15, lineheight = 0.9,
          max.overlaps = Inf, segment.size = 0.25, segment.color = "#64748b", min.segment.length = 0.2
        )
    }

    ctr_sf <- ctr %>% st_as_sf(coords = c("easting", "northing"), crs = 27700) %>%
      mutate(label = centre_label)
    p <- p +
      geom_sf(data = ctr_sf, shape = 21, fill = CENTRE_COLOR, color = "white", size = 4.4, stroke = 1.3) +
      geom_text_repel(
        data = ctr_sf, aes(label = label, geometry = geometry), stat = "sf_coordinates",
        size = 3, fontface = "bold", color = "white", bg.color = BG_COLOR, bg.r = 0.15,
        max.overlaps = Inf, segment.size = 0.25, segment.color = "#64748b"
      ) +
      coord_sf(xlim = c(fr[["xmin"]], fr[["xmax"]]), ylim = c(fr[["ymin"]], fr[["ymax"]]),
               expand = FALSE, datum = NA) +
      theme_void() +
      theme(
        plot.background  = element_rect(fill = BG_COLOR, color = NA),
        panel.background = element_rect(fill = BG_COLOR, color = NA),
        plot.margin      = margin(0, 0, 0, 0)
      )

    target <- file.path(out_dir, sprintf("%s.png", code))
    ggsave(target, plot = p, width = 6.4, height = 4.0, dpi = 200, bg = BG_COLOR)
    cat(sprintf("  map -> %s (%d schools)\n", basename(target), nrow(sch)))
  }

  invisible(out_dir)
}
