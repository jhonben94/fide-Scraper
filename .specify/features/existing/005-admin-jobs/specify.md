# Feature: Admin Job System

## Overview
Async background job execution for admin operations (imports). Status tracking with queued/running/success/failed states. Single-job concurrency guard prevents overlapping imports.

## Key Details
- Endpoints: `POST /admin/import`, `POST /admin/import-history`, `POST /admin/import-modality-flags`
- Status query: `GET /admin/jobs/{job_id}`
- States: `queued` -> `running` -> `success` | `failed`
- Concurrency: 409 Conflict if a job is already running
- Security: Mandatory API key + IP/CIDR allowlist (`FIDE_SCRAPER_ADMIN_ALLOWLIST`)
- Jobs run via FastAPI `BackgroundTasks` or asyncio tasks
