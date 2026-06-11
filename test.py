
from pathlib import Path
# # council_Budget
# from pipes.council_budget.B_bronze import run_pipeline
# from pipes.council_budget.C_silver import run_pipeline

# market_pressure_index
# from pipes.market_pressure_index.B_bronze import run_pipeline
from pipes.market_pressure_index.C_silver import run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent

run_pipeline(PROJECT_ROOT)
