"""Cliente para la API de estadísticas FIDE (W/D/L por color).

La API interna de FIDE expone datos en /a_data_stats.php.
No es documentada oficialmente; usar con moderación.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FIDE_STATS_URL = "https://ratings.fide.com/a_data_stats.php"


def _parse_int(val: Any) -> int:
    """Convierte a int de forma segura."""
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def fetch_player_stats(fideid: int) -> dict | None:
    """
    Obtiene estadísticas W/D/L por color desde la API de FIDE.

    Args:
        fideid: ID FIDE del jugador

    Returns:
        dict con total_games, standard_games, rapid_games, blitz_games,
        cada uno con white/black y wins, draws, losses. None si falla.
    """
    url = f"{FIDE_STATS_URL}?id1={fideid}&id2=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; FIDE-Scraper/1.0)",
        "Referer": f"https://ratings.fide.com/profile/{fideid}/statistics",
        "Accept": "application/json, text/javascript, */*",
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.post(url, headers=headers, data="")
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.warning("Error fetching FIDE stats for %s: %s", fideid, e)
        return None

    if not data or not isinstance(data, list) or not data:
        return None

    row = data[0]
    if not isinstance(row, dict):
        return None

    def _color_stats(total_key: str, win_key: str, draw_key: str) -> dict:
        total = _parse_int(row.get(total_key))
        wins = _parse_int(row.get(win_key))
        draws = _parse_int(row.get(draw_key))
        losses = max(0, total - wins - draws) if total else 0
        return {"total": total, "wins": wins, "draws": draws, "losses": losses}

    return {
        "total_games": {
            "white": _color_stats("white_total", "white_win_num", "white_draw_num"),
            "black": _color_stats("black_total", "black_win_num", "black_draw_num"),
        },
        "standard_games": {
            "white": _color_stats("white_total_std", "white_win_num_std", "white_draw_num_std"),
            "black": _color_stats("black_total_std", "black_win_num_std", "black_draw_num_std"),
        },
        "rapid_games": {
            "white": _color_stats("white_total_rpd", "white_win_num_rpd", "white_draw_num_rpd"),
            "black": _color_stats("black_total_rpd", "black_win_num_rpd", "black_draw_num_rpd"),
        },
        "blitz_games": {
            "white": _color_stats("white_total_blz", "white_win_num_blz", "white_draw_num_blz"),
            "black": _color_stats("black_total_blz", "black_win_num_blz", "black_draw_num_blz"),
        },
    }
