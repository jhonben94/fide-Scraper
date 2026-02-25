"""Servicio para obtener historial de rating (Progress)."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import PlayerRatingHistory


def get_player_progress(
    session: Session,
    fideid: int,
    months: int = 24,
) -> list[dict]:
    """
    Obtiene la serie temporal de ratings para un jugador.

    Args:
        session: Sesión de DB
        fideid: ID FIDE del jugador
        months: Número de meses hacia atrás

    Returns:
        Lista ordenada por periodo de dicts con period, rating, rapid_rating, blitz_rating
    """
    cutoff = date.today() - timedelta(days=months * 31)  # aprox

    stmt = (
        select(PlayerRatingHistory)
        .where(
            PlayerRatingHistory.fideid == fideid,
            PlayerRatingHistory.period >= cutoff,
        )
        .order_by(PlayerRatingHistory.period.asc())
    )
    rows = session.scalars(stmt).all()

    return [
        {
            "period": r.period.isoformat(),
            "rating": r.rating,
            "rapid_rating": r.rapid_rating,
            "blitz_rating": r.blitz_rating,
        }
        for r in rows
    ]
