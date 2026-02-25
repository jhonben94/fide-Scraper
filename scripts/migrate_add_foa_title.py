"""Migración: añade columna foa_title a la tabla players.

Ejecutar: python -m scripts.migrate_add_foa_title
O con Docker: docker compose run --rm app python -m scripts.migrate_add_foa_title
"""
import logging
import sys

from sqlalchemy import text

from src.database import get_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run():
    engine = get_engine()
    with engine.connect() as conn:
        # PostgreSQL: ADD COLUMN IF NOT EXISTS (desde PG 9.6)
        conn.execute(text("""
            ALTER TABLE players
            ADD COLUMN IF NOT EXISTS foa_title VARCHAR(50)
        """))
        conn.commit()
    logger.info("Migración completada: columna foa_title añadida (o ya existía)")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logger.exception("Error en migración: %s", e)
        sys.exit(1)
