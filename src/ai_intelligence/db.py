import psycopg

from ai_intelligence.config import DATABASE_URL


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)
