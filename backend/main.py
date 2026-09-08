from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from backend.api import jobs
from backend.api.v1 import auth, query, assets
from backend.config import settings
from backend.middleware.request_tracking import RequestTrackingMiddleware
from backend.services.model_slotting import model_slot_registry

app = FastAPI(
    title="SatQuery AI API",
    description="SIH26167 SatQuery backend for Agentic Orchestration",
    version="1.0.0",
)

app.add_middleware(RequestTrackingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(auth.router)
app.include_router(query.router)
app.include_router(assets.router)


@app.get("/health")
def health_check() -> dict[str, Any]:
    ollama_status = "unreachable"
    try:
        response = httpx.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
        ollama_status = "ok"
    except (httpx.HTTPError, Exception):
        ollama_status = "unreachable"

    postgres: dict[str, Any] = {"status": "unreachable"}
    try:
        from backend.database import check_db_connection
        postgres = check_db_connection()
    except (ImportError, SQLAlchemyError, Exception) as exc:
        postgres = {"status": "unreachable", "error": str(exc)}

    slots = model_slot_registry.get_slot_statuses()
    all_ready = any(s.status == "ready" for s in slots)

    return {
        "status": "ok",
        "router_model": settings.OLLAMA_ROUTER_MODEL,
        "talking_vlm": settings.TALKING_VLM_MODEL,
        "ollama": ollama_status,
        "postgres": postgres,
        "model_slots_count": len(slots),
        "slotted_ready": all_ready,
    }


@app.get("/models")
def list_models() -> dict[str, Any]:
    available: list[str] = []
    ollama_status = "ok"
    try:
        response = httpx.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
        available = [m.get("name", "") for m in response.json().get("models", [])]
    except (httpx.HTTPError, Exception) as exc:
        ollama_status = str(exc)

    slots = model_slot_registry.get_slot_statuses()
    router_ready = settings.OLLAMA_ROUTER_MODEL in available or any(
        s.slot_id == "router" and s.status == "ready" for s in slots
    )

    return {
        "router_model": settings.OLLAMA_ROUTER_MODEL,
        "router_ready": router_ready,
        "talking_vlm": settings.TALKING_VLM_MODEL,
        "talking_vlm_backend": settings.TALKING_VLM_BACKEND,
        "available": available,
        "ollama": ollama_status,
        "model_slots": [s.model_dump() for s in slots],
    }
