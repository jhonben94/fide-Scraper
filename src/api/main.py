"""Aplicación FastAPI principal."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

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
    """Health check legado, equivalente a liveness."""
    return {"status": "ok"}


@app.get("/health/live")
def health_live():
    """Confirma que el proceso HTTP está respondiendo."""
    return {"status": "ok"}


@app.get("/health/ready", responses={503: {"description": "Servicio no disponible"}})
def health_ready():
    """Comprueba conexión y estructura mínima requerida para servir la API."""
    engine = None
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).scalar_one()
            inspector = inspect(conn)
            schema_ready = inspector.has_schema("fide")
            tables_ready = all(
                inspector.has_table(table_name, schema="fide")
                for table_name in ("players", "player_rating_history")
            )
        if not schema_ready or not tables_ready:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    finally:
        if engine is not None:
            engine.dispose()

    return {"status": "ok"}
