# Feature: Base Import - Implementation Plan

## Architecture

### Pipeline Flow
```
CLI (run_import.py)
  -> Downloader (download ZIP, stream to disk, extract XML)
    -> Parser (iterparse, streaming, clear elements)
      -> Importer (batch upsert, 5000 per batch)
        -> Exporter (JSON + CSV, up to 100K players)
```

### Module Structure
```
scripts/run_import.py      -> CLI entry point with argparse
src/downloader.py          -> Streaming ZIP download + XML extraction
src/parser.py              -> iterparse-based XML parser
src/importer.py            -> Batch upsert pipeline
src/exporter.py            -> JSON/CSV export
src/models.py              -> SQLAlchemy Player model
src/database.py            -> Engine + session management
src/config.py              -> Settings from .env
```

### Database Operations
- Connection pooling: pool_size=5, max_overflow=10
- `pool_pre_ping`: Detect stale connections
- Batch upsert: `INSERT ... ON CONFLICT (fideid) DO UPDATE SET ...`
- Batch size: 5000 records per transaction

## Implementation Phases

### Phase 1: Download & Extract
- `download_fide_xml()`: httpx streaming download to temp file
- `extracted_xml_tempfile()`: Extract first XML from ZIP
- Handle `_foa.xml` files (skip, prefer standard list)

### Phase 2: Parse
- `iterparse` with event-driven processing
- Extract: fideid, name, country, sex, title, ratings (std/rpd/blz), games, flags, birthday, foa_title, foa_rating
- Handle namespace variations and tag naming differences

### Phase 3: Upsert
- Batch accumulation (5000 records)
- PostgreSQL `ON CONFLICT DO UPDATE` for idempotency
- Optional FIDE ID filter (parse all, upsert matching)

### Phase 4: Export
- JSON export with timestamp
- CSV export with timestamp
- Per-country export (split by federation code)

## Key Decisions
- **Streaming over in-memory**: 48MB ZIP -> ~200MB XML, streaming keeps memory low
- **iterparse over DOM**: Event-driven parsing, clear elements after processing
- **Batch size 5000**: Balance between transaction overhead and memory usage
- **ON CONFLICT upsert**: PostgreSQL native idempotency, no SELECT-before-INSERT
