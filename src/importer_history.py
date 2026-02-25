"""Importación de historial de ratings para Progress."""

import logging
from collections.abc import Iterator
from datetime import date, timedelta

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.database import get_db_session, get_engine, init_db
from src.downloader import download_fide_xml
from src.models import PlayerRatingHistory
from src.parser import parse_players_xml

logger = logging.getLogger(__name__)

BATCH_SIZE = 5000


def _batch_upsert_history(session: Session, batch: list[dict], period: date) -> int:
    """Inserta o actualiza un batch en player_rating_history (upsert por fideid+period)."""
    if not batch:
        return 0

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
    stmt = stmt.on_conflict_do_update(
        index_elements=["fideid", "period"],
        set_={
            "rating": stmt.excluded.rating,
            "rapid_rating": stmt.excluded.rapid_rating,
            "blitz_rating": stmt.excluded.blitz_rating,
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


def run_import_history(months: int = 24) -> dict:
    """
    Importa historial de ratings para los últimos N meses.

    Descarga el XML de cada periodo y guarda snapshots en player_rating_history.

    Args:
        months: Número de meses hacia atrás a importar.

    Returns:
        dict con total_periods, total_records, periods_imported.
    """
    logger.info("Iniciando importación de historial (%d meses)", months)

    engine = get_engine()
    init_db(engine)

    periods = _month_periods(months)
    total_records = 0

    with get_db_session() as session:
        for period in periods:
            period_str = period.strftime("%Y-%m-%d")
            try:
                xml_content = download_fide_xml(period=period_str)
                count = 0
                for batch in _batched(parse_players_xml(xml_content), BATCH_SIZE):
                    _batch_upsert_history(session, batch, period)
                    count += len(batch)
                    total_records += len(batch)
                logger.info("Periodo %s: %d registros", period_str, count)
            except Exception as e:
                logger.warning("Error en periodo %s: %s", period_str, e)

    return {
        "total_periods": len(periods),
        "total_records": total_records,
        "periods_imported": [p.strftime("%Y-%m-%d") for p in periods],
    }
