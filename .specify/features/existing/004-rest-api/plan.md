# Feature: REST API - Implementation Plan

## Architecture

### Route Structure
```
src/api/main.py          -> FastAPI app, lifecycle, auto-migrations
src/api/routes.py        -> Public routes (/health, /players/*)
src/api/admin_routes.py  -> Admin routes (/admin/*)
src/api/deps.py          -> API key dependency, admin allowlist
```

### Service Layer
```
src/services/calculations.py  -> ELO formulas, K-factor, rating change
src/services/rankings.py      -> World/national/continental rankings
src/services/progress.py      -> Rating time series from history table
src/scrapers/fide_stats.py    -> Live W/D/L from FIDE internal API
```

### App Lifecycle
- Auto-creates `fide` schema on startup
- Runs `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for new columns (foa_title, foa_rating, flag_std, flag_rpd, flag_blz, updated_at)

## Implementation Phases

### Phase 1: Public Endpoints
- Health check (no auth)
- Player listing with pagination and filters
- Player profile with rankings computation

### Phase 2: Calculations & Progress
- ELO expected score: `E = 1 / (1 + 10^((Rb-Ra)/400))`
- K-factor: K=40 (new <30 games or U18 <2300), K=20 (<2400 with >=30 games), K=10 (>=2400 with >=30 games)
- Rating change: `delta_R = K * (Score - ExpectedScore)`
- Progress: Query `player_rating_history` ordered by period

### Phase 3: Live Statistics
- httpx client to `ratings.fide.com/a_data_stats.php`
- Parse HTML response for W/D/L by color
- Structure into Total/Standard/Rapid/Blitz categories

### Phase 4: Admin Endpoints
- Background job system with status tracking
- Single-job concurrency guard (409 if job already running)
- Import triggers with configurable parameters

### Phase 5: Security
- `X-API-Key` dependency for public routes (optional)
- Mandatory API key + IP/CIDR allowlist for admin routes
- `X-Forwarded-For` trust configuration

## Key Decisions
- **FastAPI over Flask**: Async support, automatic OpenAPI docs, Pydantic validation
- **Live stats scraping**: FIDE doesn't expose a public API for game statistics
- **Background jobs**: Imports take minutes; don't block HTTP response
- **Auto-migrations on startup**: Schema evolution without separate migration tool
