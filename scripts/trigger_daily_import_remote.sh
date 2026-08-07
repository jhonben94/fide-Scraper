#!/usr/bin/env bash
# Dispara /admin/import (fide.players, catálogo vigente) en el fide-scraper desplegado y espera
# el resultado. Corré esto junto con trigger_daily_sync_remote.sh (misma cadencia diaria) — son
# jobs independientes que alimentan tablas distintas: este actualiza fide.players (ranking en
# vivo, ficha de jugador); el otro actualiza fide.player_rating_history (gainers, progreso).
#
# Variables de entorno requeridas:
#   FIDE_SCRAPER_API_KEY   - valor de FIDE_SCRAPER_API_KEY en el fide-scraper desplegado
# Opcionales:
#   FIDE_SCRAPER_URL       - default: https://fide.squareone.kahani.dev
#   FIDE_SYNC_MAX_WAIT_SEC - timeout de espera del job (default: 900; descarga+parsea el XML mundial)
#   FIDE_SYNC_POLL_SEC     - intervalo de polling (default: 15)

set -eu

FIDE_SCRAPER_URL="${FIDE_SCRAPER_URL:-https://fide.squareone.kahani.dev}"
MAX_WAIT_SECONDS="${FIDE_SYNC_MAX_WAIT_SEC:-900}"
POLL_INTERVAL="${FIDE_SYNC_POLL_SEC:-15}"

if [ -z "${FIDE_SCRAPER_API_KEY:-}" ]; then
  echo "Falta FIDE_SCRAPER_API_KEY en el entorno de este schedule." >&2
  exit 1
fi

echo "Disparando actualización diaria del catálogo (fide.players, PAR + afiliados a club)..."
job_response=$(curl -sS -X POST "${FIDE_SCRAPER_URL}/admin/import" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${FIDE_SCRAPER_API_KEY}" \
  -d '{"export_json": false, "export_csv": false, "countries": ["PAR"], "include_club_affiliates": true}')

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
      echo "Actualización de catálogo OK."
      echo "$status_json"
      exit 0
      ;;
    failed)
      echo "Actualización de catálogo FALLÓ." >&2
      echo "$status_json" >&2
      exit 1
      ;;
  esac

  sleep "$POLL_INTERVAL"
  elapsed=$((elapsed + POLL_INTERVAL))
done

echo "Timeout (${MAX_WAIT_SECONDS}s) esperando el resultado del job $job_id" >&2
exit 1
