# 1. Expose the main pipeline function for the aqueduct orchestrator
from sync.bq_to_oltp import etl_pipeline

# 2. Expose models and database objects (optional, but helpful for debugging)
from sync.database import engine, SessionLocal, Base
from sync.models import Borough, BoroughTransport, BoroughHousingYearly

# 3. Explicitly define what gets imported when someone uses "from sync import *"
__all__ = [
    "etl_pipeline",
    "engine",
    "SessionLocal",
    "Base",
    "Borough",
    "BoroughTransport",
    "BoroughHousingYearly"
]