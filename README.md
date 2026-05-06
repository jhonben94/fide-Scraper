# fide-Scraper

Scraper que descarga los datos oficiales XML de la [FIDE](https://www.fide.com/) (Federación Internacional de Ajedrez), los procesa, los almacena en PostgreSQL y permite exportación a JSON/CSV. Dockerizado para despliegue en producción.

**Documentación completa**: [docs/](docs/README.md)

## Requisitos

- Python 3.9+ (recomendado 3.12+; en macOS, `python3` del sistema suele ser 3.9: usá `python3.12` o un venv si podés)
- PostgreSQL 16 (o usar Docker)

## Instalación local

```bash
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tu DATABASE_URL
```

## Uso con Docker

Los datos van a la **misma PostgreSQL que el backend** (base `clubsync`, esquema `fide`).

### Desde la raíz del monorepo (recomendado)

```bash
# directorio raíz del repo (donde está docker-compose.yml)
docker compose up -d postgres fide-scraper
```

La API queda en `http://localhost:8000` y `docs` en `/docs`.

### Solo desde `fide-Scraper/` (red compartida)

Antes: en la raíz, `docker compose up -d postgres`. Luego:

```bash
docker compose build
docker compose up -d app
docker compose --profile fide-import run --rm import
```

**Importante**: Ejecutá `docker compose build` antes del primer import para que la imagen tenga el código actualizado.

### Importación manual (sin Docker)

```bash
python -m scripts.run_import
```

Opciones:

- `--period YYYY-MM-DD`: Lista histórica de esa fecha
- `--no-json`: No exportar a JSON
- `--no-csv`: No exportar a CSV

### Importar historial (para Progress)

**Importante:** Ejecuta `docker compose build` antes si acabas de añadir o modificar archivos.

El perfil `import_history` en `docker-compose.yml` usa por defecto **año calendario en curso** y solo federación **PAR** (menos filas en `fide.player_rating_history`). El XML mundial se sigue descargando y parseando; el ahorro es en escrituras a PostgreSQL.

```bash
# Reconstruir imagen (necesario si run_import_history es nuevo)
docker compose build

# Desde la raíz del monorepo:
docker compose --profile fide-import-history run --rm fide-import-history

# Desde fide-Scraper/ (con Postgres del compose raíz ya levantado):
docker compose --profile fide-import-history run --rm import_history

# Equivalente manual (SquareOne / Paraguay):
python -m scripts.run_import_history --current-year --country PAR

# Paraguay o afiliados a club local:
python -m scripts.run_import_history --current-year --country PAR --include-club-affiliates

# Reanudar sin repetir meses ya checkpointados (requiere Flyway V8):
python -m scripts.run_import_history --current-year --country PAR --skip-completed

# Solo un listado de FIDE ID (hash estable en checkpoint; no combinar con --country):
python -m scripts.run_import_history --months 24 --fide-id 123456 --fide-id 789012 --skip-completed

# Listado desde archivo (un ID por línea, # comentarios):
python -m scripts.run_import_history --months 24 --fide-ids-file ./mis_ids.txt

# Ventana rolling (ej. 12 meses), todo el mundo:
python -m scripts.run_import_history --months 12 --period-scope rolling_months

# Defaults desde .env: FIDE_HISTORY_PERIOD_SCOPE, FIDE_HISTORY_COUNTRY_CODES, FIDE_HISTORY_INCLUDE_CLUB_AFFILIATES
```

**Control de meses ya ejecutados:** tras aplicar migración Flyway `V8` (tabla `fide.history_import_checkpoint`), cada periodo importado con éxito queda registrado. Podés usar `--skip-completed` para reanudar sin repetir meses listos. Para modo `fide_ids`, la columna `country_filter` almacena una clave tipo `fides:<sha256>` (Flyway `V9` amplía el campo a VARCHAR(128)).

| Situación | Qué hacer |
|-----------|-----------|
| Primera corrida o mismo listado, sin checkpoint previo | `skip_completed` opcional |
| Reanudar import del **mismo** conjunto de FIDE ID o mismas federaciones | `skip_completed: true` |
| Borraste filas en `player_rating_history` y el checkpoint sigue marcando el periodo | `skip_completed: false` **o** borrar filas en `history_import_checkpoint` para ese `filter_key` |

**Si el portal no muestra el gráfico de historial:** el backend solo lee `fide.player_rating_history` (esquema `fide`). Si tus filas quedaron en `public.player_rating_history` por un cliente SQL incorrecto, movélas o reimportá contra la misma base que usa Quarkus.

**Retención (una vez, si ya importaste años viejos):** borrar periodos anteriores al 1 de enero del año en curso y opcionalmente vaciar/analizar:

```sql
DELETE FROM fide.player_rating_history
WHERE period < date_trunc('year', CURRENT_DATE)::date;
-- Opcional tras borrados masivos:
-- VACUUM ANALYZE fide.player_rating_history;
```

## API REST

| Endpoint | Descripción |
|----------|-------------|
| `GET /health` | Health check |
| `GET /players` | Lista jugadores (paginación, filtros) |
| `GET /players/{fideid}` | Perfil completo (datos, rankings, foa_title) |
| `GET /players/{fideid}/calculations?opponent_rating=1800` | Cálculos de rating (K-factor, puntuación esperada) |
| `GET /players/{fideid}/progress?months=24` | Evolución del rating en el tiempo |
| `GET /players/{fideid}/stats` | Estadísticas W/D/L por color (Total, Standard, Rapid, Blitz) |

Con `FIDE_SCRAPER_API_KEY` en `.env`, las rutas `/players/*` exigen header `X-API-Key`; `GET /health` sigue público. Ver [.env.example](.env.example).

**Progress** requiere datos en `fide.player_rating_history`. Recomendado para este producto: `python -m scripts.run_import_history --current-year --country PAR`

Parámetros de `GET /players`:

- `skip`, `limit`: Paginación
- `country`: Código federación (ej: ESP, USA)
- `min_rating`: Rating mínimo

## Estructura del proyecto

```
fide-Scraper/
├── src/
│   ├── config.py       # Configuración
│   ├── downloader.py   # Descarga XML FIDE
│   ├── parser.py      # Parseo XML
│   ├── models.py      # Modelo Player
│   ├── database.py    # Conexión DB
│   ├── importer.py    # Pipeline completo
│   ├── exporter.py    # Export JSON/CSV
│   ├── data/          # Mapeos (país-continente)
│   ├── services/      # Rankings, calculations, progress
│   ├── scrapers/      # Cliente API estadísticas FIDE
│   └── api/           # FastAPI (deps.py: API key opcional)
├── scripts/
│   ├── run_import.py       # CLI importación
│   └── run_import_history.py  # Import historial (Progress)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Actualización mensual

FIDE publica datos el último día de cada mes. Para actualizar automáticamente, configura un cron:

```cron
0 2 1 * * cd /ruta/al/repo && docker compose --profile fide-import run --rm fide-import
```

## Documentación

| Documento | Descripción |
|-----------|-------------|
| [Arquitectura](docs/ARCHITECTURE.md) | Diseño del sistema y componentes |
| [API REST](docs/API.md) | Endpoints y ejemplos |
| [Configuración](docs/CONFIGURATION.md) | Variables de entorno |
| [Despliegue](docs/DEPLOYMENT.md) | Docker y producción |

## Licencia

Apache 2.0
