"""Importación de historial de ratings para Progress."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterator
from datetime import date, datetime, timezone
from typing import Literal, Optional

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.database import get_db_session, get_engine, init_db
from src.downloader import discover_period_archive_xml_zip_urls, extracted_xml_from_zip_url
from src.models import HistoryImportCheckpoint, PlayerRatingHistory
from src.parser import parse_players_xml_path

logger = logging.getLogger(__name__)

BATCH_SIZE = 5000

PeriodScope = Literal["rolling_months", "current_year"]

# Las listas RPD/BLZ de FIDE usan el tag <rating> para su modalidad; se mapean a columnas distintas.
_HISTORY_KIND_ORDER: tuple[tuple[str, Callable[[dict], dict]], ...] = (
    (
        "standard",
        lambda p: {
            "fideid": p["fideid"],
            "rating": p.get("rating"),
            "rapid_rating": None,
            "blitz_rating": None,
        },
    ),
    (
        "rapid",
        lambda p: {
            "fideid": p["fideid"],
            "rating": None,
            "rapid_rating": p.get("rating"),
            "blitz_rating": None,
        },
    ),
    (
        "blitz",
        lambda p: {
            "fideid": p["fideid"],
            "rating": None,
            "rapid_rating": None,
            "blitz_rating": p.get("rating"),
        },
    ),
)


def _batch_upsert_history(session: Session, batch: list[dict], period: date) -> int:
    """Inserta o actualiza un batch en player_rating_history (upsert por fideid+period)."""
    if not batch:
        return 0

    tbl = PlayerRatingHistory.__table__
    stmt = pg_insert(PlayerRatingHistory).values(
        [
            {
                "fideid": p["fideid"],
                "period": period,
                "rating": p.get("rating"),
                "rapid_rating": p.get("rapid_rating"),
                "blitz_rating": p.get("blitz_rating"),
            }
            for p in batch
        ]
    )
    # Tres importaciones seguidas (STD / RPD / BLZ); NULL en EXCLUDED no debe borrar lo ya guardado.
    stmt = stmt.on_conflict_do_update(
        index_elements=["fideid", "period"],
        set_={
            "rating": func.coalesce(stmt.excluded.rating, tbl.c.rating),
            "rapid_rating": func.coalesce(stmt.excluded.rapid_rating, tbl.c.rapid_rating),
            "blitz_rating": func.coalesce(stmt.excluded.blitz_rating, tbl.c.blitz_rating),
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


def _month_periods(months: int) -> list[date]:
    """Genera fechas (primer día del mes) para los últimos N meses."""
    today = date.today()
    periods: list[date] = []
    for i in range(months):
        # Primer día del mes hace i meses
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        periods.append(date(year, month, 1))
    return periods


def _periods_current_year(today: Optional[date] = None) -> list[date]:
    """Primer día de cada mes desde enero del año en curso hasta el mes actual (inclusive)."""
    today = today or date.today()
    periods: list[date] = []
    d = date(today.year, 1, 1)
    end = date(today.year, today.month, 1)
    while d <= end:
        periods.append(d)
        if d.month == 12:
            d = date(d.year + 1, 1, 1)
        else:
            d = date(d.year, d.month + 1, 1)
    return periods


def _normalize_country_codes(codes: frozenset[str] | None) -> frozenset[str] | None:
    if not codes:
        return None
    out = frozenset(c.strip().upper() for c in codes if c and str(c).strip())
    return out or None


def _normalize_fide_ids(ids: frozenset[int] | None) -> frozenset[int] | None:
    if not ids:
        return None
    out = frozenset(int(i) for i in ids if i is not None)
    return out or None


def _fide_list_filter_key(fide_ids: frozenset[int]) -> str:
    """Clave estable para checkpoint (mismo conjunto → misma clave). ~70 chars."""
    canonical = ",".join(str(i) for i in sorted(fide_ids))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"fides:{digest}"


def _history_filter_key(codes: frozenset[str] | None, include_club_affiliates: bool) -> str:
    parts: list[str] = []
    if codes:
        parts.append(",".join(sorted(codes)))
    if include_club_affiliates:
        parts.append("club_affiliates")
    return "|".join(parts)


def _build_filter_key(
    codes: frozenset[str] | None,
    include_club_affiliates: bool,
    fide_ids: frozenset[int] | None,
) -> str:
    if fide_ids:
        return _fide_list_filter_key(fide_ids)
    return _history_filter_key(codes, include_club_affiliates)


def _load_affiliated_fideids(session: Session) -> frozenset[int]:
    """Obtiene FIDE IDs de jugadores con club asignado en la base principal."""
    rows = session.execute(
        text(
            """
            SELECT DISTINCT CAST(p.fide_id AS INTEGER) AS fideid
            FROM player p
            WHERE p.current_club_id IS NOT NULL
              AND p.fide_id IS NOT NULL
              AND p.fide_id ~ '^[0-9]+$'
            """
        )
    )
    return frozenset(int(r[0]) for r in rows)


def _completed_periods(session: Session, period_scope: str, filter_key: str) -> set[date]:
    stmt = select(HistoryImportCheckpoint.period).where(
        HistoryImportCheckpoint.period_scope == period_scope,
        HistoryImportCheckpoint.country_filter == filter_key,
    )
    return {row[0] for row in session.execute(stmt)}


def _upsert_checkpoint(
    session: Session,
    *,
    period: date,
    period_scope: str,
    filter_key: str,
    rows_parsed: int,
    rows_upserted: int,
) -> None:
    now = datetime.now(timezone.utc)
    tbl = HistoryImportCheckpoint.__table__
    stmt = pg_insert(tbl).values(
        period=period,
        country_filter=filter_key,
        period_scope=period_scope,
        rows_parsed=rows_parsed,
        rows_upserted=rows_upserted,
        finished_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_fide_history_import_checkpoint",
        set_={
            "rows_parsed": stmt.excluded.rows_parsed,
            "rows_upserted": stmt.excluded.rows_upserted,
            "finished_at": stmt.excluded.finished_at,
        },
    )
    session.execute(stmt)


def run_import_history(
    months: int = 24,
    *,
    period_scope: PeriodScope = "rolling_months",
    country_codes: frozenset[str] | None = None,
    include_club_affiliates: bool = False,
    skip_completed: bool = False,
    fide_ids: frozenset[int] | None = None,
) -> dict:
    """
    Importa historial de ratings.

    Descarga el XML de cada periodo y guarda snapshots en player_rating_history.

    Args:
        months: En modo ``rolling_months``, meses hacia atrás desde hoy (primer día de cada mes).
        period_scope: ``rolling_months`` o ``current_year`` (solo meses del año calendario en curso).
        country_codes: Si se define (p. ej. ``frozenset({"PAR"})``), solo se persisten esas federaciones
            (código FIDE a mayúsculas). El XML completo se sigue parseando en streaming.
            Ignorado si ``fide_ids`` no está vacío.
        include_club_affiliates: Incluye también jugadores con club asignado en tabla local ``player``
            (filtro OR con ``country_codes``). Ignorado si ``fide_ids`` no está vacío.
        skip_completed: Si es True, omite periodos ya registrados en ``fide.history_import_checkpoint``.
        fide_ids: Si se define y no está vacío, solo se persisten estos FIDE ID (clave de checkpoint por hash
            estable del conjunto ordenado).

    Returns:
        dict con total_periods, total_records (upserts), total_rows_parsed, periods_imported,
        period_scope, country_codes, periods_skipped (opcional), fide_ids_mode, fide_id_count, filter_key.
    """
    fid = _normalize_fide_ids(fide_ids)
    codes = None if fid else _normalize_country_codes(country_codes)
    include_club = False if fid else include_club_affiliates
    filter_key = _build_filter_key(codes, include_club, fid)
    if period_scope == "current_year":
        periods = _periods_current_year()
        logger.info(
            "Iniciando importación de historial (año en curso: %d periodos, año %d)",
            len(periods),
            date.today().year,
        )
    else:
        periods = _month_periods(months)
        logger.info("Iniciando importación de historial (%d meses, rolling)", months)
    if fid:
        logger.info("Modo listado FIDE ID: %d identidades (filter_key=%s)", len(fid), filter_key)
    else:
        if codes:
            logger.info("Filtro federación: %s", ",".join(sorted(codes)))
        if include_club:
            logger.info("Filtro adicional habilitado: jugadores afiliados a club")

    periods_planned = list(periods)
    engine = get_engine()
    init_db(engine)

    total_records = 0
    total_rows_parsed = 0
    periods_skipped: list[str] = []

    with get_db_session() as session:
        affiliated_fideids: frozenset[int] = frozenset()
        if include_club and not fid:
            affiliated_fideids = _load_affiliated_fideids(session)
            logger.info("Jugadores afiliados a club detectados: %d", len(affiliated_fideids))

        working = list(periods_planned)
        if skip_completed:
            done = _completed_periods(session, period_scope, filter_key)
            periods_skipped = [p.strftime("%Y-%m-%d") for p in working if p in done]
            working = [p for p in working if p not in done]
            if periods_skipped:
                logger.info(
                    "Omitiendo %d periodo(s) ya en history_import_checkpoint (%s / %s): %s",
                    len(periods_skipped),
                    period_scope,
                    filter_key or "(sin filtro país)",
                    ", ".join(periods_skipped),
                )

        for period in working:
            period_str = period.strftime("%Y-%m-%d")
            period_parsed = 0
            period_upserted = 0
            try:
                zip_urls = discover_period_archive_xml_zip_urls(period_str)
                for kind, row_fn in _HISTORY_KIND_ORDER:
                    zip_url = zip_urls[kind]
                    with extracted_xml_from_zip_url(zip_url) as xml_path:
                        for batch in _batched(parse_players_xml_path(xml_path), BATCH_SIZE):
                            period_parsed += len(batch)
                            total_rows_parsed += len(batch)
                            if fid:
                                batch = [p for p in batch if int(p.get("fideid", 0)) in fid]
                            elif codes or include_club:
                                batch = [
                                    p
                                    for p in batch
                                    if (
                                        (codes and (p.get("country") or "").strip().upper() in codes)
                                        or (
                                            include_club
                                            and int(p.get("fideid", 0)) in affiliated_fideids
                                        )
                                    )
                                ]
                            if not batch:
                                continue
                            mapped = [row_fn(p) for p in batch]
                            _batch_upsert_history(session, mapped, period)
                            n = len(mapped)
                            period_upserted += n
                            total_records += n
                    logger.debug("Periodo %s %s: ZIP %s", period_str, kind, zip_url)
                logger.info(
                    "Periodo %s: %d filas parseadas, %d upsert (std+rpd+blz)",
                    period_str,
                    period_parsed,
                    period_upserted,
                )
                _upsert_checkpoint(
                    session,
                    period=period,
                    period_scope=period_scope,
                    filter_key=filter_key,
                    rows_parsed=period_parsed,
                    rows_upserted=period_upserted,
                )
            except Exception as e:
                logger.warning("Error en periodo %s: %s", period_str, e)

    return {
        "total_periods": len(working),
        "periods_requested": len(periods_planned),
        "total_records": total_records,
        "total_rows_parsed": total_rows_parsed,
        "periods_imported": [p.strftime("%Y-%m-%d") for p in working],
        "periods_skipped": periods_skipped,
        "period_scope": period_scope,
        "country_codes": sorted(codes) if codes else None,
        "include_club_affiliates": include_club,
        "fide_ids_mode": bool(fid),
        "fide_id_count": len(fid) if fid else None,
        "filter_key": filter_key,
    }
