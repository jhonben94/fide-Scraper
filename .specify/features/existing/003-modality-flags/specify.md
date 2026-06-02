# Feature: Modality Flags Import

## Overview
Downloads all three per-modality archive ZIPs for a period and extracts per-player `flag` values into `flag_std`, `flag_rpd`, `flag_blz` columns.

## Key Details
- Module: `src/importer_modality_flags.py`
- Admin endpoint: `POST /admin/import-modality-flags`
- Downloads std + rpd + blz archive ZIPs for latest period
- Extracts `flag` field per player per modality
- Batch-updates via `UPDATE ... FROM unnest()` for efficiency
- Auto-resolves period from `MAX(period)` in `player_rating_history`
- Columns added via Flyway V20 (backend) and auto-migration (scraper startup)
