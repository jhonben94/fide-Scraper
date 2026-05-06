"""Parseo del XML de jugadores FIDE (streaming con iterparse)."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO


def _local_tag(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _parse_int(value: str | None) -> int | None:
    """Convierte string a int, retorna None si vacío o inválido."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _get_text(element: ET.Element, tag: str) -> str | None:
    """Obtiene el texto de un subelemento, retorna None si no existe."""
    child = element.find(tag)
    if child is None:
        for c in element:
            local_tag = _local_tag(c.tag)
            if local_tag == tag:
                return c.text.strip() if c.text else None
        return None
    return child.text.strip() if child.text else None


def _first_text(element: ET.Element, *tags: str) -> str | None:
    """Primer subelemento no vacío entre varios nombres (leyendas FIDE distintas por tipo de lista)."""
    for tag in tags:
        v = _get_text(element, tag)
        if v is not None and str(v).strip() != "":
            return v
    return None


def _parse_player_element(elem: ET.Element) -> dict | None:
    """Extrae los datos de un elemento player."""
    fideid = _parse_int(_get_text(elem, "fideid"))
    if fideid is None:
        return None

    return {
        "fideid": fideid,
        "name": _get_text(elem, "name") or "",
        "country": _get_text(elem, "country") or "",
        "sex": _get_text(elem, "sex"),
        "title": _get_text(elem, "title") or _get_text(elem, "titl"),
        "rating": _parse_int(_first_text(elem, "rating", "srtng")),
        "games": _parse_int(_first_text(elem, "games", "sgm")),
        "rapid_rating": _parse_int(_first_text(elem, "rapid_rating", "rrtng")),
        "rapid_games": _parse_int(_first_text(elem, "rapid_games", "rgm")),
        "blitz_rating": _parse_int(_first_text(elem, "blitz_rating", "brtng")),
        "blitz_games": _parse_int(_first_text(elem, "blitz_games", "bgm")),
        "birthday": _parse_int(_get_text(elem, "birthday")),
        "flag": _get_text(elem, "flag"),
        "foa_title": _get_text(elem, "foa_title"),
        "foa_rating": _parse_int(_get_text(elem, "foa_rating")),
    }


def parse_players_xml_stream(source: str | Path | BinaryIO) -> Iterator[dict]:
    """
    Parsea jugadores con iterparse (evento end en <player>) y libera memoria tras cada fila.

    `source` puede ser ruta a archivo XML, pathlib.Path, o objeto binario legible (p. ej. BytesIO).
    """
    # Solo procesar y limpiar en `end` de `<player>`: limpiar hijos antes rompe el árbol.
    for _event, elem in ET.iterparse(source, events=("end",)):
        if _local_tag(elem.tag) != "player":
            continue
        player = _parse_player_element(elem)
        if player:
            yield player
        elem.clear()


def parse_players_xml(xml_content: bytes) -> Iterator[dict]:
    """
    Parsea XML en memoria usando streaming (no carga el árbol completo).

    Para archivos grandes preferir parse_players_xml_stream sobre un path tras extraer el ZIP a disco.
    """
    return parse_players_xml_stream(io.BytesIO(xml_content))


def parse_players_xml_path(path: str | Path) -> Iterator[dict]:
    """Parsea desde ruta de archivo XML en disco."""
    return parse_players_xml_stream(path)
