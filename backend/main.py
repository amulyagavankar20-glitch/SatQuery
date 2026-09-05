from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from backend.api import jobs
from backend.api.v1 import auth, query, assets
from backend.config import settings
from backend.middleware.request_tracking import RequestTrackingMiddleware
import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter

app = FastAPI(
    title="SatQuery AI API",
    description="SIH26167 SatQuery backend for Agentic Orchestration",
    version="1.0.0",
)

@app.on_event("startup")
async def startup():
    redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis_client)

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
        response = httpx.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=5.0)
        response.raise_for_status()
        ollama_status = "ok"
    except httpx.HTTPError:
        ollama_status = "unreachable"

    postgres: dict[str, Any] = {"status": "unreachable"}
    try:
        from backend.database import check_db_connection
        postgres = check_db_connection()
    except (ImportError, SQLAlchemyError) as exc:
        postgres = {"status": "unreachable", "error": str(exc)}

    return {
        "status": "ok",
        "router_model": settings.OLLAMA_ROUTER_MODEL,
        "talking_vlm": settings.TALKING_VLM_MODEL,
        "ollama": ollama_status,
        "postgres": postgres,
    }


@app.get("/models")
def list_models() -> dict[str, Any]:
    available: list[str] = []
    ollama_status = "ok"
    try:
        response = httpx.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=5.0)
        response.raise_for_status()
        available = [m.get("name", "") for m in response.json().get("models", [])]
    except httpx.HTTPError as exc:
        ollama_status = str(exc)
    return {
        "router_model": settings.OLLAMA_ROUTER_MODEL,
        "router_ready": settings.OLLAMA_ROUTER_MODEL in available,
        "talking_vlm": settings.TALKING_VLM_MODEL,
        "talking_vlm_backend": settings.TALKING_VLM_BACKEND,
        "available": available,
        "ollama": ollama_status,
    }
