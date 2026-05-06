"""Script CLI para importar historial de ratings (Progress)."""

import argparse
import logging
import sys
from typing import Literal

from src.config import get_settings
from src.importer_history import run_import_history

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_period_scope(raw: str) -> Literal["rolling_months", "current_year"]:
    v = (raw or "").strip().lower()
    if v == "current_year":
        return "current_year"
    return "rolling_months"


def _load_fide_ids_from_file(path: str) -> frozenset[int]:
    out: set[int] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            token = raw.split()[0]
            out.add(int(token))
    return frozenset(out)


def main():
    parser = argparse.ArgumentParser(description="Importar historial de ratings FIDE para Progress")
    parser.add_argument(
        "--months",
        type=int,
        default=24,
        help="Meses hacia atrás en modo rolling (default: 24). Ignorado con --current-year.",
    )
    parser.add_argument(
        "--current-year",
        action="store_true",
        help="Solo periodos del año calendario en curso (enero → mes actual)",
    )
    parser.add_argument(
        "--period-scope",
        type=str,
        choices=["rolling_months", "current_year"],
        default=None,
        help="Alternativa a --current-year (útil con variables de entorno documentadas)",
    )
    parser.add_argument(
        "--country",
        action="append",
        dest="countries",
        metavar="CODE",
        help="Código federación FIDE (repetible), ej. --country PAR. Sin esto: todo el mundo (o FIDE_HISTORY_COUNTRY_CODES en .env)",
    )
    parser.add_argument(
        "--skip-completed",
        action="store_true",
        help="No reprocesar periodos ya registrados en fide.history_import_checkpoint",
    )
    parser.add_argument(
        "--include-club-affiliates",
        action="store_true",
        help="Incluye también jugadores con club asignado (OR con --country PAR)",
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
        "--fide-ids-file",
        type=str,
        default=None,
        metavar="PATH",
        help="Archivo con un FIDE ID por línea (# comentarios). Se unen con --fide-id.",
    )
    args = parser.parse_args()

    settings = get_settings()

    merged_fides: set[int] = set()
    if args.fide_ids_arg:
        merged_fides.update(int(x) for x in args.fide_ids_arg)
    if args.fide_ids_file:
        merged_fides.update(_load_fide_ids_from_file(args.fide_ids_file))

    fid: frozenset[int] | None = frozenset(merged_fides) if merged_fides else None

    if fid:
        if args.countries:
            logger.warning("Ignorando --country en modo --fide-id / --fide-ids-file")
        if args.include_club_affiliates:
            logger.warning("Ignorando --include-club-affiliates en modo listado FIDE ID")
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

    period_scope: Literal["rolling_months", "current_year"] = "rolling_months"
    if args.current_year:
        period_scope = "current_year"
    elif args.period_scope is not None:
        period_scope = _parse_period_scope(args.period_scope)
    else:
        period_scope = _parse_period_scope(settings.fide_history_period_scope)

    try:
        result = run_import_history(
            months=args.months,
            period_scope=period_scope,
            country_codes=codes,
            include_club_affiliates=include_club_affiliates,
            skip_completed=bool(args.skip_completed),
            fide_ids=fid,
        )
        logger.info("Resultado: %s", result)
    except Exception as e:
        logger.exception("Error durante la importación: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
