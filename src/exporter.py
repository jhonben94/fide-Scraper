"""Exportación de datos de jugadores a JSON y CSV."""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from src.config import get_settings

logger = logging.getLogger(__name__)


def _ensure_export_path() -> Path:
    """Asegura que el directorio de exportación existe."""
    settings = get_settings()
    path = Path(str(settings.export_path))
    path.mkdir(parents=True, exist_ok=True)
    return path


def export_to_json(players: list[dict], filename: str | None = None) -> Path:
    """
    Exporta jugadores a un archivo JSON.

    Args:
        players: Lista de diccionarios con datos de jugadores.
        filename: Nombre del archivo. Si no se especifica, usa timestamp.

    Returns:
        Ruta del archivo creado.
    """
    export_dir = _ensure_export_path()
    if not filename:
        filename = f"players_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = export_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(players, f, ensure_ascii=False, indent=2)

    logger.info("Exportados %d jugadores a %s", len(players), filepath)
    return filepath


def export_to_csv(players: list[dict], filename: str | None = None) -> Path:
    """
    Exporta jugadores a un archivo CSV.

    Args:
        players: Lista de diccionarios con datos de jugadores.
        filename: Nombre del archivo. Si no se especifica, usa timestamp.

    Returns:
        Ruta del archivo creado.
    """
    if not players:
        raise ValueError("No hay jugadores para exportar")

    export_dir = _ensure_export_path()
    if not filename:
        filename = f"players_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = export_dir / filename

    fieldnames = list(players[0].keys())

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(players)

    logger.info("Exportados %d jugadores a %s", len(players), filepath)
    return filepath


def export_by_country(players: list[dict]) -> dict[str, Path]:
    """
    Exporta jugadores agrupados por país a archivos JSON separados.

    Returns:
        Diccionario {código_país: ruta_archivo}
    """
    by_country: dict[str, list[dict]] = {}
    for p in players:
        country = p.get("country", "UNK") or "UNK"
        if country not in by_country:
            by_country[country] = []
        by_country[country].append(p)

    export_dir = _ensure_export_path()
    country_dir = export_dir / "by_country"
    country_dir.mkdir(exist_ok=True)

    result: dict[str, Path] = {}
    for country, plist in by_country.items():
        filepath = country_dir / f"{country}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(plist, f, ensure_ascii=False, indent=2)
        result[country] = filepath

    logger.info("Exportados %d países a %s", len(result), country_dir)
    return result
