"""Cálculos de rating FIDE según reglamento oficial.

Fórmulas basadas en FIDE Rating Regulations (Handbook).
- Expected score: E(Ra, Rb) = 1 / (1 + 10^((Rb-Ra)/400))
- K-factor: 40 (nuevos/<18 y <2300), 20 (<2400), 10 (>=2400 y >=30 partidas)
- Cambio: ΔR = K × (Score - ExpectedScore)
"""

import math
from datetime import date


def expected_score(player_rating: int, opponent_rating: int) -> float:
    """
    Puntuación esperada del jugador contra un oponente.

    Args:
        player_rating: Rating del jugador (Ra)
        opponent_rating: Rating del oponente (Rb)

    Returns:
        Valor entre 0 y 1 (ej. 0.5 = empate esperado)
    """
    diff = opponent_rating - player_rating
    return 1.0 / (1.0 + math.pow(10, diff / 400.0))


def k_factor(
    rating: int,
    games: int | None = 0,
    birthday: int | None = None,
) -> int:
    """
    K-factor según reglamento FIDE.

    Args:
        rating: Rating actual del jugador
        games: Número de partidas estándar jugadas (total histórico)
        birthday: Año de nacimiento (para jugadores < 18)

    Returns:
        K = 40, 20 o 10
    """
    games = games or 0
    is_under_18 = False
    if birthday:
        current_year = date.today().year
        is_under_18 = (current_year - birthday) < 18

    # K=40: nuevos (<30 partidas) o <18 con rating < 2300
    if games < 30:
        return 40
    if is_under_18 and rating < 2300:
        return 40

    # K=10: rating >= 2400 con >= 30 partidas
    if rating >= 2400:
        return 10

    # K=20: rating < 2400 con >= 30 partidas
    return 20


def rating_change(
    player_rating: int,
    opponent_rating: int,
    score: float,
    games: int | None = None,
    birthday: int | None = None,
) -> float:
    """
    Cambio de rating para una partida (ΔR = K × (Score - E)).

    Args:
        player_rating: Rating del jugador antes de la partida
        opponent_rating: Rating del oponente
        score: Puntuación obtenida (1=victoria, 0.5=tablas, 0=derrota)
        games: Partidas jugadas antes de esta (para K-factor)
        birthday: Año de nacimiento (para K-factor)

    Returns:
        Cambio de rating (puede ser negativo)
    """
    e = expected_score(player_rating, opponent_rating)
    k = k_factor(player_rating, games, birthday)
    return k * (score - e)


def get_calculation_example(
    player_rating: int,
    opponent_rating: int,
    games: int | None = None,
    birthday: int | None = None,
) -> dict:
    """
    Genera un ejemplo de cálculo para mostrar en la API.

    Returns:
        dict con expected_score, k_factor, rating_changes para win/draw/loss
    """
    e = expected_score(player_rating, opponent_rating)
    k = k_factor(player_rating, games, birthday)

    return {
        "player_rating": player_rating,
        "opponent_rating": opponent_rating,
        "expected_score": round(e, 4),
        "k_factor": k,
        "rating_changes": {
            "win": round(rating_change(player_rating, opponent_rating, 1.0, games, birthday), 2),
            "draw": round(rating_change(player_rating, opponent_rating, 0.5, games, birthday), 2),
            "loss": round(rating_change(player_rating, opponent_rating, 0.0, games, birthday), 2),
        },
    }
