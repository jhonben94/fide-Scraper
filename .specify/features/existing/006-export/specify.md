# Feature: Data Export

## Overview
Export FIDE player data to JSON and CSV formats. Supports full export (up to 100K players) and per-country split exports.

## Key Details
- Module: `src/exporter.py`
- `export_to_json()`: Timestamped JSON file with all player fields
- `export_to_csv()`: Timestamped CSV file
- `export_by_country()`: Players grouped into separate JSON files by federation code under `by_country/` subdirectory
- Max 100,000 players per export
- Output directory: configurable via `EXPORT_PATH` env var
- Triggered automatically after base import (can be disabled with `--no-json` / `--no-csv`)
