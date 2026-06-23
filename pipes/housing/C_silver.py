from pathlib import Path

import pandas as pd

from utils.big_query.import_big_query import load_into_bigquery
from utils.extraction import column_row_extractor
from utils.filters import london_borough_filter, date_filter

# tables each borough appearing 5 times

# silver_council_tax_bands X
# silver_avg_house_price X
# silver_housing_stock X
# silver_housing_stock_additions X
# silver_affordable_housing X


# ──pipes/housing/C_silver Config ───────────────────────────────────────────────────────────────────
PIPELINES = [

    {
        "sources": [
            {
                "file": "ingestion_dwelling_stock_local_2021.csv",
                "year_name": "2021"
            },
            {
                "file": "ingestion_dwelling_stock_local_2022.csv",
                "year_name": "2022"
            },
            {
                "file": "ingestion_dwelling_stock_local_2023.csv",
                "year_name": "2023"
            },
            {
                "file": "ingestion_dwelling_stock_local_2024.csv",
                "year_name": "2024"
            },
            {
                "file": "ingestion_dwelling_stock_local_2025.csv",
                "year_name": "2025"
            }
        ],
        "table_name": "housing_stock",
        "extraction_functions": [london_borough_filter],
        "data_row_start": 6,
        "data_row_end": 336,
        "columns": [
            {"col": 1, "name": "ons_code", "type": "STRING"},
            {"col": 2, "name": "Area", "type": "STRING"},
            {"col": 3, "name": "local_authority", "type": "FLOAT"},
            {"col": 4, "name": "private_registered_provider", "type": "FLOAT"},
            {"col": 5, "name": "Other public sector ", "type": "FLOAT"},
            {"col": 6, "name": "private_sector", "type": "FLOAT"},
            {"col": 7, "name": "total_dwellings", "type": "FLOAT"},
            {"col": 8, "name": "_source_file", "type": "STRING"},
            {"col": 9, "name": "_sheet_name", "type": "STRING"},
            {"col": 10, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 11, "name": "_row_number", "type": "INTEGER"},
        ]
    },
    {
        "sources": [
            {
                "file": "ingestion_Affordable_housing_net_additions_local_2021.csv",
                "year_name": "2021"
            },
            {
                "file": "ingestion_Affordable_housing_net_additions_local_2022.csv",
                "year_name": "2022"
            },
            {
                "file": "ingestion_Affordable_housing_net_additions_local_2023.csv",
                "year_name": "2023"
            },
            {
                "file": "ingestion_Affordable_housing_net_additions_local_2024.csv",
                "year_name": "2024"
            },
            {
                "file": "ingestion_Affordable_housing_net_additions_local_2025.csv",
                "year_name": "2025"
            }
        ],
        "table_name": "affordable_stock_additions",
        "extraction_functions": [london_borough_filter],
        "data_row_start": 12,
        "data_row_end": 300,
        "columns": [
            {"col": 0, "name": "ons_code", "type": "STRING"},
            {"col": 1, "name": "Area", "type": "STRING"},
            {"col": 20, "name": "total", "type": "INTEGER"},
            {"col": 21, "name": "_source_file", "type": "STRING"},
            {"col": 22, "name": "_sheet_name", "type": "STRING"},
            {"col": 23, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 24, "name": "_row_number", "type": "INTEGER"},
        ]
    },
    {
        "sources": [
            {
                "file": "ingestion_Council_tax_2021.csv",
                "year_name": "2021"
            },
            {
                "file": "ingestion_Council_tax_2022.csv",
                "year_name": "2022"
            },
            {
                "file": "ingestion_Council_tax_2023.csv",
                "year_name": "2023"
            },
            {
                "file": "ingestion_Council_tax_2024.csv",
                "year_name": "2024"
            },
            {
                "file": "ingestion_Council_tax_2025.csv",
                "year_name": "2025"
            }
        ],
        "table_name": "council_tax_bands",
        "extraction_functions": [london_borough_filter],
        "data_row_start": 3,
        "data_row_end": 38,
        "columns": [
            {"col": 0, "name": "ons_code", "type": "STRING"},
            {"col": 1, "name": "Area", "type": "STRING"},
            {"col": 2, "name": "band_a", "type": "INTEGER"},
            {"col": 3, "name": "band_b", "type": "INTEGER"},
            {"col": 4, "name": "band_c", "type": "INTEGER"},
            {"col": 5, "name": "band_d", "type": "INTEGER"},
            {"col": 6, "name": "band_e", "type": "INTEGER"},
            {"col": 7, "name": "band_f", "type": "INTEGER"},
            {"col": 8, "name": "band_g", "type": "INTEGER"},
            {"col": 9, "name": "band_h", "type": "INTEGER"},
            {"col": 10, "name": "_source_file", "type": "STRING"},
            {"col": 11, "name": "_sheet_name", "type": "STRING"},
            {"col": 12, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 13, "name": "_row_number", "type": "INTEGER"},
        ]

    },
    {
        "sources": [
            {
                "file": "ingestion_average_house_prices_1968-2026.csv",
                "year_name": "9"
            }
        ],
        "table_name": "average_house_price",
        "extraction_functions": [london_borough_filter, date_filter],
        "data_row_start": 6,
        "data_row_end": 150302,
        "columns": [
            {"col": 0, "name": "date", "type": "DATETIME"},
            {"col": 1, "name": "Area", "type": "STRING"},
            {"col": 2, "name": "ons_code", "type": "STRING"},
            {"col": 3, "name": "average_price", "type": "FLOAT"},
            {"col": 7, "name": "_source_file", "type": "STRING"},
            {"col": 8, "name": "_sheet_name", "type": "STRING"},
            {"col": 9, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 10, "name": "_row_number", "type": "INTEGER"},
        ]

    },
    {
        "sources": [
            {
                "file": "ingestion_net_additional_dwelling_local_2001-2025.csv",
                "year_name": "9"
            }
        ],
        "table_name": "net_housing_additions",
        "extraction_functions": [london_borough_filter],
        "data_row_start": 7,
        "data_row_end": 430,
        "columns": [
            {"col": 3, "name": "Area", "type": "STRING"},
            {"col": 2, "name": "ons_code", "type": "STRING"},
            {"col": 23, "name": "2021_additions", "type": "FLOAT"},
            {"col": 24, "name": "2022_additions", "type": "FLOAT"},
            {"col": 25, "name": "2023_additions", "type": "FLOAT"},
            {"col": 26, "name": "2024_additions", "type": "FLOAT"},
            {"col": 27, "name": "2025_additions", "type": "FLOAT"},
            {"col": 28, "name": "_source_file", "type": "STRING"},
            {"col": 29, "name": "_sheet_name", "type": "STRING"},
            {"col": 30, "name": "_ingested_at", "type": "DATETIME"},
            {"col": 31, "name": "_row_number", "type": "INTEGER"},
        ]

    }
]

PIPE_NAME = "housing"
PROJECT_ID = "roomreview-487913"
LAYER = "silver_layer"
OUTPUT_NAME = "extraction"


def run_pipeline(project_root: Path):
    folder = project_root / "data" / "B_bronze" / PIPE_NAME

    for config in PIPELINES:
        table_name = config["table_name"]
        processed_dfs = []

        print(f"\n--- Processing Pipeline: {table_name} ---")

        for src in config["sources"]:
            raw_file = folder / src["file"]
            year_name = src["year_name"]

            if not raw_file.exists():
                print(f"  [SKIP] File not found: {raw_file}")
                continue

            print(f"  Processing file: {raw_file.name}")

            raw_filters = config.get("extraction_functions") or [config.get("extraction_function")]
            raw_filters = [f for f in raw_filters if f is not None]

            # Compose multiple filters into one callable if needed
            if len(raw_filters) > 1:
                def combined_filter(df, filters=raw_filters):
                    for f in filters:
                        df = f(df)
                    return df

                function_filter = combined_filter
            elif len(raw_filters) == 1:
                function_filter = raw_filters[0]
            else:
                function_filter = None

            try:
                df = column_row_extractor(
                    file_path=raw_file,
                    data_row_start=config["data_row_start"],
                    data_row_end=config["data_row_end"],
                    columns=config["columns"],
                    output_name=OUTPUT_NAME,
                    pipe_name=PIPE_NAME,
                    function_filter=function_filter,
                    year_name=year_name
                )
                processed_dfs.append(df)

            except Exception as e:
                print(f"  [ERROR] Failed to process {raw_file.name}: {e}")
                continue

        # Concat and upload per pipeline table
        if processed_dfs:
            final_df = pd.concat(processed_dfs, ignore_index=True)
            min_year = int(final_df["year_name"].min())
            max_year = int(final_df["year_name"].max())

            out_path = project_root / "data" / "C_silver" / PIPE_NAME / f"{OUTPUT_NAME}_{table_name}{min_year}_{max_year}.csv"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            final_df.to_csv(out_path, index=False)
            print(f"  Saved to {out_path}")

            print(f"  Uploading to BigQuery table: {PIPE_NAME}_{table_name}...")
            load_into_bigquery(
                project_id=PROJECT_ID,
                layer=LAYER,
                table_name=f"{PIPE_NAME}_{table_name}",
                df=final_df,
                dry_run=True  # Set to False when ready to upload
            )
        else:
            print(f"  [WARN] No data processed for pipeline: {table_name}")
