# Feature: REST API

## Overview
FastAPI REST API serving FIDE player data: profiles, rankings, rating calculations, progress (time series), and live statistics. Optional API key authentication for public routes; admin routes for triggering imports.

## Functional Requirements

### FR-001: Health Check
- `GET /health` - Always public, returns service status

### FR-002: Player Listing
- `GET /players` - Paginated list with `skip`, `limit`, `country`, `min_rating` filters

### FR-003: Player Profile
- `GET /players/{fideid}` - Complete profile: data, ratings, titles, rankings (world/national/continent for active+all)

### FR-004: Rating Calculations
- `GET /players/{fideid}/calculations?opponent_rating=1800` - ELO expected score, K-factor (K=40/20/10 per FIDE regulations), rating change for win/draw/loss

### FR-005: Rating Progress
- `GET /players/{fideid}/progress?months=24` - Time series of Standard/Rapid/Blitz ratings from `player_rating_history`

### FR-006: Live Statistics
- `GET /players/{fideid}/stats` - W/D/L by color (white/black) across Total, Standard, Rapid, Blitz - fetched live from FIDE's internal API

### FR-007: Admin Import
- `POST /admin/import` - Trigger base import as background job
- `POST /admin/import-history` - Trigger history import as background job
- `POST /admin/import-modality-flags` - Trigger modality flag import
- `GET /admin/jobs/{job_id}` - Query job status

## Security
- Public routes: Optional `X-API-Key` header
- Admin routes: Mandatory API key + IP/CIDR allowlist (`FIDE_SCRAPER_ADMIN_ALLOWLIST`)
- `X-Forwarded-For` trust for reverse proxy setups

## Success Criteria
- SC-001: Player profile response < 200ms
- SC-002: Calculations follow official FIDE ELO formulas
- SC-003: Admin jobs run in background with status tracking
- SC-004: Single-job concurrency guard (409 on conflict)
