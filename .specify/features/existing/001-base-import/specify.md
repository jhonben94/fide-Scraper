# Feature: Base/Monthly FIDE Import

## Overview
Downloads the official FIDE combined XML ZIP (~48MB), streams and parses player data, and batch-upserts into PostgreSQL (`fide.players` table). Supports optional JSON/CSV export and selective import by FIDE ID.

## Functional Requirements

### FR-001: Download FIDE XML
- **Given** an import is triggered
- **When** the downloader runs
- **Then** the FIDE ZIP is streamed to disk (memory-efficient)
- **And** the first XML is extracted from the ZIP (avoids `_foa.xml`)

### FR-002: Stream Parse XML
- **Given** an extracted XML file
- **When** the parser processes it
- **Then** `<player>` elements are parsed via `iterparse` (event-driven, streaming)
- **And** elements are cleared after parsing to free memory
- **And** multiple FIDE tag naming conventions are handled (e.g., `rating`/`srtng`, `games`/`sgm`)

### FR-003: Batch Upsert
- **Given** parsed player records
- **When** the importer processes them
- **Then** records are upserted in batches of 5000
- **And** `ON CONFLICT DO UPDATE` by `fideid` ensures idempotency
- **And** all 18+ player fields are updated

### FR-004: Selective Import
- **Given** a list of FIDE IDs (up to 50,000)
- **When** the import runs with `--fide-id` filter
- **Then** the full XML is parsed but only matching IDs are upserted

### FR-005: Export
- **Given** a completed import
- **When** export is enabled (default)
- **Then** up to 100,000 players are exported to timestamped JSON and CSV files

### FR-006: CLI Entry Point
- **Given** a user runs `python -m scripts.run_import`
- **When** optional flags are provided (`--period`, `--no-json`, `--no-csv`)
- **Then** the import pipeline executes end-to-end

## Data Model
- Input: FIDE combined XML ZIP from `ratings.fide.com`
- Output: `fide.players` table (18+ fields per player)
- Export: Timestamped JSON and CSV files in `EXPORT_PATH`

## Success Criteria
- SC-001: Full import completes within 5 minutes for ~300K players
- SC-002: Memory usage stays under 512MB during processing
- SC-003: Re-running the same import produces identical results (idempotent)
- SC-004: Export files are created with timestamps in filename

## Edge Cases
- EC-001: FIDE portal unavailable - download fails with clear error message
- EC-002: XML format changes - parser handles multiple tag naming conventions
- EC-003: Empty XML - import completes with 0 rows, no error
