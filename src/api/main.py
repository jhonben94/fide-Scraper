"""Aplicación FastAPI principal."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text

from src.api.admin_routes import admin_router
from src.api.deps import verify_admin_access, verify_optional_api_key
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
            conn.execute(text("ALTER TABLE fide.players ADD COLUMN IF NOT EXISTS foa_title VARCHAR(50)"))
            conn.execute(text("ALTER TABLE fide.players ADD COLUMN IF NOT EXISTS foa_rating INTEGER"))
            conn.execute(text("ALTER TABLE fide.players ADD COLUMN IF NOT EXISTS flag_std VARCHAR(5)"))
            conn.execute(text("ALTER TABLE fide.players ADD COLUMN IF NOT EXISTS flag_rpd VARCHAR(5)"))
            conn.execute(text("ALTER TABLE fide.players ADD COLUMN IF NOT EXISTS flag_blz VARCHAR(5)"))
            conn.execute(
                text(
                    "ALTER TABLE fide.players ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                )
            )
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

app.include_router(router, dependencies=[Depends(verify_optional_api_key)])
app.include_router(admin_router, dependencies=[Depends(verify_admin_access)])


@app.get("/health")
def health():
    """Health check para monitoreo."""
    return {"status": "ok"}
