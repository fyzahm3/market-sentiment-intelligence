from contextlib import contextmanager

import psycopg2

from app.core.config import settings


@contextmanager
def get_db_connection():
    conn = psycopg2.connect(settings.database_url)
    try:
        yield conn
    finally:
        conn.close()
