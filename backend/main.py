from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from backend.api import jobs
from backend.api.v1 import auth
from backend.config import settings
from backend.middleware.request_tracking import RequestTrackingMiddleware
from backend.services.model_slotting import model_slot_registry
from src.logger import logging

app = FastAPI(
    title="SatQuery AI API",
    description="SatQuery AI Backend for Agentic Orchestration",
    version="1.0.0",
)

@app.on_event("startup")
async def startup():
    try:
        from backend.database import SessionLocal
        from backend.services.tool_catalog import seed_tool_registry
        db = SessionLocal()
        try:
            changed = seed_tool_registry(db)
            logging.info("[Startup] Seeded tool registry (updated: %s)", changed or "none")
        finally:
            db.close()
    except Exception as exc:
        logging.error("[Startup] Failed to seed tool registry: %s", exc, exc_info=True)

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


@app.get("/health")
def health_check() -> dict[str, Any]:
    openrouter_status = "configured" if settings.OPENROUTER_API_KEY else "missing_key"

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
        "router_model": settings.VLM_MODEL,
        "vlm_model": settings.VLM_MODEL,
        "vlm_provider": settings.VLM_PROVIDER,
        "openrouter": openrouter_status,
        "talking_vlm": settings.TALKING_VLM_MODEL,
        "postgres": postgres,
        "model_slots_count": len(slots),
        "slotted_ready": all_ready,
    }


@app.get("/models")
def list_models() -> dict[str, Any]:
    slots = model_slot_registry.get_slot_statuses()
    router_ready = bool(settings.OPENROUTER_API_KEY) or any(
        s.slot_id == "router" and s.status == "ready" for s in slots
    )

    return {
        "router_model": settings.VLM_MODEL,
        "router_ready": router_ready,
        "vlm_model": settings.VLM_MODEL,
        "vlm_provider": settings.VLM_PROVIDER,
        "openrouter_configured": bool(settings.OPENROUTER_API_KEY),
        "talking_vlm": settings.TALKING_VLM_MODEL,
        "talking_vlm_backend": settings.TALKING_VLM_BACKEND,
        "model_slots": [s.model_dump() for s in slots],
    }
