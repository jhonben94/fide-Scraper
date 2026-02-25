"""Cálculo de rankings mundial, nacional y continental."""

import json
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.models import Player

# Cargar mapeo país -> continente
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
with open(_DATA_DIR / "country_continent.json", encoding="utf-8") as f:
    COUNTRY_CONTINENT = json.load(f)


def _is_active():
    """Condición para jugadores activos (sin flag de inactividad)."""
    return or_(Player.flag.is_(None), Player.flag == "")


def _rated():
    """Condición para jugadores con rating > 0."""
    return Player.rating > 0


def _count_better_ranked(session: Session, rating: int | None, country: str | None = None, continent: str | None = None, active_only: bool = False) -> int:
    """Cuenta jugadores con rating estrictamente mayor al dado."""
    if rating is None or rating <= 0:
        return 0

    stmt = select(func.count()).select_from(Player).where(
        Player.rating > rating,
        _rated(),
    )
    if country:
        stmt = stmt.where(Player.country == country)
    if continent:
        stmt = stmt.where(Player.country.in_(c for c, cont in COUNTRY_CONTINENT.items() if cont == continent))
    if active_only:
        stmt = stmt.where(_is_active())

    return session.scalar(stmt) or 0


def _count_total(session: Session, country: str | None = None, continent: str | None = None, active_only: bool = False) -> int:
    """Cuenta total de jugadores con rating > 0 en el ámbito dado."""
    stmt = select(func.count()).select_from(Player).where(_rated())
    if country:
        stmt = stmt.where(Player.country == country)
    if continent:
        stmt = stmt.where(Player.country.in_(c for c, cont in COUNTRY_CONTINENT.items() if cont == continent))
    if active_only:
        stmt = stmt.where(_is_active())

    return session.scalar(stmt) or 0


def get_player_rankings(session: Session, player: Player) -> dict:
    """
    Calcula los rankings mundial, nacional y continental para un jugador.

    Returns:
        dict con estructura:
        {
            "world": {"rank_active": N, "rank_all": N, "total_active": N, "total_all": N},
            "national": {...},
            "continent": {...}
        }
    """
    rating = player.rating or 0
    country = player.country
    continent = COUNTRY_CONTINENT.get(country, "Unknown")

    def _ranks(scope_country: str | None, scope_continent: str | None) -> dict:
        rank_active = 1 + _count_better_ranked(session, rating, scope_country, scope_continent, active_only=True)
        rank_all = 1 + _count_better_ranked(session, rating, scope_country, scope_continent, active_only=False)
        total_active = _count_total(session, scope_country, scope_continent, active_only=True)
        total_all = _count_total(session, scope_country, scope_continent, active_only=False)
        return {
            "rank_active": rank_active,
            "rank_all": rank_all,
            "total_active": total_active,
            "total_all": total_all,
        }

    return {
        "world": _ranks(None, None),
        "national": _ranks(country, None),
        "continent": _ranks(None, continent) if continent != "Unknown" else {"rank_active": None, "rank_all": None, "total_active": None, "total_all": None},
    }
