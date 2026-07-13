from datetime import datetime
import json

def generate_month_list(start_ym: str) -> list[str]:
    """Generates a list of YYYY-MM strings from start_ym up to the current month."""
    start_dt = datetime.strptime(start_ym, "%Y-%m")
    now_dt = datetime.now()

    months = []
    current_dt = start_dt
    while current_dt <= now_dt:
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