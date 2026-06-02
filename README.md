# FIDE Scraper

Scraper que descarga los datos oficiales XML de la [FIDE](https://www.fide.com/) (Federación Internacional de Ajedrez), los procesa, los almacena en PostgreSQL (esquema `fide`) y expone una API REST con capacidades de exportación. Dockerizado para despliegue en producción.

## Stack

| Capa | Tecnología | Versión |
|------|-----------|---------|
| Lenguaje | Python | 3.12 |
| API | FastAPI | >=0.115.0 |
| ASGI | Uvicorn | >=0.32.0 |
| ORM/Toolkit | SQLAlchemy | >=2.0.0 |
| Base de datos | PostgreSQL | 16 |
| HTTP Client | httpx | >=0.27.0 |
| Validación | Pydantic | >=2.0.0 |
| Settings | pydantic-settings | >=2.0.0 |

## Features

### 1. Importación Base Mensual
Descarga el ZIP XML combinado de FIDE (~48MB), parseo streaming con `iterparse`, batch upsert de 5000 registros en `fide.players`. Soporta importación selectiva por FIDE ID (hasta 50,000). Exportación automática a JSON/CSV (hasta 100K jugadores).

**CLI**: `python -m scripts.run_import [--period YYYY-MM-DD] [--no-json] [--no-csv]`

### 2. Importación Histórica de Ratings
Descarga archives ZIP por periodo (standard + rapid + blitz por separado), three-pass upsert con `COALESCE` para merge de modalidades. Scopes: `--current-year` (año calendario), `--months N` (rolling window). Filtros: `--country PAR`, `--include-club-affiliates`, `--fide-id`, `--fide-ids-file`. Checkpoint en `history_import_checkpoint` para resume con `--skip-completed`. FIDE ID lists usan SHA-256 como checkpoint key estable.

**CLI**: `python -m scripts.run_import_history --current-year --country PAR [--skip-completed]`

### 3. Import de Flags por Modalidad
Descarga los 3 ZIPs por modalidad para un periodo, extrae `flag` por jugador, batch-update de columnas `flag_std`, `flag_rpd`, `flag_blz` vía `UPDATE ... FROM unnest()`. Auto-resuelve periodo desde `MAX(period)`.

### 4. API REST - Jugadores

| Endpoint | Descripción |
|----------|-------------|
| `GET /health` | Health check (siempre público) |
| `GET /players` | Lista paginada con filtros (country, min_rating) |
| `GET /players/{fideid}` | Perfil completo con rankings (mundial/nacional/continental, activos/todos) |
| `GET /players/{fideid}/calculations?opponent_rating=1800` | Cálculos ELO: expected score, K-factor, rating change |
| `GET /players/{fideid}/progress?months=24` | Evolución del rating (Std/Rpd/Blz) en el tiempo |
| `GET /players/{fideid}/stats` | Estadísticas W/D/L por color (Total, Std, Rpd, Blz) - live desde FIDE |

Con `FIDE_SCRAPER_API_KEY` en `.env`, rutas `/players/*` exigen header `X-API-Key`.

### 5. API REST - Admin

| Endpoint | Descripción |
|----------|-------------|
| `POST /admin/import` | Trigger importación base (background job) |
| `POST /admin/import-history` | Trigger importación histórica (background job) |
| `POST /admin/import-modality-flags` | Trigger import de flags (background job) |
| `GET /admin/jobs/{job_id}` | Estado del job (queued/running/success/failed) |

Requiere API key + IP/CIDR allowlist (`FIDE_SCRAPER_ADMIN_ALLOWLIST`). Single-job concurrency guard (409 si ya hay un job corriendo).

### 6. Exportación de Datos
- **JSON**: Archivo timestamped con todos los campos del jugador
- **CSV**: Archivo timestamped
- **Por país**: Archivos JSON separados por federación en `by_country/`
- Máximo 100,000 jugadores por export

### Cálculos de Rating (Regulaciones FIDE)
- **Expected Score**: `E = 1 / (1 + 10^((Rb-Ra)/400))`
- **K-Factor**: K=40 (nuevos <30 partidas, o U18 con rating <2300), K=20 (rating <2400 con >=30 partidas), K=10 (rating >=2400 con >=30 partidas)
- **Rating Change**: `delta_R = K * (Score - ExpectedScore)`

## Requisitos

- Python 3.9+ (recomendado 3.12+)
- PostgreSQL 16 (o usar Docker)

## Instalación local

```bash
pip install -r requirements.txt
cp .env.example .env
# Editar .env con DATABASE_URL
```

## Arranque rápido

### Con Docker (desde raíz del monorepo)

```bash
docker compose up -d postgres fide-scraper
```

API en `http://localhost:8000`, docs en `/docs`.

### Solo desde fide-Scraper/ (red compartida)

```bash
# Primero levantar postgres desde la raíz
docker compose build
docker compose up -d app
docker compose --profile fide-import run --rm import
```

### Importación manual (sin Docker)

```bash
python -m scripts.run_import
python -m scripts.run_import_history --current-year --country PAR
```

## Estructura

```
fide-Scraper/
├── src/
│   ├── config.py              # Pydantic-settings desde .env
│   ├── downloader.py          # Descarga streaming ZIP + extracción XML
│   ├── parser.py              # iterparse streaming XML
│   ├── models.py              # SQLAlchemy models (Player, RatingHistory, Checkpoint)
│   ├── database.py            # Engine + connection pooling
│   ├── importer.py            # Pipeline base (download -> parse -> upsert -> export)
│   ├── importer_history.py    # Pipeline histórico (multi-period, three-pass)
│   ├── importer_modality_flags.py  # Import flags por modalidad
│   ├── exporter.py            # JSON/CSV/per-country export
│   ├── data/                  # Mapeos (country_continent.json)
│   ├── services/              # Rankings, calculations, progress
│   ├── scrapers/              # FIDE stats scraper
│   └── api/                   # FastAPI (routes, admin_routes, deps, main)
├── scripts/
│   ├── run_import.py          # CLI importación base
│   └── run_import_history.py  # CLI importación histórica
├── docs/                      # Documentación detallada
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── CONFIGURATION.md
│   └── DEPLOYMENT.md
├── Dockerfile                 # Multi-stage build (3.12-slim, non-root)
├── docker-compose.yml         # 3 services (app, import, import_history)
├── VERSION                    # 1.1.5
└── requirements.txt
```

## SDD (Spec-Driven Development)

Este proyecto usa [Spec-Driven Development](https://github.com/github/spec-kit) para gestionar features. La documentación vive en `.specify/`:

```
.specify/
├── memory/constitution.md          # Principios del proyecto
└── features/existing/              # Features documentados
    ├── 001-base-import/            # specify.md + plan.md (core)
    ├── 002-history-import/         # specify.md + plan.md (core)
    ├── 004-rest-api/               # specify.md + plan.md (core)
    └── 003,005,006-*/              # specify.md (baseline)
```

Para agregar un nuevo feature:
```
/speckit.specify   -> Definir requisitos
/speckit.plan      -> Plan técnico
/speckit.tasks     -> Desglose de tareas
/speckit.implement -> Implementar
```

## Actualización mensual

FIDE publica datos el último día de cada mes. Cron recomendado:

```cron
0 2 1 * * cd /ruta/al/repo && docker compose --profile fide-import run --rm fide-import
```

## Despliegue

Imagen: `jhonybenitez/squareone-fide-scraper:{version}` (tag desde `VERSION`)

Los datos van a la **misma PostgreSQL que el backend** (base `clubsync`, esquema `fide`).

## Documentación adicional

| Documento | Descripción |
|-----------|-------------|
| [Arquitectura](docs/ARCHITECTURE.md) | Diseño del sistema y componentes |
| [API REST](docs/API.md) | Endpoints y ejemplos |
| [Configuración](docs/CONFIGURATION.md) | Variables de entorno |
| [Despliegue](docs/DEPLOYMENT.md) | Docker y producción |

## Licencia

Apache 2.0
