"""Orquestador del pipeline: descarga, parseo, importación a DB y exportación."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.database import get_db_session, get_engine, init_db
from src.downloader import extracted_xml_tempfile
from src.exporter import export_to_csv, export_to_json
from src.models import Player
from src.parser import parse_players_xml_path

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
            "updated_at": func.now(),
        },
    )
    session.execute(stmt)
    return len(batch)


def _normalize_country_codes(codes: frozenset[str] | None) -> frozenset[str] | None:
    if not codes:
        return None
    out = frozenset(c.strip().upper() for c in codes if c and str(c).strip())
    return out or None


def _player_matches_country(player: dict, country_codes: frozenset[str] | None) -> bool:
    if not country_codes:
        return True
    return (player.get("country") or "").strip().upper() in country_codes


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
    fide_ids: frozenset[int] | None = None,
    country_codes: frozenset[str] | None = None,
) -> dict:
    """
    Ejecuta el pipeline completo: descarga -> parse -> DB -> export.

    Args:
        period: Fecha opcional YYYY-MM-DD para listas históricas.
        export_json: Si True, exporta a JSON.
        export_csv: Si True, exporta a CSV.
        fide_ids: Si se define, solo se hace upsert de estos FIDE ID (el XML completo se sigue
            parseando en streaming; útil para API / import puntual).
        country_codes: Si se define (p. ej. ``frozenset({"PAR"})``), solo se persisten esas
            federaciones FIDE. El XML completo se sigue parseando en streaming.

    Returns:
        Diccionario con estadísticas: total_imported, total_parsed_rows, json_path, csv_path.
    """
    codes = None if fide_ids else _normalize_country_codes(country_codes)
    logger.info(
        "Iniciando importación FIDE (period=%s, fide_ids=%s, countries=%s)",
        period,
        f"solo {len(fide_ids)} id(s)" if fide_ids else "todos",
        sorted(codes) if codes else "todas",
    )

    engine = get_engine()
    init_db(engine)

    parsed_rows = 0
    upserted = 0
    with extracted_xml_tempfile(period=period) as xml_path:
        with get_db_session() as session:
            for batch in _batched(parse_players_xml_path(xml_path), BATCH_SIZE):
                parsed_rows += len(batch)
                if fide_ids:
                    batch = [p for p in batch if int(p.get("fideid", 0)) in fide_ids]
                elif codes:
                    batch = [p for p in batch if _player_matches_country(p, codes)]
                if not batch:
                    continue
                _batch_upsert(session, batch)
                upserted += len(batch)
                if not fide_ids and (upserted % 50000 == 0 or upserted < 10000):
                    logger.info("Importados %d jugadores...", upserted)
                elif fide_ids and upserted and upserted % 1000 == 0:
                    logger.info("Importados %d filas (filtro FIDE)...", upserted)

    result: dict = {
        "total_imported": upserted,
        "total_parsed_rows": parsed_rows,
        "fide_ids_mode": bool(fide_ids),
        "fide_id_count": len(fide_ids) if fide_ids else None,
        "country_codes": sorted(codes) if codes else None,
    }

    # Exportar solo los jugadores solicitados si hay filtro; si no, primeros EXPORT_LIMIT.
    if export_json or export_csv:
        with get_db_session() as session:
            if fide_ids:
                ids_list = list(fide_ids)
                stmt = select(Player).where(Player.fideid.in_(ids_list))
            elif codes:
                stmt = (
                    select(Player)
                    .where(func.upper(Player.country).in_(codes))
                    .limit(EXPORT_LIMIT)
                )
            else:
                stmt = select(Player).limit(EXPORT_LIMIT)
            players = [p.to_dict() for p in session.scalars(stmt).all()]
            if players:
                if export_json:
                    result["json_path"] = str(export_to_json(players))
                if export_csv:
                    result["csv_path"] = str(export_to_csv(players))

    logger.info("Importación completada: %d upserts (%d filas parseadas)", upserted, parsed_rows)
    return result
