#!/usr/bin/env bash
# Dispara /admin/import-history en el fide-scraper desplegado para el snapshot mensual DENSO
# (period_scope=current_year: una fila por jugador por cada mes de enero al mes actual). Es lo
# que sostiene el selector de "ver el ranking de tal mes" en el sitio público.
#
# No confundir con:
#   - trigger_daily_sync_remote.sh      -> fide.player_rating_history, solo cambios, diario
#   - trigger_daily_import_remote.sh    -> fide.players (catálogo vigente), diario
#   - trigger_history_backfill_remote.sh -> backfill puntual de N meses (5 años), uso único
#
# Pensado para un schedule mensual (día 1), no diario.
#
# Variables de entorno requeridas:
#   FIDE_SCRAPER_API_KEY   - valor de FIDE_SCRAPER_API_KEY en el fide-scraper desplegado
# Opcionales:
#   FIDE_SCRAPER_URL       - default: https://fide.squareone.kahani.dev
#   FIDE_SYNC_MAX_WAIT_SEC - timeout de espera del job (default: 3600; hasta 12 meses x 3 modalidades)
#   FIDE_SYNC_POLL_SEC     - intervalo de polling (default: 20)

set -eu

FIDE_SCRAPER_URL="${FIDE_SCRAPER_URL:-https://fide.squareone.kahani.dev}"
MAX_WAIT_SECONDS="${FIDE_SYNC_MAX_WAIT_SEC:-3600}"
POLL_INTERVAL="${FIDE_SYNC_POLL_SEC:-20}"

if [ -z "${FIDE_SCRAPER_API_KEY:-}" ]; then
  echo "Falta FIDE_SCRAPER_API_KEY en el entorno de este schedule." >&2
  exit 1
fi

echo "Disparando snapshot mensual denso (current_year, PAR + afiliados a club)..."
job_response=$(curl -sS -X POST "${FIDE_SCRAPER_URL}/admin/import-history" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${FIDE_SCRAPER_API_KEY}" \
  -d '{"period_scope": "current_year", "countries": ["PAR"], "include_club_affiliates": true}')

job_id=$(echo "$job_response" | grep -o '"job_id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$job_id" ]; then
  echo "No se pudo encolar el job. Respuesta: $job_response" >&2
  exit 1
fi
echo "Job encolado: $job_id"

elapsed=0
while [ "$elapsed" -lt "$MAX_WAIT_SECONDS" ]; do
  status_json=$(curl -sS -H "X-API-Key: ${FIDE_SCRAPER_API_KEY}" \
    "${FIDE_SCRAPER_URL}/admin/jobs/${job_id}")
  status=$(echo "$status_json" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)

  case "$status" in
    success)
      echo "Snapshot mensual OK."
      echo "$status_json"
      exit 0
      ;;
    failed)
      echo "Snapshot mensual FALLÓ." >&2
      echo "$status_json" >&2
      exit 1
      ;;
  esac

  sleep "$POLL_INTERVAL"
  elapsed=$((elapsed + POLL_INTERVAL))
done

echo "Timeout (${MAX_WAIT_SECONDS}s) esperando el resultado del job $job_id" >&2
exit 1
