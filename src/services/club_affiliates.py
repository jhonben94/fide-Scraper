"""FIDE IDs de jugadores con club asignado en la base principal (ClubSync)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def load_affiliated_fideids(session: Session) -> frozenset[int]:
    """Obtiene FIDE IDs de jugadores con club asignado en la tabla `player` de ClubSync.

    Usado para incluir, junto a un filtro por país (ej. PAR), a extranjeros afiliados a un
    club local que de otro modo quedarían afuera del filtro de federación.
    """
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
