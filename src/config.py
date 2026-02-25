"""Configuración de la aplicación desde variables de entorno."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración cargada desde variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str = "postgresql://fide:fide@localhost:5432/fide"
    # Listas disponibles: standard, rapid, blitz, combined (STD+RPD+BLZ)
    fide_xml_url: str = "https://ratings.fide.com/download/standard_rating_list_xml.zip"
    export_path: str = "data/exports"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Obtiene la configuración (cacheada)."""
    return Settings()
