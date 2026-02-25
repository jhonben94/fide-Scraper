"""Orquestador del pipeline: descarga, parseo, importación a DB y exportación."""

import logging
from collections.abc import Iterator

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.database import get_db_session, get_engine, init_db
from src.downloader import download_fide_xml
from src.exporter import export_to_csv, export_to_json
from src.models import Player
from src.parser import parse_players_xml

logger = logging.getLogger(__name__)

BATCH_SIZE = 5000
EXPORT_LIMIT = 100_000  # Máximo jugadores a exportar (para evitar memoria)


def _batch_upsert(session: Session, batch: list[dict]) -> int:
    """Inserta o actualiza un batch de jugadores (upsert por fideid)."""
    if not batch:
        return 0

    stmt = pg_insert(Player).values(
        [
            {
                "fideid": p["fideid"],
                "name": p["name"],
                "country": p["country"],
                "sex": p.get("sex"),
                "title": p.get("title"),
                "rating": p.get("rating"),
                "games": p.get("games"),
                "rapid_rating": p.get("rapid_rating"),
                "rapid_games": p.get("rapid_games"),
                "blitz_rating": p.get("blitz_rating"),
                "blitz_games": p.get("blitz_games"),
                "birthday": p.get("birthday"),
                "flag": p.get("flag"),
                "foa_title": p.get("foa_title"),
                "foa_rating": p.get("foa_rating"),
            }
            for p in batch
        ]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["fideid"],
        set_={
            "name": stmt.excluded.name,
            "country": stmt.excluded.country,
            "sex": stmt.excluded.sex,
            "title": stmt.excluded.title,
            "rating": stmt.excluded.rating,
            "games": stmt.excluded.games,
            "rapid_rating": stmt.excluded.rapid_rating,
            "rapid_games": stmt.excluded.rapid_games,
            "blitz_rating": stmt.excluded.blitz_rating,
            "blitz_games": stmt.excluded.blitz_games,
            "birthday": stmt.excluded.birthday,
            "flag": stmt.excluded.flag,
            "foa_title": stmt.excluded.foa_title,
            "foa_rating": stmt.excluded.foa_rating,
        },
    )
    session.execute(stmt)
    return len(batch)


def _batched(iterator: Iterator[dict], size: int) -> Iterator[list[dict]]:
    """Agrupa un iterador en batches del tamaño indicado."""
    batch: list[dict] = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def run_import(
    period: str | None = None,
    export_json: bool = True,
    export_csv: bool = True,
) -> dict:
    """
    Ejecuta el pipeline completo: descarga -> parse -> DB -> export.

    Args:
        period: Fecha opcional YYYY-MM-DD para listas históricas.
        export_json: Si True, exporta a JSON.
        export_csv: Si True, exporta a CSV.

    Returns:
        Diccionario con estadísticas: total_imported, json_path, csv_path.
    """
    logger.info("Iniciando importación FIDE (period=%s)", period)

    # 1. Descargar XML
    xml_content = download_fide_xml(period=period)

    # 2. Inicializar DB
    engine = get_engine()
    init_db(engine)

    total = 0
    with get_db_session() as session:
        for batch in _batched(parse_players_xml(xml_content), BATCH_SIZE):
            _batch_upsert(session, batch)
            total += len(batch)
            if total % 50000 == 0 or total < 10000:
                logger.info("Importados %d jugadores...", total)

    result: dict = {"total_imported": total}

    # 3. Exportar desde DB (streaming para evitar memoria)
    if export_json or export_csv:
        with get_db_session() as session:
            stmt = select(Player).limit(EXPORT_LIMIT)
            players = [p.to_dict() for p in session.scalars(stmt).all()]
            if players:
                if export_json:
                    result["json_path"] = str(export_to_json(players))
                if export_csv:
                    result["csv_path"] = str(export_to_csv(players))

    logger.info("Importación completada: %d jugadores", total)
    return result
