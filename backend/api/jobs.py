import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from backend.agents.graph import run_graph
from backend.exceptions import UnsupportedFormatError
from backend.schemas import JobCreate, RouteRequest, RouteResponse
from backend.services.ingest import ingest_rasters
from backend.services.persistence import create_job_record, load_job, persist_assets
from backend.services.router import route_query_with_qwen
from backend.session import create_session, get_session_by_job_id

router = APIRouter()

@router.post("/ingest", response_model=dict[str, Any])
async def ingest_job(
    files: list[UploadFile] = File(..., description="GeoTIFF rasters"),
    query: str = Form(""),
    sensor: str | None = Form(None),
):
    """Save uploaded GeoTIFFs, classify input configuration, persist assets."""
    try:
        session, classification, assets = ingest_rasters(files, query=query, sensor=sensor)
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ingest failed: {exc}") from exc

    create_job_record(
        job_id=session.job_id,
        session_id=session.session_id,
        query=session.query or "INGESTED",
        input_mode=session.input_mode or "UNKNOWN",
        task=session.task,
        status=session.status,
    )
    persist_assets(session.job_id, assets)

    return {
        "job_id": session.job_id,
        "session_id": session.session_id,
        "status": session.status,
        "input_class": session.input_mode,
        "valid": classification.valid,
        "validation_messages": classification.validation_messages,
        "refusal_reason": classification.refusal_reason,
        "assets": [
            {
                "filename": a.get("filename"),
                "file_path": a.get("file_path"),
                "modality": a.get("modality"),
                "sensor": a.get("sensor"),
                "width": a.get("width"),
                "height": a.get("height"),
                "crs": a.get("crs"),
                "bounds_wgs84": a.get("bounds_wgs84"),
            }
            for a in assets
        ],
    }


@router.post("/route", response_model=RouteResponse)
async def route_job(request: RouteRequest):
    """
    Route the job and return the plan.
    """
    return await route_query_with_qwen(request)


@router.post("/run", status_code=202)
async def run_job(job: JobCreate, background_tasks: BackgroundTasks):
    """
    Create a session and start the LangGraph workflow in the background.
    """
    session = None
    if job.job_id is not None:
        session = get_session_by_job_id(job.job_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Ingested job not found. POST /ingest first.")
        session.query = job.query
        if job.input_mode:
            session.input_mode = job.input_mode
        if job.task and job.task != "UNROUTED":
            session.task = job.task
        session.status = "running"
    else:
        if not job.input_mode:
            raise HTTPException(status_code=400, detail="input_mode is required when job_id is omitted.")
        session = create_session(
            session_id=job.session_id,
            job_id=uuid.uuid4(),
            query=job.query,
            input_mode=job.input_mode,
            task=job.task,
        )

    create_job_record(
        job_id=session.job_id,
        session_id=session.session_id,
        query=session.query,
        input_mode=session.input_mode,
        task=session.task,
        project_id=job.project_id,
        status="running",
    )

    async def _run() -> None:
        await asyncio.to_thread(run_graph, session.session_id)

    background_tasks.add_task(_run)

    return {"session_id": session.session_id, "job_id": session.job_id, "status": "running"}


@router.get("/jobs/{job_id}", response_model=dict[str, Any])
async def get_job(job_id: str):
    """
    Get job status and results.
    """
    session = get_session_by_job_id(job_id)
    if session:
        return {
            "session_id": session.session_id,
            "job_id": session.job_id,
            "status": session.status,
            "task": session.task,
            "route": session.route,
            "traces": session.traces,
            "artifacts": session.artifacts,
            "errors": session.errors,
            "input_class": session.input_mode,
            "preprocessing": session.preprocessing_result,
        }

    persisted = load_job(job_id)
    if persisted:
        return persisted

    raise HTTPException(status_code=404, detail="Job not found")
