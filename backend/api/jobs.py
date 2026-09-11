import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from backend.agents.graph import run_graph
from backend.exceptions import UnsupportedFormatError
from backend.schemas import JobCreate, JobView, RouteRequest, RouteResponse
from backend.services.ingest import ingest_rasters
from backend.services.job_view import (
    footprint_geojson,
    footprint_kml,
    get_job_view,
    resolve_asset_preview_path,
    resolve_composite_path,
    resolve_vv_path,
    resolve_vh_path,
    resolve_overlay_path,
    resolve_tile_path,
    safe_job_file,
)
from backend.services.persistence import create_job_record, persist_assets
from backend.services.router import route_query_with_qwen
from backend.session import create_session, get_session_by_job_id

router = APIRouter()

@router.post("/ingest")
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
                "modality": a.get("modality"),
                "sensor": a.get("sensor"),
                "width": a.get("width"),
                "height": a.get("height"),
                "crs": a.get("crs"),
                "bounds_wgs84": a.get("bounds_wgs84"),
                "preview_url": f"/jobs/{session.job_id}/artifacts/assets/{idx}",
            }
            for idx, a in enumerate(assets)
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
        if job.active_slot:
            session.metadata["active_slot"] = job.active_slot
        if job.mode:
            session.metadata["mode"] = job.mode
        if job.active_filename:
            session.metadata["active_filename"] = job.active_filename
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


@router.get("/jobs/{job_id}", response_model=JobView)
async def get_job(job_id: str) -> JobView:
    """Canonical JobView for the Analyze UI (docs/api-spec.md)."""
    view = get_job_view(job_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return view


@router.api_route("/jobs/{job_id}/artifacts/composite", methods=["GET", "HEAD"])
async def get_composite(job_id: str, slot: str | None = None, index: int = 0):
    if get_job_view(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    idx = 1 if slot == "T2" else index
    path = resolve_asset_preview_path(job_id, idx) if (slot or index > 0) else resolve_composite_path(job_id)
    safe = safe_job_file(job_id, path) if path else None
    if safe is None:
        raise HTTPException(status_code=404, detail="Composite not ready")
    return FileResponse(safe, media_type="image/png")


@router.api_route("/jobs/{job_id}/artifacts/assets/{asset_index}", methods=["GET", "HEAD"])
async def get_asset_preview(job_id: str, asset_index: int = 0):
    if get_job_view(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = resolve_asset_preview_path(job_id, asset_index)
    safe = safe_job_file(job_id, path) if path else None
    if safe is None:
        raise HTTPException(status_code=404, detail=f"Asset {asset_index} preview not ready")
    return FileResponse(safe, media_type="image/png")


@router.get("/jobs/{job_id}/artifacts/vv")
async def get_vv_artifact(job_id: str):
    if get_job_view(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = resolve_vv_path(job_id)
    safe = safe_job_file(job_id, path) if path else None
    if safe is None:
        raise HTTPException(status_code=404, detail="VV visualization not ready")
    return FileResponse(safe, media_type="image/png")


@router.get("/jobs/{job_id}/artifacts/vh")
async def get_vh_artifact(job_id: str):
    if get_job_view(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = resolve_vh_path(job_id)
    safe = safe_job_file(job_id, path) if path else None
    if safe is None:
        raise HTTPException(status_code=404, detail="VH visualization not ready")
    return FileResponse(safe, media_type="image/png")


@router.get("/jobs/{job_id}/artifacts/overlay")
async def get_overlay_artifact(job_id: str):
    if get_job_view(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = resolve_overlay_path(job_id)
    safe = safe_job_file(job_id, path) if path else None
    if safe is None:
        raise HTTPException(status_code=404, detail="Overlay not ready")
    return FileResponse(safe, media_type="image/png")


@router.get("/jobs/{job_id}/artifacts/tiles/{index}")
async def get_tile(job_id: str, index: int):
    if get_job_view(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = resolve_tile_path(job_id, index)
    safe = safe_job_file(job_id, path) if path else None
    if safe is None:
        raise HTTPException(status_code=404, detail="Tile not found")
    return FileResponse(safe, media_type="image/png", filename=safe.name)


@router.get("/jobs/{job_id}/export.geojson")
async def export_geojson(job_id: str):
    geo = footprint_geojson(job_id)
    if geo is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return geo


@router.get("/jobs/{job_id}/export.kml")
async def export_kml(job_id: str):
    kml = footprint_kml(job_id)
    if kml is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return Response(content=kml, media_type="application/vnd.google-earth.kml+xml")


@router.get("/jobs/{job_id}/report.pdf")
async def export_pdf(job_id: str):
    view = get_job_view(job_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        from backend.services.pdf_report import generate_job_pdf
        pdf_bytes = generate_job_pdf(view)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=satquery_report_{job_id}.pdf"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to render PDF: {exc}") from exc
