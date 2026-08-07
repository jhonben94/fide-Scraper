#!/usr/bin/env bash
# Dispara /admin/import-history en el fide-scraper desplegado y espera el resultado.
# Pensado para corridas puntuales (backfill de varios meses), no para un schedule recurrente
# (para eso está trigger_daily_sync_remote.sh).
#
# Variables de entorno requeridas:
#   FIDE_SCRAPER_API_KEY      - valor de FIDE_SCRAPER_API_KEY en el fide-scraper desplegado
# Opcionales:
#   FIDE_SCRAPER_URL          - default: https://fide.squareone.kahani.dev
#   FIDE_HISTORY_MONTHS       - default: 60 (5 años)
#   FIDE_HISTORY_PERIOD_SCOPE - default: rolling_months
#   FIDE_HISTORY_SKIP_COMPLETED - default: false ("true" para omitir períodos ya en checkpoint)
#   FIDE_SYNC_MAX_WAIT_SEC    - timeout de espera del job (default: 10800 = 3h; 60 meses puede tardar)
#   FIDE_SYNC_POLL_SEC        - intervalo de polling (default: 30)

set -eu

FIDE_SCRAPER_URL="${FIDE_SCRAPER_URL:-https://fide.squareone.kahani.dev}"
MONTHS="${FIDE_HISTORY_MONTHS:-60}"
PERIOD_SCOPE="${FIDE_HISTORY_PERIOD_SCOPE:-rolling_months}"
SKIP_COMPLETED="${FIDE_HISTORY_SKIP_COMPLETED:-false}"
MAX_WAIT_SECONDS="${FIDE_SYNC_MAX_WAIT_SEC:-10800}"
POLL_INTERVAL="${FIDE_SYNC_POLL_SEC:-30}"

if [ -z "${FIDE_SCRAPER_API_KEY:-}" ]; then
  echo "Falta FIDE_SCRAPER_API_KEY en el entorno." >&2
  exit 1
fi

echo "Disparando backfill histórico: ${MONTHS} meses, scope=${PERIOD_SCOPE}, skip_completed=${SKIP_COMPLETED} (PAR + afiliados a club)..."
job_response=$(curl -sS -X POST "${FIDE_SCRAPER_URL}/admin/import-history" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${FIDE_SCRAPER_API_KEY}" \
  -d "{\"months\": ${MONTHS}, \"period_scope\": \"${PERIOD_SCOPE}\", \"countries\": [\"PAR\"], \"include_club_affiliates\": true, \"skip_completed\": ${SKIP_COMPLETED}}")

job_id=$(echo "$job_response" | grep -o '"job_id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$job_id" ]; then
  echo "No se pudo encolar el job. Respuesta: $job_response" >&2
  exit 1
fi
echo "Job encolado: $job_id (puede tardar bastante — no cierres la terminal)"

elapsed=0
while [ "$elapsed" -lt "$MAX_WAIT_SECONDS" ]; do
  status_json=$(curl -sS -H "X-API-Key: ${FIDE_SCRAPER_API_KEY}" \
    "${FIDE_SCRAPER_URL}/admin/jobs/${job_id}")
  status=$(echo "$status_json" | grep -o '"status":"[^"]*"' | head -1 | cut -d'"' -f4)

  case "$status" in
    success)
      echo "Backfill histórico OK."
      echo "$status_json"
      exit 0
      ;;
    failed)
      echo "Backfill histórico FALLÓ." >&2
      echo "$status_json" >&2
      exit 1
      ;;
    *)
      echo "[$(date +%H:%M:%S)] status=${status:-desconocido}, esperando..."
      ;;
  esac

  sleep "$POLL_INTERVAL"
  elapsed=$((elapsed + POLL_INTERVAL))
done

echo "Timeout (${MAX_WAIT_SECONDS}s) esperando el resultado del job $job_id — puede seguir corriendo igual, consultá manualmente:" >&2
echo "curl -sS -H \"X-API-Key: \$FIDE_SCRAPER_API_KEY\" \"${FIDE_SCRAPER_URL}/admin/jobs/${job_id}\"" >&2
exit 1
