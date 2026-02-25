"""Rutas de la API REST."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db_session
from src.models import Player
from src.scrapers.fide_stats import fetch_player_stats
from src.services.calculations import get_calculation_example
from src.services.progress import get_player_progress
from src.services.rankings import get_player_rankings

router = APIRouter(prefix="/players", tags=["players"])


def get_db():
    """Dependency para obtener sesión de DB."""
    with get_db_session() as session:
        yield session


@router.get("", response_model=dict)
def list_players(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    country: str | None = Query(None, min_length=2, max_length=3),
    min_rating: int | None = Query(None, ge=0, le=3000),
    session: Session = Depends(get_db),
):
    """
    Lista jugadores con paginación y filtros opcionales.

    - **skip**: Jugadores a saltar (paginación)
    - **limit**: Máximo jugadores a retornar (1-500)
    - **country**: Filtrar por código de federación (ej: ESP, USA)
    - **min_rating**: Filtrar por rating mínimo
    """
    stmt = select(Player)
    if country:
        stmt = stmt.where(Player.country == country.upper())
    if min_rating is not None:
        stmt = stmt.where(Player.rating >= min_rating)
    stmt = stmt.order_by(Player.rating.desc().nullslast(), Player.fideid)
    stmt = stmt.offset(skip).limit(limit)

    players = list(session.scalars(stmt).all())
    return {
        "total": len(players),
        "skip": skip,
        "limit": limit,
        "players": [p.to_dict() for p in players],
    }


@router.get("/{fideid}", response_model=dict)
def get_player(fideid: int, session: Session = Depends(get_db)):
    """
    Obtiene un jugador por su ID FIDE con perfil completo.

    Incluye datos personales, ratings (standard/rapid/blitz), títulos (FIDE, FOA)
    y rankings (mundial, nacional, continental) para activos y todos.
    """
    stmt = select(Player).where(Player.fideid == fideid)
    player = session.scalar(stmt)
    if not player:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    result = player.to_dict()
    result["rankings"] = get_player_rankings(session, player)
    return result


@router.get("/{fideid}/calculations", response_model=dict)
def get_player_calculations(
    fideid: int,
    opponent_rating: int = Query(1800, ge=1000, le=3000, description="Rating del oponente para el ejemplo"),
    session: Session = Depends(get_db),
):
    """
    Ejemplo de cálculo de rating FIDE para un jugador.

    Muestra puntuación esperada, K-factor y cambio de rating para victoria/tablas/derrota
    contra un oponente con el rating indicado.
    """
    stmt = select(Player).where(Player.fideid == fideid)
    player = session.scalar(stmt)
    if not player:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    rating = player.rating or 1500  # fallback si no tiene rating
    example = get_calculation_example(
        player_rating=rating,
        opponent_rating=opponent_rating,
        games=player.games,
        birthday=player.birthday,
    )
    return {"player": player.to_dict(), "calculation": example}


@router.get("/{fideid}/progress", response_model=dict)
def get_player_progress_endpoint(
    fideid: int,
    months: int = Query(24, ge=1, le=120, description="Meses de historial a retornar"),
    session: Session = Depends(get_db),
):
    """
    Evolución del rating en el tiempo (Standard, Rapid, Blitz).

    Requiere haber ejecutado el import de historial: python -m scripts.run_import_history
    """
    stmt = select(Player).where(Player.fideid == fideid)
    player = session.scalar(stmt)
    if not player:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    history = get_player_progress(session, fideid, months)
    return {"player": player.to_dict(), "progress": history}


@router.get("/{fideid}/stats", response_model=dict)
def get_player_stats_endpoint(fideid: int, session: Session = Depends(get_db)):
    """
    Estadísticas W/D/L por color (Total, Standard, Rapid, Blitz).

    Obtiene datos desde la API interna de FIDE (ratings.fide.com).
    """
    stmt = select(Player).where(Player.fideid == fideid)
    player = session.scalar(stmt)
    if not player:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    stats = fetch_player_stats(fideid)
    if stats is None:
        raise HTTPException(
            status_code=503,
            detail="No se pudieron obtener estadísticas de FIDE. El jugador puede no tener partidas registradas.",
        )
    return {"player": player.to_dict(), "stats": stats}
