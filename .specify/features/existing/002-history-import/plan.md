# Feature: History Import - Implementation Plan

## Architecture

### Pipeline Flow
```
CLI (run_import_history.py)
  -> Scope Resolution (current_year | rolling_months | fide_ids)
    -> For each period:
        -> Download 3 archive ZIPs (std + rpd + blz)
        -> Parse each XML
        -> Three-pass upsert with COALESCE
        -> Record checkpoint
```

### Module Structure
```
scripts/run_import_history.py  -> CLI with argparse (months, country, skip-completed, etc.)
src/importer_history.py        -> Multi-period pipeline
src/downloader.py              -> discover_period_archive_xml_zip_urls() + streaming download
src/parser.py                  -> Streaming XML parser (reused)
src/models.py                  -> PlayerRatingHistory + HistoryImportCheckpoint models
src/database.py                -> Engine + session management
```

### Database Operations
- `PlayerRatingHistory`: unique(fideid, period), nullable rating columns
- `HistoryImportCheckpoint`: (period, filter_key, country_filter, completed_at)
- Three-pass COALESCE: `UPDATE SET std = COALESCE(NEW.std, EXISTING.std)`

### Scope Resolution
| Scope | Logic |
|-------|-------|
| `current_year` | Jan 1 to current month of current year |
| `rolling_months N` | Last N months from current date |
| `fide_ids` | All periods in scope, filtered by ID list |

## Implementation Phases

### Phase 1: Archive Discovery
- Scrape FIDE archive page for per-modality ZIP URLs
- Map periods to download URLs for std/rpd/blz

### Phase 2: Multi-Period Pipeline
- Iterate over periods in scope
- Skip completed periods if `--skip-completed`
- Download, parse, upsert per period

### Phase 3: Three-Pass Upsert
- Pass 1: Standard ratings (INSERT ON CONFLICT)
- Pass 2: Rapid ratings (UPDATE with COALESCE)
- Pass 3: Blitz ratings (UPDATE with COALESCE)

### Phase 4: Filtering
- Country code filter: `WHERE country IN (...)`
- Club affiliate filter: JOIN `player` table for `current_club_id`
- FIDE ID filter: `WHERE fideid IN (...)`

### Phase 5: Checkpointing
- Record completed period + filter_key in checkpoint table
- SHA-256 hash for FIDE ID lists (stable key)
- `country_filter` column for federation-based checkpoints

## Key Decisions
- **Three-pass COALESCE**: Each modality ZIP is separate; merge at DB level
- **Checkpoint per period**: Granular resume, don't reprocess completed months
- **SHA-256 for ID lists**: Stable hash regardless of ID order in command line
- **Archive scraping**: Dynamic URL discovery instead of hardcoded URLs
