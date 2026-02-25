"""Descarga de datos XML oficiales desde FIDE."""

import io
import logging
import zipfile

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)


def download_fide_xml(period: str | None = None) -> bytes:
    """
    Descarga el archivo ZIP de FIDE y retorna el contenido XML descomprimido.

    Args:
        period: Fecha opcional en formato YYYY-MM-DD para listas históricas.

    Returns:
        Contenido del archivo XML como bytes.

    Raises:
        httpx.HTTPError: Si la descarga falla.
        zipfile.BadZipFile: Si el archivo descargado no es un ZIP válido.
    """
    settings = get_settings()
    url = settings.fide_xml_url
    if period:
        url = f"{url}?period={period}" if "?" not in url else f"{url}&period={period}"

    logger.info("Descargando datos FIDE desde %s", url)

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    zip_content = response.content
    logger.info("Descargado %d bytes, descomprimiendo...", len(zip_content))

    with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zf:
        # El ZIP puede contener players_list_xml_foa.xml o similar
        xml_names = [n for n in zf.namelist() if n.endswith(".xml")]
        if not xml_names:
            raise ValueError("No se encontró archivo XML en el ZIP")
        xml_name = xml_names[0]
        xml_content = zf.read(xml_name)

    logger.info("XML extraído: %s (%d bytes)", xml_name, len(xml_content))
    return xml_content
