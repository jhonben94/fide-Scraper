"""Script CLI para ejecutar la importación de datos FIDE."""

import argparse
import logging
import sys

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
        "--no-json",
        action="store_true",
        help="No exportar a JSON",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="No exportar a CSV",
    )
    args = parser.parse_args()

    try:
        result = run_import(
            period=args.period,
            export_json=not args.no_json,
            export_csv=not args.no_csv,
        )
        logger.info("Resultado: %s", result)
    except Exception as e:
        logger.exception("Error durante la importación: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
