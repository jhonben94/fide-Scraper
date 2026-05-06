"""Descarga de datos XML oficiales desde FIDE (streaming a disco)."""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

CHUNK = 1024 * 1024

# Página de archivo oficial: enlaces por periodo (STD/RPD/BLZ en ZIPs distintos).
# `players_list_xml.zip?period=` devuelve el mismo listado actual; no sirve para historial.
FIDE_ARCHIVE_DOWNLOAD_PAGE = "https://ratings.fide.com/a_download.php"


def discover_period_archive_xml_zip_urls(period: str) -> dict[str, str]:
    """
    Obtiene las URLs de los ZIP XML (standard / rapid / blitz) para un periodo de lista FIDE.

    Args:
        period: Fecha del primer día del mes, formato ``YYYY-MM-DD`` (ej. ``2024-05-01``).

    Returns:
        Diccionario con claves ``standard``, ``rapid``, ``blitz`` y URL completa a cada ZIP.
    """
    url = f"{FIDE_ARCHIVE_DOWNLOAD_PAGE}?period={period}"
    logger.info("Resolviendo enlaces de archivo FIDE: %s", url)
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        html = response.text
    found: dict[str, str] = {}
    for match in re.finditer(
        r"https://ratings\.fide\.com/download/(standard|rapid|blitz)_\w+_xml\.zip",
        html,
        flags=re.IGNORECASE,
    ):
        kind = match.group(1).lower()
        if kind not in found:
            found[kind] = match.group(0)
    required = ("standard", "rapid", "blitz")
    missing = [k for k in required if k not in found]
    if missing:
        raise ValueError(
            f"No se encontraron enlaces XML de archivo para period={period}; faltan: {missing}"
        )
    return {k: found[k] for k in required}


def _build_url(period: str | None) -> str:
    settings = get_settings()
    url = settings.fide_xml_url
    if period:
        url = f"{url}?period={period}" if "?" not in url else f"{url}&period={period}"
    return url


def _stream_download_to_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(dest, "wb") as out:
                for chunk in response.iter_bytes(chunk_size=CHUNK):
                    if chunk:
                        out.write(chunk)
    logger.info("ZIP guardado en disco: %s (%d bytes)", dest, dest.stat().st_size)


def _pick_xml_entry(xml_names: list[str]) -> str:
    """
    El ZIP combinado suele traer varios XML; evitar elegir al azar `*_foa.xml` si existe la lista principal.
    """
    if not xml_names:
        raise ValueError("Lista de XML vacía")
    lower = {n: n.lower() for n in xml_names}

    def is_foa(n: str) -> bool:
        return "_foa" in lower[n]

    non_foa = [n for n in xml_names if not is_foa(n)]
    pool = non_foa if non_foa else xml_names

    for suffix in ("players_list_xml.xml", "standard_rating_list.xml"):
        for n in pool:
            if lower[n].endswith(suffix):
                return n
    return sorted(pool)[0]


def _extract_first_xml_from_zip(zip_path: Path, xml_path: Path) -> str:
    with zipfile.ZipFile(zip_path, "r") as zf:
        xml_names = [n for n in zf.namelist() if n.endswith(".xml")]
        if not xml_names:
            raise ValueError("No se encontró archivo XML en el ZIP")
        member = _pick_xml_entry(xml_names)
        with zf.open(member) as src, open(xml_path, "wb") as dst:
            shutil.copyfileobj(src, dst, length=CHUNK)
        logger.info("XML extraído a disco: %s (entrada ZIP: %s)", xml_path, member)
        return member


@contextmanager
def extracted_xml_from_zip_url(zip_url: str) -> Iterator[Path]:
    """
    Descarga un ZIP desde una URL absoluta, extrae el XML elegido a un temporal y hace yield de la ruta.
    """
    logger.info("Descargando datos FIDE desde %s", zip_url)

    fd_zip, zip_str = tempfile.mkstemp(suffix=".zip")
    os.close(fd_zip)
    zip_path = Path(zip_str)

    fd_xml, xml_str = tempfile.mkstemp(suffix=".xml")
    os.close(fd_xml)
    xml_path = Path(xml_str)

    try:
        _stream_download_to_file(zip_url, zip_path)
        _extract_first_xml_from_zip(zip_path, xml_path)
        yield xml_path
    finally:
        for p in (xml_path, zip_path):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


@contextmanager
def extracted_xml_tempfile(period: str | None = None) -> Iterator[Path]:
    """
    Descarga el ZIP a un temporal, extrae el primer .xml a otro temporal y hace yield de la ruta XML.

    Al salir del contexto borra ambos archivos.
    """
    url = _build_url(period)
    logger.info("Descargando datos FIDE desde %s", url)

    fd_zip, zip_str = tempfile.mkstemp(suffix=".zip")
    os.close(fd_zip)
    zip_path = Path(zip_str)

    fd_xml, xml_str = tempfile.mkstemp(suffix=".xml")
    os.close(fd_xml)
    xml_path = Path(xml_str)

    try:
        _stream_download_to_file(url, zip_path)
        _extract_first_xml_from_zip(zip_path, xml_path)
        yield xml_path
    finally:
        for p in (xml_path, zip_path):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


def download_fide_xml(period: str | None = None) -> bytes:
    """
    Descarga ZIP y retorna el XML en memoria (legado; listas grandes pueden usar mucha RAM).

    Preferí `extracted_xml_tempfile` + `parse_players_xml_path` en el importador.
    """
    with extracted_xml_tempfile(period=period) as xml_path:
        return xml_path.read_bytes()
