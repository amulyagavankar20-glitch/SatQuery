import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from backend.schemas import JobCreate, JobResponse, RouteRequest, RouteResponse
from backend.session import create_session, get_session
from backend.services.router import route_query_with_qwen
from backend.agents.graph import run_graph

router = APIRouter()

@router.post("/ingest", response_model=Dict[str, Any])
async def ingest_job(manifest: Dict[str, Any]):
    """
    Ingest a new job request and return a job_id.
    """
    job_id = str(uuid.uuid4())
    return {"job_id": job_id, "status": "ingested"}


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
    session = create_session(
        session_id=job.session_id,
        job_id=job.project_id or uuid.uuid4(),
        query=job.query,
        input_mode=job.input_mode,
        task=job.task
    )
    
    # Example background task execution logic will be added here
    background_tasks.add_task(run_graph, session.session_id)

    return {"session_id": session.session_id, "job_id": session.job_id, "status": "running"}


@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_job(job_id: str):
    """
    Get job status and results.
    """
    session = get_session(job_id)
    if not session:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "session_id": session.session_id,
        "job_id": session.job_id,
        "status": session.status,
        "traces": session.traces,
        "artifacts": session.artifacts
    }
