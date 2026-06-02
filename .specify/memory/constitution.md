# FIDE Scraper Constitution

## Core Principles

### I. Memory-Efficient Data Processing
All FIDE XML processing uses streaming parsers (`iterparse`) to handle ~48MB XML files without loading entire documents into memory. Batch database operations use configurable batch sizes (default 5000) with PostgreSQL `ON CONFLICT DO UPDATE` upserts. Downloads are streamed to disk, not held in memory.

### II. Shared Database Schema
The `fide` schema in the shared `clubsync` PostgreSQL database is the single source of truth for FIDE player data. The backend reads from this schema for rankings and player profiles. No separate database; schema isolation provides logical separation.

### III. Idempotent Operations
All import operations are idempotent. Base imports use `ON CONFLICT DO UPDATE` by `fideid`. History imports use checkpoint tables (`history_import_checkpoint`) to track completed periods, enabling `--skip-completed` for resumable imports. Re-running the same import produces the same result.

### IV. API as Data Gateway
The FastAPI REST API serves as the data gateway for FIDE player information. It provides player profiles, rating calculations (ELO formulas, K-factors), rating progress (time series), and live statistics (W/D/L by color from FIDE's internal API). Optional API key authentication for public routes; mandatory API key + IP allowlist for admin routes.

### V. Background Job System
Admin operations (imports) run as background jobs with status tracking (queued/running/success/failed). Single-job concurrency guard prevents overlapping imports. Job status is queryable via REST API.

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.12 |
| API Framework | FastAPI | >=0.115.0 |
| ASGI Server | Uvicorn | >=0.32.0 |
| ORM/Toolkit | SQLAlchemy | >=2.0.0 |
| Database | PostgreSQL | 16 |
| DB Driver | psycopg2-binary | >=2.9.0 |
| HTTP Client | httpx | >=0.27.0 |
| Validation | Pydantic | >=2.0.0 |
| Settings | pydantic-settings | >=2.0.0 |
| Config | python-dotenv | >=1.0.0 |

## Code Conventions

- **Package structure**: `src/` for core modules, `src/api/` for FastAPI routes, `src/services/` for business logic, `src/scrapers/` for external API clients
- **Modules**: `downloader.py`, `parser.py`, `importer.py`, `importer_history.py`, `importer_modality_flags.py`, `exporter.py`, `models.py`, `database.py`, `config.py`
- **Scripts**: `scripts/run_import.py`, `scripts/run_import_history.py` for CLI entry points
- **Settings**: Pydantic-settings `Settings` class loading from `.env` and environment variables
- **Database**: SQLAlchemy engine with connection pooling (pool_size=5, max_overflow=10), `pool_pre_ping` for stale connection detection
- **Error handling**: FastAPI exception handlers, structured logging
- **Naming**: snake_case for Python files and functions, PascalCase for classes

## Data Model

### Table: `fide.players`
| Field | Type | Description |
|-------|------|-------------|
| fideid | Integer | PK, FIDE identifier |
| name | String | Official name |
| country | String | Federation code (3-letter) |
| sex | String | M/F |
| birthday | Integer | Birth year |
| rating | Integer | Standard rating |
| games | Integer | Standard games |
| flag | String | Inactivity flag |
| flag_std | String | Standard modality flag |
| rapid_rating | Integer | Rapid rating |
| rapid_games | Integer | Rapid games |
| flag_rpd | String | Rapid modality flag |
| blitz_rating | Integer | Blitz rating |
| blitz_games | Integer | Blitz games |
| flag_blz | String | Blitz modality flag |
| title | String | FIDE title (GM, IM, etc.) |
| foa_title | String | FOA title |
| foa_rating | Integer | FOA rating |
| updated_at | DateTime | Last update timestamp |

### Table: `fide.player_rating_history`
Per-period snapshots with unique constraint on `(fideid, period)`.

### Table: `fide.history_import_checkpoint`
Tracks completed import periods for idempotency.

## Security Model

| Layer | Mechanism |
|-------|-----------|
| Public routes (`/players/*`) | Optional `X-API-Key` header (disabled if key not set) |
| Admin routes (`/admin/*`) | Mandatory API key + IP/CIDR allowlist |
| Health check (`/health`) | Always public, no auth |
| Proxy support | `X-Forwarded-For` trust for reverse proxy setups |

## Deployment

- **Docker**: Multi-stage build (Python 3.12-slim, non-root `appuser`)
- **Docker Compose**: 3 services (app, import, import_history) on shared network
- **Image tagging**: Based on `VERSION` file (current: 1.1.5)
- **Registry**: `jhonybenitez/squareone-fide-scraper:{version}`
- **Cron**: Monthly update on 1st of month at 02:00

## Governance

This constitution supersedes all ad-hoc practices. Amendments require:
1. Documentation of the change rationale
2. Agreement from the development team
3. Migration plan for any breaking changes

All new features must follow the SDD workflow: specify -> plan -> tasks -> implement.

**Version**: 1.0.0 | **Ratified**: 2026-05-27 | **Last Amended**: 2026-05-27
