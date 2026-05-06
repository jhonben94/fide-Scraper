"""Migración legacy: añade columnas FOA en fide.players (Flyway V6 ya las incluye).

Ejecutar: python -m scripts.migrate_add_foa_title
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
            ALTER TABLE fide.players
            ADD COLUMN IF NOT EXISTS foa_title VARCHAR(50)
        """))
        conn.execute(text("""
            ALTER TABLE fide.players
            ADD COLUMN IF NOT EXISTS foa_rating INTEGER
        """))
        conn.commit()
    logger.info("Migración completada: fide.players foa_title / foa_rating (o ya existían)")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logger.exception("Error en migración: %s", e)
        sys.exit(1)
