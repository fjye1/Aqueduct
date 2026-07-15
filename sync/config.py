import os
from dotenv import load_dotenv

# Find the project root directory
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # Get the DB connection string from your .env
    DATABASE_URL = os.environ.get("DATABASE_URL")