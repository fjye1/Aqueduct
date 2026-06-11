
from pathlib import Path
from pipes.council_budget.B_bronze import run_pipeline
# from pipes.council_budget.C_silver import run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent

run_pipeline(PROJECT_ROOT)