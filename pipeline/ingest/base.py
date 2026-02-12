import psycopg2
from config.settings import DB_CONFIG


def get_connection():
    """Return a psycopg2 connection using .env settings."""
    return psycopg2.connect(**DB_CONFIG)
