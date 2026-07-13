from datetime import datetime
from dateutil.relativedelta import relativedelta
import json


def generate_month_list(start_ym: str) -> list[str]:
    """
    Generates a list of YYYY-MM strings from start_ym up to the latest available month
    accounting for the API's standard 2-month reporting delay.
    """
    start_dt = datetime.strptime(start_ym, "%Y-%m")

    # Calculate the max available month based on the 2-month delay
    # If today is 2026-07, max_dt becomes 2026-05
    max_dt = datetime.now() - relativedelta(months=2)

    # Safety check: if start date is further in the future than the delay allows
    if start_dt > max_dt:
        return []

    months = []
    current_dt = start_dt

    # Change the condition to stop at the max delayed date instead of now_dt
    while current_dt <= max_dt:
        months.append(current_dt.strftime("%Y-%m"))
        if current_dt.month == 12:
            current_dt = current_dt.replace(year=current_dt.year + 1, month=1)
        else:
            current_dt = current_dt.replace(month=current_dt.month + 1)

    return months

def load_pipeline_state(state_file_path) -> dict:
    if state_file_path.exists():
        with open(state_file_path, "r") as f:
            return json.load(f)
    return {"processed_batches": []}


def save_pipeline_state(state: dict,state_file_path):
    state_file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file_path, "w") as f:
        json.dump(state, f, indent=4)