"""Script CLI para la sincronización diaria de ratings basada en cambios."""

import argparse
import logging
import sys
from datetime import date

from src.config import get_settings
from src.importer_history import run_daily_change_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Sincronizar fide.player_rating_history con los ZIP actuales de FIDE, "
        "escribiendo solo filas donde el rating realmente cambió"
    )
    parser.add_argument(
        "--country",
        action="append",
        dest="countries",
        metavar="CODE",
        help="Código federación FIDE (repetible), ej. --country PAR. Sin esto: FIDE_HISTORY_COUNTRY_CODES en .env",
    )
    parser.add_argument(
        "--include-club-affiliates",
        action="store_true",
        help="Incluye también jugadores con club asignado (OR con --country)",
    )
    parser.add_argument(
        "--fide-id",
        action="append",
        dest="fide_ids_arg",
        metavar="ID",
        default=None,
        help="FIDE ID a incluir (repetible). No combinar con --country ni --include-club-affiliates.",
    )
    parser.add_argument(
        "--period",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help="Fecha a usar como period de las filas de cambio (default: hoy)",
    )
    args = parser.parse_args()

    settings = get_settings()

    merged_fides: set[int] = set()
    if args.fide_ids_arg:
        merged_fides.update(int(x) for x in args.fide_ids_arg)
    fid: frozenset[int] | None = frozenset(merged_fides) if merged_fides else None

    if fid:
        if args.countries:
            logger.warning("Ignorando --country en modo --fide-id")
        codes = None
        include_club_affiliates = False
    else:
        countries = list(args.countries) if args.countries else None
        if not countries and settings.fide_history_country_codes:
            countries = [x.strip() for x in settings.fide_history_country_codes.split(",") if x.strip()]
        codes = frozenset(c.strip().upper() for c in countries) if countries else None
        include_club_affiliates = bool(
            args.include_club_affiliates or settings.fide_history_include_club_affiliates
        )

    period = date.fromisoformat(args.period) if args.period else None

    try:
        result = run_daily_change_sync(
            country_codes=codes,
            include_club_affiliates=include_club_affiliates,
            fide_ids=fid,
            period=period,
        )
        logger.info("Resultado: %s", result)
    except Exception as e:
        logger.exception("Error durante la sincronización diaria: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
