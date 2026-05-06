
"""Importación de flags FIDE por modalidad desde los ZIP de archivo (standard/rapid/blitz XML)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import text

from src.database import get_db_session, get_engine, init_db
from src.downloader import discover_period_archive_xml_zip_urls, extracted_xml_from_zip_url
from src.parser import parse_players_xml_path

logger = logging.getLogger(__name__)


ALLOWED_FLAG_COLUMNS = frozenset({"flag_std", "flag_rpd", "flag_blz"})



def _resolve_period(engine: Any, period: str | None) -> str:
    """Periodo `YYYY-MM-DD` para a_download.php; por defecto max(period) del historial."""
    if period and str(period).strip():
        p = str(period).strip()[:10]
        date.fromisoformat(p)
        return p
    with engine.connect() as conn:
        row = conn.execute(text("SELECT MAX(period) FROM fide.player_rating_history")).scalar()
        if row is None:
            raise ValueError(
                "No hay filas en fide.player_rating_history: pasá period=YYYY-MM-DD "
                "(primer día de mes, ej. 2026-05-01) o importá historial primero."
            )
        return row.isoformat() if hasattr(row, "isoformat") else str(row)


def _collect_flags_from_zip(url: str) -> dict[int, str | None]:
    """Parsea un ZIP de lista FIDE y devuelve fideid -> flag (o None)."""
    out: dict[int, str | None] = {}
    with extracted_xml_from_zip_url(url) as xml_path:
        for row in parse_players_xml_path(xml_path):
            fid = int(row["fideid"])
            fl = row.get("flag")
            if fl is not None and str(fl).strip() == "":
                fl = None
            out[fid] = str(fl).strip() if fl else None
    return out


def _batch_update_flags(session: Any, column: str, mapping: dict[int, str | None]) -> int:
    """Actualiza una columna flag_* con UPDATE FROM unnest."""
    if column not in ALLOWED_FLAG_COLUMNS:
        raise ValueError(f"columna no permitida: {column}")
    if not mapping:
        return 0
    pairs = list(mapping.items())
    chunk_size = 8000
    total = 0
    for i in range(0, len(pairs), chunk_size):
        chunk = pairs[i : i + chunk_size]
        fids = [x[0] for x in chunk]
        flags = [x[1] for x in chunk]
        session.execute(
            text(
                f"""
                UPDATE fide.players AS p
                SET {column} = v.flag
                FROM unnest(CAST(:fids AS int[]), CAST(:flags AS varchar[])) AS v(fid, flag)
                WHERE p.fideid = v.fid
                """
            ),
            {"fids": fids, "flags": flags},
        )
        total += len(chunk)
    return total


def run_import_modality_flags(period: str | None = None) -> dict:
    """
    Descarga los tres XML de archivo FIDE (standard, rapid, blitz) y actualiza flag_std, flag_rpd, flag_blz.

    No modifica ratings ni `flag` legado. Si period es None, usa MAX(period) de fide.player_rating_history.
    """
    engine = get_engine()
    init_db(engine)
    period_str = _resolve_period(engine, period)
    urls = discover_period_archive_xml_zip_urls(period_str)
    logger.info("Flags por modalidad: period=%s urls=%s", period_str, urls)

    kind_to_column = {"standard": "flag_std", "rapid": "flag_rpd", "blitz": "flag_blz"}
    stats: dict[str, object] = {"period": period_str}

    with get_db_session() as session:
        for kind, col in kind_to_column.items():
            url = urls[kind]
            logger.info("Parseando %s -> %s", kind, url)
            mapping = _collect_flags_from_zip(url)
            n = _batch_update_flags(session, col, mapping)
            stats[f"{kind}_players"] = len(mapping)
            stats[f"{kind}_rows_updated"] = n

    logger.info("Import modality flags completado: %s", stats)
    return stats
