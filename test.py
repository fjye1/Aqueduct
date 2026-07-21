from pathlib import Path

# market_pressure_index
# from pipes.market_pressure_index.B_bronze import run_pipeline
# from pipes.market_pressure_index.C_silver import run_pipeline

# # council_Budget
# from pipes.council_budget.B_bronze import run_pipeline
# from pipes.council_budget.C_silver import run_pipeline

# Housing
# from pipes.housing.B_bronze import run_pipeline
# from pipes.housing.C_silver import run_pipeline
# from pipes.housing.D_gold import run_pipeline

#Infrastructure
# from pipes.infrastructure.B_bronze import run_pipeline
# from pipes.infrastructure.C_silver import run_pipeline
# from pipes.infrastructure.D_gold import run_pipeline

#Education
# from pipes.education.B_bronze import run_pipeline
# from pipes.education.C_silver import run_pipeline
# from pipes.education.D_gold import run_pipeline

#Police
from pipes.police.B_bronze import run_pipeline
# from pipes.police.C_silver import run_pipeline
# from pipes.police.D_gold import run_pipeline


PROJECT_ROOT = Path(__file__).resolve().parent

run_pipeline(PROJECT_ROOT)








