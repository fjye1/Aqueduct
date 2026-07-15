# sync/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sync.config import Config

# 1. Create the engine
engine = create_engine(Config.DATABASE_URL)

# 2. Configure the session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Create the base class for your models to inherit from
Base = declarative_base()

# 4. Your custom safe commit helper (stripped of Flask context)
def safe_commit(session):
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise