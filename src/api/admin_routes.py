"""Rutas administrativas para ejecutar imports on-demand."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator

from src.importer import run_import
from src.importer_history import run_daily_change_sync, run_import_history
from src.importer_modal_flags import run_import_modality_flags

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin", tags=["admin"])

_jobs_lock = threading.Lock()
_active_job_id: str | None = None
_jobs: dict[str, dict[str, Any]] = {}

_MAX_FIDE_IDS_PER_REQUEST = 50_000


class ImportRequest(BaseModel):
    """Parámetros para importación mensual/base (`fide.players` desde el XML FIDE)."""

    period: Optional[str] = Field(
        default=None,
        description="Fecha opcional YYYY-MM-DD para listas históricas puntuales",
    )
    export_json: bool = Field(default=True, description="Exportar salida JSON (solo filas importadas si usás fide_ids)")
    export_csv: bool = Field(default=True, description="Exportar salida CSV (solo filas importadas si usás fide_ids)")
    countries: Optional[list[str]] = Field(
        default=None,
        description="Códigos federación FIDE (ej. PAR); solo esos jugadores se persisten en fide.players",
    )
    include_club_affiliates: bool = Field(
        default=False,
        description="Incluye también jugadores con club asignado en la tabla local `player` (OR con "
        "countries), ej. extranjeros afiliados a un club paraguayo",
    )
    fide_ids: Optional[list[int]] = Field(
        default=None,
        max_length=_MAX_FIDE_IDS_PER_REQUEST,
        description="Solo actualizar estos FIDE ID en fide.players (el ZIP/XML completo se descarga e iguala; "
        "recomendado desactivar export en import masivo de un solo id: export_json/export_csv false).",
    )

    @field_validator("fide_ids", mode="before")
    @classmethod
    def _import_empty_fide_ids_to_none(cls, v):
        if v == []:
            return None
        return v

    @field_validator("fide_ids")
    @classmethod
    def _import_fide_ids_positive(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        if v is None:
            return None
        for x in v:
            if x is None or int(x) <= 0:
                raise ValueError("fide_ids debe contener enteros positivos")
        return v

    @model_validator(mode="after")
    def _exclusive_fide_list_mode(self):
        if self.fide_ids:
            if self.countries:
                raise ValueError("No combinar fide_ids con countries")
            if self.include_club_affiliates:
                raise ValueError("No combinar fide_ids con include_club_affiliates")
        return self


class ImportModalityFlagsRequest(BaseModel):
    """Importar solo flags por modalidad (ZIP archivo STD/RPD/BLZ) para el periodo indicado."""

    period: Optional[str] = Field(
        default=None,
        description="Primer día del mes YYYY-MM-DD (ej. 2026-05-01). Por defecto: MAX(period) en fide.player_rating_history.",
    )


class ImportHistoryRequest(BaseModel):
    """Parámetros para importación histórica."""

    months: int = Field(default=24, ge=1, le=120, description="Meses hacia atrás (modo rolling_months)")
    period_scope: Literal["rolling_months", "current_year"] = Field(
        default="rolling_months",
        description="current_year = solo meses del año calendario en curso",
    )
    period: Optional[str] = Field(
        default=None,
        description="Fecha YYYY-MM-DD (obligatoriamente primer día del mes). Si se proporciona, solo se importa ese período.",
    )
    use_current_files: bool = Field(
        default=False,
        description="Solo válido si se proporciona period. Usa los ZIP actuales (standard/rapid/blitz_rating_list_xml.zip).",
    )
    countries: Optional[list[str]] = Field(
        default=None,
        description="Códigos federación FIDE (ej. PAR); solo esos jugadores se persisten",
    )
    include_club_affiliates: bool = Field(
        default=False,
        description="Incluye también jugadores con club asignado (OR con countries)",
    )
    skip_completed: bool = Field(
        default=False,
        description="Omitir periodos ya en fide.history_import_checkpoint",
    )
    fide_ids: Optional[list[int]] = Field(
        default=None,
        max_length=_MAX_FIDE_IDS_PER_REQUEST,
        description="Solo estos FIDE ID (excluye countries / include_club_affiliates)",
    )

    @field_validator("fide_ids", mode="before")
    @classmethod
    def _empty_fide_ids_to_none(cls, v):
        if v == []:
            return None
        return v

    @field_validator("fide_ids")
    @classmethod
    def _fide_ids_positive(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        if v is None:
            return None
        for x in v:
            if x is None or int(x) <= 0:
                raise ValueError("fide_ids debe contener enteros positivos")
        return v

    @model_validator(mode="after")
    def _period_must_be_first_day(self):
        if self.period is not None:
            try:
                parsed = date.fromisoformat(self.period)
                if parsed.day != 1:
                    raise ValueError("period debe ser el primer día del mes (YYYY-MM-01)")
            except ValueError as e:
                if "YYYY-MM-01" in str(e):
                    raise
                raise ValueError("period debe tener formato YYYY-MM-DD") from e
        return self

    @model_validator(mode="after")
    def _use_current_requires_period(self):
        if self.use_current_files and not self.period:
            raise ValueError("use_current_files=true requiere period")
        return self

    @model_validator(mode="after")
    def _exclusive_fide_list_mode(self):
        if self.fide_ids:
            if self.countries:
                raise ValueError("No combinar fide_ids con countries")
            if self.include_club_affiliates:
                raise ValueError("No combinar fide_ids con include_club_affiliates")
        return self


class DailySyncRequest(BaseModel):
    """Parámetros para la sincronización diaria basada en cambios (`fide.player_rating_history`)."""

    period: Optional[str] = Field(
        default=None,
        description="Fecha YYYY-MM-DD a usar como period de las filas de cambio (default: hoy)",
    )
    countries: Optional[list[str]] = Field(
        default=None,
        description="Códigos federación FIDE (ej. PAR); solo esos jugadores se evalúan/persisten",
    )
    include_club_affiliates: bool = Field(
        default=False,
        description="Incluye también jugadores con club asignado (OR con countries)",
    )
    fide_ids: Optional[list[int]] = Field(
        default=None,
        max_length=_MAX_FIDE_IDS_PER_REQUEST,
        description="Solo estos FIDE ID (excluye countries / include_club_affiliates)",
    )

    @field_validator("fide_ids", mode="before")
    @classmethod
    def _empty_fide_ids_to_none(cls, v):
        if v == []:
            return None
        return v

    @field_validator("fide_ids")
    @classmethod
    def _fide_ids_positive(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        if v is None:
            return None
        for x in v:
            if x is None or int(x) <= 0:
                raise ValueError("fide_ids debe contener enteros positivos")
        return v

    @model_validator(mode="after")
    def _exclusive_fide_list_mode(self):
        if self.fide_ids:
            if self.countries:
                raise ValueError("No combinar fide_ids con countries")
            if self.include_club_affiliates:
                raise ValueError("No combinar fide_ids con include_club_affiliates")
        return self


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_view(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job["job_id"],
        "type": job["type"],
        "status": job["status"],
        "created_at": job["created_at"],
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "request": job.get("request"),
        "result": job.get("result"),
        "error": job.get("error"),
    }


def _queue_job(job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    global _active_job_id
    with _jobs_lock:
        if _active_job_id is not None:
            current = _jobs.get(_active_job_id)
            if current and current.get("status") in {"queued", "running"}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un import en ejecución (job_id={_active_job_id})",
                )

        job_id = uuid.uuid4().hex
        job = {
            "job_id": job_id,
            "type": job_type,
            "status": "queued",
            "created_at": _utc_now_iso(),
            "started_at": None,
            "finished_at": None,
            "request": payload,
            "result": None,
            "error": None,
        }
        _jobs[job_id] = job
        _active_job_id = job_id
        return job


def _run_job(job_id: str) -> None:
    global _active_job_id
    with _jobs_lock:
        job = _jobs[job_id]
        job["status"] = "running"
        job["started_at"] = _utc_now_iso()

    try:
        if job["type"] == "import":
            req = job["request"]
            raw_catalog = req.get("fide_ids")
            fid_catalog: frozenset[int] | None = None
            if raw_catalog:
                fid_catalog = frozenset(int(x) for x in raw_catalog if x is not None)
            raw_countries = req.get("countries")
            codes = None
            if raw_countries and not fid_catalog:
                codes = frozenset(str(c).strip().upper() for c in raw_countries if str(c).strip())
            result = run_import(
                period=req.get("period"),
                export_json=bool(req.get("export_json", True)),
                export_csv=bool(req.get("export_csv", True)),
                fide_ids=fid_catalog,
                country_codes=codes,
                include_club_affiliates=bool(req.get("include_club_affiliates", False)),
            )
        elif job["type"] == "import-history":
            req = job["request"]
            months = int(req.get("months", 24))
            period_scope = req.get("period_scope") or "rolling_months"
            if period_scope not in ("rolling_months", "current_year"):
                period_scope = "rolling_months"
            raw_fide = req.get("fide_ids")
            fid: frozenset[int] | None = None
            if raw_fide:
                fid = frozenset(int(x) for x in raw_fide if x is not None)
            raw_countries = req.get("countries")
            codes = None
            if raw_countries and not fid:
                codes = frozenset(str(c).strip().upper() for c in raw_countries if str(c).strip())
            result = run_import_history(
                months=months,
                period_scope=period_scope,
                country_codes=codes,
                include_club_affiliates=bool(req.get("include_club_affiliates", False)),
                skip_completed=bool(req.get("skip_completed", False)),
                fide_ids=fid,
                explicit_period=req.get("period"),
                use_current_files=bool(req.get("use_current_files", False)),
            )
        elif job["type"] == "import-modality-flags":
            req = job["request"]
            result = run_import_modality_flags(period=req.get("period"))
        elif job["type"] == "daily-change-sync":
            req = job["request"]
            raw_fide = req.get("fide_ids")
            fid: frozenset[int] | None = None
            if raw_fide:
                fid = frozenset(int(x) for x in raw_fide if x is not None)
            raw_countries = req.get("countries")
            codes = None
            if raw_countries and not fid:
                codes = frozenset(str(c).strip().upper() for c in raw_countries if str(c).strip())
            req_period = req.get("period")
            result = run_daily_change_sync(
                country_codes=codes,
                include_club_affiliates=bool(req.get("include_club_affiliates", False)),
                fide_ids=fid,
                period=date.fromisoformat(req_period) if req_period else None,
            )
        else:
            raise RuntimeError(f"Tipo de job no soportado: {job['type']}")

        with _jobs_lock:
            job["status"] = "success"
            job["result"] = result
            job["finished_at"] = _utc_now_iso()
    except Exception as exc:
        logger.exception("Fallo job administrativo %s", job_id)
        with _jobs_lock:
            job["status"] = "failed"
            job["error"] = str(exc)
            job["finished_at"] = _utc_now_iso()
    finally:
        with _jobs_lock:
            if _active_job_id == job_id:
                _active_job_id = None


@admin_router.post("/import", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
def trigger_import(payload: ImportRequest, background_tasks: BackgroundTasks):
    """Dispara importación del XML base (`fide.players`) en background; opcionalmente solo `fide_ids`."""
    job = _queue_job(
        job_type="import",
        payload={
            "period": payload.period,
            "export_json": payload.export_json,
            "export_csv": payload.export_csv,
            "countries": payload.countries,
            "include_club_affiliates": payload.include_club_affiliates,
            "fide_ids": payload.fide_ids,
        },
    )
    background_tasks.add_task(_run_job, job["job_id"])
    return _job_view(job)


@admin_router.post("/import-history", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
def trigger_import_history(payload: ImportHistoryRequest, background_tasks: BackgroundTasks):
    """Dispara importación de `fide.player_rating_history` en background; opcionalmente solo `fide_ids`."""
    job = _queue_job(
        job_type="import-history",
        payload={
            "months": payload.months,
            "period_scope": payload.period_scope,
            "period": payload.period,
            "use_current_files": payload.use_current_files,
            "countries": payload.countries,
            "include_club_affiliates": payload.include_club_affiliates,
            "skip_completed": payload.skip_completed,
            "fide_ids": payload.fide_ids,
        },
    )
    background_tasks.add_task(_run_job, job["job_id"])
    return _job_view(job)



@admin_router.post("/import-modality-flags", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
def trigger_import_modality_flags(payload: ImportModalityFlagsRequest, background_tasks: BackgroundTasks):
    """Actualiza flag_std, flag_rpd, flag_blz desde los tres XML de archivo FIDE del periodo."""
    job = _queue_job(
        job_type="import-modality-flags",
        payload={"period": payload.period},
    )
    background_tasks.add_task(_run_job, job["job_id"])
    return _job_view(job)


@admin_router.post("/sync-daily", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
def trigger_daily_sync(payload: DailySyncRequest, background_tasks: BackgroundTasks):
    """Dispara la sincronización diaria basada en cambios de `fide.player_rating_history` en background."""
    job = _queue_job(
        job_type="daily-change-sync",
        payload={
            "period": payload.period,
            "countries": payload.countries,
            "include_club_affiliates": payload.include_club_affiliates,
            "fide_ids": payload.fide_ids,
        },
    )
    background_tasks.add_task(_run_job, job["job_id"])
    return _job_view(job)


@admin_router.get("/jobs/{job_id}", response_model=dict)
def get_job_status(job_id: str):
    """Obtiene estado y resultado de un job administrativo."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")
        return _job_view(job)
