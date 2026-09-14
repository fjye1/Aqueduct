# Aqueduct

A collection of London open-data ETL pipelines built on a medallion architecture
(`A_raw -> B_bronze -> C_silver -> D_gold`), landing in BigQuery, with an optional
sync step down to a Postgres OLTP database for serving.

Each **pipe** (`pipes/<pipe_name>/`) ingests one public dataset (housing, education,
police crime, council budgets, LSOA-level demographics, transport infrastructure,
etc.), cleans and reshapes it, and produces a borough- or LSOA-grain gold table
ready to query.

---

## 1. File tree

```
Aqueduct/
├── .env                        # secrets — PROJECT_ID, DATABASE_URL (not committed)
├── .example.env                # template for the above
├── requirements.txt            # pinned Python deps (pip freeze style)
├── pipeline.py                 # currently empty — not a working orchestrator
├── test.py                     # manual runner: uncomment the pipe stage(s) to run
├── test2.py / local_test.py    # scratch / one-off scripts, not part of the pipeline
│
├── pipes/                      # one folder per dataset ("pipe")
│   ├── council_budget/
│   ├── education/
│   ├── housing/
│   ├── infrastructure/         # PTAL / transit accessibility (borough grain)
│   ├── infrastructure_map/     # OSM street + station network data
│   │   └── download_osm.py     # pre-downloads OSM extracts per borough (via R)
│   ├── lsoa_demographics/      # LSOA-grain population/demographics
│   ├── lsoa_housing/           # LSOA-grain housing
│   ├── lsoa_map/               # LSOA boundary shapefiles
│   ├── lsoa_police/            # LSOA-grain crime (re-aggregated from police/ raw JSON)
│   ├── market_pressure_index/  # composite pressure index inputs
│   └── police/                 # borough-grain crime, pulled from the UK Police API
│       Each of the above (where applicable) contains:
│         B_bronze.py           # raw -> bronze: ingest + audit columns
│         C_silver.py           # bronze -> silver: extract, clean, cast, filter, join
│         D_gold.py             # silver -> gold: aggregate onto a borough/LSOA skeleton
│
├── utils/                      # shared, reusable pipeline building blocks
│   ├── io/
│   │   ├── ingestion.py        # Excel/CSV -> bronze CSV, with audit columns
│   │   ├── extraction.py       # bronze CSV -> silver DataFrame (column select/clean/cast)
│   │   └── yaml_loader.py      # (currently unused/empty)
│   ├── transformations/
│   │   ├── filters.py          # London/LSOA filters, geo joins, reshaping helpers
│   │   ├── clean_cast.py       # type coercion for silver columns (INTEGER/FLOAT/DATE/...)
│   │   └── aggregation.py      # GoldGrain, MetricAggregator, GoldMatrixPostProcessor
│   ├── operational/
│   │   ├── audit.py            # build_audit_columns (_source_file, _ingested_at, ...)
│   │   └── state.py            # incremental-load state + month-range helpers
│   ├── big_query/
│   │   ├── connection.py       # SQLAlchemy engine via local gcloud ADC
│   │   ├── import_big_query.py # DataFrame -> BigQuery (batch + streaming JSON)
│   │   └── export_big_query.py # BigQuery -> local CSV
│   ├── functions.py            # count_by_borough, standardise_names
│   └── helper.py               # sanitise, clean_and_cast (dup of transformations/clean_cast.py), find_headers
│
├── sync/                       # BigQuery gold layer -> Postgres OLTP
│   ├── config.py                # loads .env (DATABASE_URL, PROJECT_ID)
│   ├── database.py               # SQLAlchemy engine/session for Postgres
│   ├── models.py                  # ORM tables mirroring the gold layer (DistinctTable, ...)
│   └── bq_to_oltp.py               # copies each gold table from BigQuery into Postgres
│
├── tests/
│   ├── test_pipeline.py         # (currently empty)
│   └── test_utils.py            # e.g. dry-run test for load_into_bigquery
│
└── data/                       # local medallion storage (gitignored, per pipe)
    ├── A_raw/<pipe>/            # source files as downloaded (xlsx/csv/ods/shp/json/...)
    ├── B_bronze/<pipe>/         # 1:1 ingested copies + audit columns, minimal cleaning
    ├── C_silver/<pipe>/         # cleaned, typed, filtered, joined tables
    └── D_gold/<pipe>/           # final borough/LSOA-grain analytical tables
```

---

## 2. The medallion layers

| Layer | Folder | Produced by | What happens |
|---|---|---|---|
| Raw | `data/A_raw/<pipe>/` | manual download / API pull | Source files untouched, as received (xlsx, csv, ods, shapefiles, JSON) |
| Bronze | `data/B_bronze/<pipe>/` | `pipes/<pipe>/B_bronze.py` | Load each source file, stringify every column, stamp audit columns (`_source_file`, `_sheet_name`, `_ingested_at`, `_row_number`), write one CSV per source, upload to `bronze_layer` in BigQuery |
| Silver | `data/C_silver/<pipe>/` | `pipes/<pipe>/C_silver.py` | Pull only the needed columns/rows out of bronze by position, cast to real types (INTEGER/FLOAT/DATE/...), apply dataset-specific filters (London-only, date ranges, geo joins), optionally merge several silver tables together, upload to `silver_layer` |
| Gold | `data/D_gold/<pipe>/` | `pipes/<pipe>/D_gold.py` | Start from a fixed grain "skeleton" CSV (one row per borough or LSOA), merge in one or more silver metric sources, compute derived metrics (ratios, deviations from average, YoY change, ranks), upload to `gold_layer_borough` |

BigQuery datasets referenced by the pipes: `bronze_layer`, `silver_layer`, `gold_layer_borough`
(project id comes from `PROJECT_ID` in `.env`, current value hardcoded per-pipe as `roomreview-487913`).

An optional final step, `sync/bq_to_oltp.py`, copies the gold tables out of BigQuery
into a Postgres database (`DATABASE_URL` in `.env`) using the ORM models in `sync/models.py`,
for use by a serving application.

---

## 3. How a pipe is structured and run

There is **no central orchestrator** — `pipeline.py` is empty. Each pipe stage exposes
a single entry point, and you run stages by importing and calling them, e.g. from `test.py`:

```python
from pipes.housing.B_bronze import run_pipeline as bronze
from pipes.housing.C_silver import run_pipeline as silver
from pipes.housing.D_gold import run_pipeline as gold

PROJECT_ROOT = Path(__file__).resolve().parent
bronze(PROJECT_ROOT)
silver(PROJECT_ROOT)
gold(PROJECT_ROOT)
```

`test.py` already has every pipe's imports written out, commented — uncomment the
stage(s) you want and run `python test.py`. Stages must run in order (bronze before
silver before gold) since each reads the previous layer's CSV output from disk.

### Anatomy of B_bronze.py (Excel/CSV ingestion pattern)

Most bronze stages are declarative: a `PIPELINES` list of dicts, each describing one
source document and how to ingest it, fed into `utils/io/ingestion.py`:

```python
PIPELINES = [
    {
        "sources": [{"file": "Housing_Statistics_2025.xlsx", "sheet_index": "Table 2a", "year_name": "2025"}],
        "table_name": "Affordable_housing_net_additions_local",
        "ingestion_function": batch_ingestion_excel,   # or batch_ingestion_csv
    },
]
```
`run_pipeline(project_root)` resolves each `file` under `data/A_raw/<pipe>/`, calls the
ingestion function, and uploads each resulting DataFrame to BigQuery.

Two other bronze patterns exist:
- **API pull with incremental state** (`pipes/police/B_bronze.py`) — uses
  `utils/operational/state.py` (`generate_month_list`, `load_pipeline_state`,
  `save_pipeline_state`) to fetch new months only, writing partitioned JSON to
  `data/A_raw/police/police_crimes/year=YYYY/month=MM/`.
- **Direct file load** (e.g. `pipes/lsoa_map/B_bronze.py`) — a short ad hoc script,
  no `PIPELINES` config, for shapefiles etc.

### Anatomy of C_silver.py

A `PIPELINES` list defines, per table, which raw bronze columns to pull, the row
range, target types, and any row-filter function(s), fed into
`utils/io/extraction.py:column_row_extractor`:

```python
{
    "sources": [{"file": "ingestion_dwelling_stock_local_2021.csv", "year_name": "2021"}],
    "table_name": "housing_stock",
    "extraction_functions": [london_borough_filter],
    "data_row_start": 6, "data_row_end": 336,
    "columns": [
        {"col": 1, "name": "ons_code", "type": "STRING"},
        {"col": 7, "name": "total_dwellings", "type": "FLOAT"},
    ],
}
```
An optional top-level `JOINS` list merges several of that pipe's silver tables together
(e.g. `merge_housing_data`) once all `PIPELINES` entries have run.

### Anatomy of D_gold.py

Uses `utils/transformations/aggregation.py`:
- `GoldGrain(project_root, pipe_name, grain_columns)` loads `data/D_gold/<pipe>/_skeleton.csv`
  (the fixed list of boroughs or LSOAs) and exposes `.merge_metric(other_df, join_mapping)`
  to left-join each silver source onto it.
- `MetricAggregator.process(df, source_config)` is a config-driven transform pipeline
  applied to each silver source before merging — supports `filter_out`,
  `conditional_aggregations`, `sum_columns`, `groupby_cols`, `calculate_ratio`,
  `calculate_ratio_per_1k`, `calculate_deviation` (vs. group average),
  `calculate_yoy_change`, `calculate_rank`, `rename_cols`, `keep_cols`.

```python
GOLD_PIPELINES = {
    "table_name": "housing",
    "metric_sources": [{
        "file": "extraction_housing_merged.csv",
        "join_on": {"ons_code": "ons_code"},
        "keep_cols": ["year", "ons_code", "total_dwellings", ...],
        "calculate_deviation": [{"target_col": "average_price", "new_avg_col": "lon_average_price",
                                  "new_dev_col": "pct_diff_average_price", "group_by": ["year"]}],
    }],
}
```
The final `gold.base_df` is written to `data/D_gold/<pipe>/` and uploaded to
`gold_layer_borough`; some pipes also save a "latest year only" CSV/table.

---

## 4. Reusable functions by module

### `utils/io/ingestion.py`
- `ingestion_excel(file_path, sheet_target, pipe_name, output_name, table_name, year_name)` —
  loads one Excel sheet as all-string columns, stamps audit columns, writes to `B_bronze`.
- `batch_ingestion_excel(sources, pipe_name, output_name, table_name)` — loops `ingestion_excel`
  over a list of `{file, sheet_index, year_name}` sources, returns `{year_name: df}`.
- `ingestion_csv(file_path, pipe_name, output_name, table_name, year_name)` — CSV equivalent.
- `batch_ingestion_csv(sources, pipe_name, output_name, table_name)` — CSV equivalent of the batch loop.

### `utils/io/extraction.py`
- `column_row_extractor(file_path, pipe_name, data_row_start, data_row_end, columns, output_name, year_name=None, function_filter=None)` —
  pulls specific columns/rows out of a bronze CSV by position, renames, casts via
  `clean_and_cast`, applies an optional row filter, tags with `year_name`.

### `utils/transformations/filters.py`
- `london_borough_filter(df, filter_by_ons_code=True)` — restricts rows to the 33 London boroughs
  (by `ons_code` or by `BOROUGH` name). Uses constants `LONDON_BOROUGHS_UK` / `LONDON_BOROUGH_NAMES_UK`.
- `london_lsoa_filter(df, lsoa_column="lsoa21cd")` — restricts rows to LSOAs in `data/LSOA_skeleton.csv`.
- `melt_year_columns(df, var_name="year", value_name="net_additions")` — wide year columns -> long format.
- `merge_housing_data(dfs, on=("ons_code", "year"), how="left")` — normalizes each housing
  silver table's year column then chain-merges them all.
- `merge_school_and_ofsted(dfs, on="unique_reference_number", how="left")` — joins school location + Ofsted tables.
- `date_filter(df)` / `year_filter(df)` — keep rows within a fixed date/year range (2021–2026-ish).
- `os_to_lat_lon(df)` — converts OS Easting/Northing (EPSG:27700) to lon/lat (EPSG:4326).
- `get_borough_from_lat_lon(df)` — spatial join of points onto `data/A_raw/infrastructure/london_boroughs.shp`.
- `get_lsoa_from_lat_lon(df, lat_col, lon_col)` — spatial join of points onto the LSOA shapefiles in `data/A_raw/lsoa_police/`.
- `process_crime_df(df)` — maps raw police `category` to a coarser `analytical_category` via `CRIME_BUCKETS`.
- `pivot_raw_police_categories(df)` — pivots raw crime categories into one annualised-rate column each, plus a category lookup table.

### `utils/transformations/clean_cast.py` / `utils/helper.py:clean_and_cast`
- `clean_and_cast(series, col_type, col_name=None)` — standardises null-like strings, then
  casts to `STRING`/`INTEGER`/`FLOAT`/`DATE`/`DATETIME`/`TIMESTAMP`/`TIME`, logging any values
  that fail to parse. **Note:** this function is duplicated (with minor differences —
  `transformations/clean_cast.py` rounds fractional INTEGER values and parses dates
  `dayfirst=True`) between the two modules; `extraction.py` imports the `transformations` version.

### `utils/transformations/aggregation.py`
- `initialize_gold_skeleton(project_root, pipe_name, grain_columns)` — loads a pipe's `_skeleton.csv`.
- `GoldGrain` — wraps the skeleton DataFrame; `.merge_metric(other_df, join_mapping, how="left")`
  standardises join keys (lowercase, `&`-normalized) and left-merges a metric source onto it.
- `MetricAggregator.process(df, source_config)` — the gold-layer transform pipeline described above.
- `GoldMatrixPostProcessor.finalize(matrix_df, text_col="transport_line_name")` — fills count
  columns with 0 and consolidates transit network names onto one text column (used by infrastructure pipes).

### `utils/operational/audit.py`
- `build_audit_columns(df, source_file, sheet_target=None, existing=False)` — adds/refreshes
  `_source_file`, `_sheet_name`, `_ingested_at`, `_row_number`.

### `utils/operational/state.py`
- `generate_month_list(start_ym)` — list of `"YYYY-MM"` strings from `start_ym` up to
  2 months before today (matches the UK Police API's reporting delay).
- `load_pipeline_state(state_file_path)` / `save_pipeline_state(state, state_file_path)` —
  JSON checkpoint file for incremental/resumable ingestion (used by `pipes/police/B_bronze.py`).

### `utils/big_query/*`
- `connection.big_query_engine(project_id)` — SQLAlchemy engine using local `gcloud` ADC login.
- `import_big_query.load_into_bigquery(project_id, layer, table_name, df, dry_run)` —
  full-table `WRITE_TRUNCATE` load; `dry_run=True` just prints what would happen.
- `import_big_query.append_json_dataframe_to_bigquery(project_id, layer, table_name, df, json_column_name, dry_run, partition_col=None, clustering_fields=None)` —
  `WRITE_APPEND` load for tables with a native JSON column (bypasses PyArrow).
- `export_big_query.export_big_query(project_id, layer, table_name)` — pulls a BigQuery table
  down to a timestamped local CSV.

### `utils/functions.py` / `utils/helper.py`
- `count_by_borough(df, count_column_name)` — group-by-borough row counts (fills missing borough as "Unknown / Outside London").
- `standardise_names(series)` — lowercase, strip, normalize `" and "` -> `" & "` (used for fuzzy join keys).
- `sanitise(name)` — filesystem/BigQuery-safe slug (lowercase, underscores, strip bad chars).
- `find_headers(file_path, sheet_name)` — quick print of the first 15 rows of a sheet, for
  eyeballing where a table's real header/data rows start.
- `_pandas_dtype_to_bq(dtype)` — maps a pandas dtype to a BigQuery type string, used when
  building a `LoadJobConfig` schema.

### `sync/` (BigQuery -> Postgres)
- `config.Config` — reads `DATABASE_URL` and `PROJECT_ID` from `.env`.
- `database.py` — Postgres SQLAlchemy `engine`/`SessionLocal`/`Base`, plus `safe_commit(session)`.
- `models.py` — ORM tables mirroring `gold_layer_borough`: `DistinctTable` (boroughs, the parent
  table) with `EducationLondon`, `RentQuarterly`, `HousingPriceQuarterly`, `HousingStockAnnual`,
  `PolicePolice` relationships.
- `bq_to_oltp.sync_all_tables()` — creates the Postgres tables if needed, then copies each
  table in `tables_to_sync` from `gold_layer_borough` into Postgres (append-only).

---

## 5. Setup

1. `pip install -r requirements.txt`
2. Copy `.example.env` to `.env` and fill in:
   - `PROJECT_ID` — your GCP project id for BigQuery
   - `DATABASE_URL` — Postgres connection string (only needed for `sync/`)
3. Authenticate for BigQuery with Application Default Credentials:
   `gcloud auth application-default login`
4. Place source files for a pipe under `data/A_raw/<pipe_name>/` matching the
   filenames referenced in that pipe's `B_bronze.py`.
5. Run stages for a pipe (see `test.py` for the import pattern), in order:
   bronze -> silver -> gold. Most stages default to `dry_run=True` on the BigQuery
   load — flip to `False` once you've checked the printed dry-run output.

## 6. Tests

`pytest` — currently light coverage (`tests/test_utils.py` covers the
`load_into_bigquery` dry-run path). Most utility functions are marked
`# TODO build Test for this function` and are not yet covered.
