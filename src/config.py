"""Configuración de la aplicación desde variables de entorno."""

from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address, ip_network
from functools import lru_cache
from typing import Optional, Union

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración cargada desde variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Misma BD que el backend Quarkus (esquema `fide`; tablas creadas por Flyway V6 o init_db del scraper).
    database_url: str = "postgresql://clubsync:clubsync@localhost:5432/clubsync"
    # libpq application_name: pg_stat_activity / logs (no mezclar con el pool del backend).
    fide_scraper_pg_application_name: str = "fide-scraper"
    # Lista combinada oficial STD+RPD+BLZ (~48 MB en download_lists.phtml); no usar _foa si querés los mismos datos que la web.
    fide_xml_url: str = "https://ratings.fide.com/download/players_list_xml.zip"
    export_path: str = "data/exports"
    log_level: str = "INFO"
    # Si se define, todas las rutas /players/* exigen header X-API-Key (salvo documentación interna)
    fide_scraper_api_key: Optional[str] = Field(default=None, description="API key opcional para FastAPI")
    # Allowlist para endpoints /admin/* (IPs o CIDRs separados por coma; vacío = solo API key).
    fide_scraper_admin_allowlist: Optional[str] = Field(
        default=None,
        description="Allowlist IP/CIDR para rutas administrativas",
    )
    # Si es true, usa X-Forwarded-For (primer IP) para evaluar allowlist.
    fide_scraper_trust_forwarded_for: bool = Field(
        default=True,
        description="Confiar en X-Forwarded-For para obtener IP cliente",
    )
    # Import historial (scripts.run_import_history): valores por defecto si no pasás flags en CLI
    fide_history_country_codes: Optional[str] = Field(
        default=None,
        description="CSV de códigos FIDE (ej. PAR). Filtra filas antes del upsert en player_rating_history",
    )
    fide_history_period_scope: str = Field(
        default="rolling_months",
        description="rolling_months | current_year (solo meses del año calendario en curso)",
    )
    fide_history_include_club_affiliates: bool = Field(
        default=False,
        description="Incluir también jugadores con club asignado (OR con filtro de países) en import_history",
    )

    def parsed_admin_allowlist(
        self,
    ) -> list[Union[IPv4Address, IPv6Address, IPv4Network, IPv6Network]]:
        """Parses allowlist CSV into IPs/CIDRs; ignora entradas vacías."""
        if self.fide_scraper_admin_allowlist is None or self.fide_scraper_admin_allowlist.strip() == "":
            return []
        values: list[Union[IPv4Address, IPv6Address, IPv4Network, IPv6Network]] = []
        for raw in self.fide_scraper_admin_allowlist.split(","):
            token = raw.strip()
            if token == "":
                continue
            if "/" in token:
                values.append(ip_network(token, strict=False))
            else:
                values.append(ip_address(token))
        return values


@lru_cache
def get_settings() -> Settings:
    """Obtiene la configuración (cacheada)."""
    return Settings()
