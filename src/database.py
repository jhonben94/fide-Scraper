"""Conexión y sesión de base de datos."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.models import Base


def get_engine(url: str | None = None):
    """Crea el engine de SQLAlchemy."""
    settings = get_settings()
    database_url = url or settings.database_url
    kwargs = {"pool_pre_ping": True}
    if not database_url.startswith("sqlite"):
        kwargs.update(
            pool_size=5,
            max_overflow=10,
            connect_args={"application_name": settings.fide_scraper_pg_application_name},
        )
    return create_engine(database_url, **kwargs)


def get_session_factory():
    """Crea la fábrica de sesiones."""
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(engine=None):
    """Inicializa esquema `fide` (si falta) y las tablas en la base de datos."""
    if engine is None:
        engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS fide"))
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager para obtener una sesión de base de datos."""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
