import os
from dotenv import load_dotenv

# Load environment variables from config/.env
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

# Use local data folder (copy of original)
PIPELINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_DIR = os.path.join(PIPELINE_DIR, "data", "raw")
GREENROOF_DIR = os.path.join(RAW_DATA_DIR, os.getenv("GREENROOF_SUBDIR", "greenroof"))
PARKPLATZ_DIR = os.path.join(RAW_DATA_DIR, os.getenv("PARKPLATZ_SUBDIR", "parkplatz"))
TIME_RESOLUTION = os.getenv("TIME_RESOLUTION", "minute")
