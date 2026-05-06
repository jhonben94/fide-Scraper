"""Dependencias FastAPI."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address
import logging
from typing import List, Optional, Union

from fastapi import Header, HTTPException, Request, status

from src.config import get_settings

logger = logging.getLogger(__name__)
_allowlist_warned = False


async def verify_optional_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    """
    Si `FIDE_SCRAPER_API_KEY` está configurada, exige el mismo valor en `X-API-Key`.
    Si no está configurada, no autentica (modo desarrollo local).
    """
    expected = get_settings().fide_scraper_api_key
    if expected is None or (isinstance(expected, str) and expected.strip() == ""):
        return
    if x_api_key != expected.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o ausente (header X-API-Key)",
        )


def _resolve_client_ip(request: Request) -> Optional[str]:
    settings = get_settings()
    if settings.fide_scraper_trust_forwarded_for:
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            # Formato típico: "client, proxy1, proxy2"
            first = forwarded_for.split(",")[0].strip()
            if first:
                return first
    if request.client and request.client.host:
        return request.client.host
    return None


def _ip_allowed(
    candidate_ip: str,
    allowlist: List[Union[IPv4Address, IPv6Address, IPv4Network, IPv6Network]],
) -> bool:
    ip_obj = ip_address(candidate_ip)
    for allowed in allowlist:
        if isinstance(allowed, (IPv4Address, IPv6Address)) and ip_obj == allowed:
            return True
        if isinstance(allowed, (IPv4Network, IPv6Network)) and ip_obj in allowed:
            return True
    return False


async def verify_admin_access(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> None:
    """
    Protege /admin/* con API key obligatoria y allowlist IP/CIDR opcional.

    - API key: si no está configurada o no coincide => 401.
    - Allowlist: si está configurada y la IP cliente no coincide => 403.
    """
    global _allowlist_warned
    settings = get_settings()

    expected = settings.fide_scraper_api_key
    if expected is None or expected.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="FIDE_SCRAPER_API_KEY no configurada para endpoints administrativos",
        )
    if x_api_key != expected.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o ausente (header X-API-Key)",
        )

    try:
        allowlist = settings.parsed_admin_allowlist()
    except ValueError as exc:
        logger.exception("Allowlist admin inválida")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FIDE_SCRAPER_ADMIN_ALLOWLIST inválida: {exc}",
        ) from None
    if not allowlist:
        if not _allowlist_warned:
            logger.warning(
                "Allowlist admin no configurada (FIDE_SCRAPER_ADMIN_ALLOWLIST); "
                "se valida solo API key."
            )
            _allowlist_warned = True
        return

    candidate_ip = _resolve_client_ip(request)
    if candidate_ip is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No se pudo resolver IP cliente")

    try:
        if _ip_allowed(candidate_ip, allowlist):
            return
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"IP cliente inválida en request: {candidate_ip}",
        ) from None

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"IP no permitida por allowlist: {candidate_ip}",
    )
