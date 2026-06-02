# Feature: Historical Rating Import

## Overview
Downloads per-period FIDE archive ZIPs (standard + rapid + blitz separately), processes multiple months of historical data, and upserts into `fide.player_rating_history`. Supports rolling window, current-year scope, country filtering, club affiliate filtering, and checkpoint-based resume.

## Functional Requirements

### FR-001: Multi-Period Download
- **Given** a history import is triggered with a time scope
- **When** the downloader runs
- **Then** per-period archive ZIPs are downloaded for each month in scope
- **And** standard, rapid, and blitz lists are downloaded separately

### FR-002: Three-Pass Upsert
- **Given** a period's data from 3 modality ZIPs
- **When** the importer processes them
- **Then** three passes upsert with `COALESCE` to merge modalities
- **And** standard ratings are set first, then rapid and blitz fill in

### FR-003: Time Scopes
- **Given** the import configuration
- **When** `--current-year` is used
- **Then** only months in the current calendar year are processed
- **When** `--months N` is used
- **Then** the last N months (rolling window) are processed

### FR-004: Country Filtering
- **Given** `--country PAR` is specified
- **When** the import processes records
- **Then** only players from the specified federation(s) are written to the database

### FR-005: Club Affiliate Filtering
- **Given** `--include-club-affiliates` is specified
- **When** the import processes records
- **Then** only players with a `current_club_id` in the `player` table are included

### FR-006: Checkpoint Resume
- **Given** `--skip-completed` is specified
- **When** the import encounters a period already in `history_import_checkpoint`
- **Then** that period is skipped
- **And** FIDE ID lists use a stable SHA-256 hash as checkpoint key

### FR-007: FIDE ID List Import
- **Given** `--fide-id 123 --fide-id 456` or `--fide-ids-file ./ids.txt`
- **When** the import runs
- **Then** only specified players are imported across all periods
- **And** the checkpoint key is `fides:{sha256}` for stable identification

## Data Model
- Input: FIDE archive ZIPs per period (standard + rapid + blitz)
- Output: `fide.player_rating_history` (fideid, period, std/rpd/blz ratings)
- Checkpoint: `fide.history_import_checkpoint` (period, filter_key, completed_at)

## Success Criteria
- SC-001: 12-month import completes within 30 minutes for PAR federation
- SC-002: Checkpoint prevents re-processing completed periods
- SC-003: Three-pass COALESCE correctly merges all 3 modalities
- SC-004: FIDE ID list imports use stable SHA-256 checkpoint keys

## Edge Cases
- EC-001: Missing archive for a period - skip with warning, continue
- EC-002: Partial data (only standard, no rapid/blitz) - COALESCE handles nulls
- EC-003: Checkpoint exists but data was deleted - use `--skip-completed=false` to reimport
