"""Parseo del XML de jugadores FIDE."""

import io
import xml.etree.ElementTree as ET
from typing import Iterator


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
    # FIDE puede usar namespaces: buscar con y sin namespace
    child = element.find(tag)
    if child is None:
        # Intentar por nombre local (tag puede ser {ns}localname)
        for c in element:
            local_tag = c.tag.split("}")[-1] if "}" in c.tag else c.tag
            if local_tag == tag:
                return c.text.strip() if c.text else None
        return None
    return child.text.strip() if child.text else None


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
        "title": _get_text(elem, "title"),
        "rating": _parse_int(_get_text(elem, "rating")),
        "games": _parse_int(_get_text(elem, "games")),
        "rapid_rating": _parse_int(_get_text(elem, "rapid_rating")),
        "rapid_games": _parse_int(_get_text(elem, "rapid_games")),
        "blitz_rating": _parse_int(_get_text(elem, "blitz_rating")),
        "blitz_games": _parse_int(_get_text(elem, "blitz_games")),
        "birthday": _parse_int(_get_text(elem, "birthday")),
        "flag": _get_text(elem, "flag"),
        "foa_title": _get_text(elem, "foa_title"),
        "foa_rating": _parse_int(_get_text(elem, "foa_rating")),
    }


def parse_players_xml(xml_content: bytes) -> Iterator[dict]:
    """
    Parsea el XML de jugadores FIDE y genera diccionarios por jugador.

    Usa ET.parse() para cargar el árbol completo. Busca todos los <player>
    en el árbol (soporta namespaces y estructura anidada).
    """
    tree = ET.parse(io.BytesIO(xml_content))
    root = tree.getroot()

    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "player":
            player = _parse_player_element(elem)
            if player:
                yield player
