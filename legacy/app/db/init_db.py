from pathlib import Path

from app.core.logging import get_logger
from app.db.connection import get_db_connection

logger = get_logger("db.migrations")
SCHEMA_ORDER = [
    "schemas.sql",
    "trading_schema.sql",
    "history_schema.sql",
    "benchmark_schema.sql",
]


def init_db() -> None:
    base_dir = Path(__file__).resolve().parent
    with get_db_connection() as conn:
        cur = conn.cursor()
        for schema_file in SCHEMA_ORDER:
            schema_path = base_dir / schema_file
            logger.info("applying_schema", schema=str(schema_path))
            sql = schema_path.read_text(encoding="utf-8")
            cur.execute(sql)
        conn.commit()
        cur.close()
    logger.info("database_initialized", applied=len(SCHEMA_ORDER))


if __name__ == "__main__":
    init_db()


