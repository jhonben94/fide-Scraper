"""Script CLI para importar historial de ratings (Progress)."""

import argparse
import logging
import sys

from src.importer_history import run_import_history

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Importar historial de ratings FIDE para Progress")
    parser.add_argument(
        "--months",
        type=int,
        default=24,
        help="Número de meses hacia atrás a importar (default: 24)",
    )
    args = parser.parse_args()

    try:
        result = run_import_history(months=args.months)
        logger.info("Resultado: %s", result)
    except Exception as e:
        logger.exception("Error durante la importación: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
