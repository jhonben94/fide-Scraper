"""Aplicación FastAPI principal."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from src.api.routes import router
from src.database import init_db, get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la DB y ejecuta migraciones al arrancar."""
    engine = get_engine()
    init_db(engine)
    # Migraciones: añadir columnas si no existen
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS foa_title VARCHAR(50)"))
            conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS foa_rating INTEGER"))
            conn.commit()
    except Exception:
        pass
    yield


app = FastAPI(
    title="FIDE Scraper API",
    description="API para consultar datos de jugadores de la Federación Internacional de Ajedrez",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
def health():
    """Health check para monitoreo."""
    return {"status": "ok"}
