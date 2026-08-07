"""Script CLI para ejecutar la importación de datos FIDE."""

import argparse
import logging
import sys

from src.config import get_settings
from src.importer import run_import

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Importar datos FIDE a la base de datos")
    parser.add_argument(
        "--period",
        type=str,
        default=None,
        help="Fecha en formato YYYY-MM-DD para listas históricas",
    )
    parser.add_argument(
        "--country",
        action="append",
        dest="countries",
        metavar="CODE",
        help="Código federación FIDE (repetible), ej. --country PAR. Sin esto: todo el mundo",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="No exportar a JSON",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="No exportar a CSV",
    )
    parser.add_argument(
        "--include-club-affiliates",
        action="store_true",
        help="Incluye también jugadores con club asignado (OR con --country), ej. extranjeros afiliados a un club local",
    )
    args = parser.parse_args()

    settings = get_settings()
    countries = args.countries
    if not countries and settings.fide_history_country_codes:
        countries = [
            c.strip().upper()
            for c in settings.fide_history_country_codes.split(",")
            if c.strip()
        ]

    codes = frozenset(countries) if countries else None
    include_club_affiliates = bool(
        args.include_club_affiliates or settings.fide_history_include_club_affiliates
    )

    try:
        result = run_import(
            period=args.period,
            export_json=not args.no_json,
            export_csv=not args.no_csv,
            country_codes=codes,
            include_club_affiliates=include_club_affiliates,
        )
        logger.info("Resultado: %s", result)
    except Exception as e:
        logger.exception("Error durante la importación: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
