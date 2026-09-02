from typing import Any

import httpx
from fastapi import FastAPI

from backend.api import jobs
from backend.config import settings

app = FastAPI(
    title="SatQuery AI API",
    description="SIH26167 SatQuery backend for Agentic Orchestration",
    version="1.0.0",
)

app.include_router(jobs.router)


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
    except Exception as exc:
        postgres = {"status": "unreachable", "error": str(exc)}

    return {
        "status": "ok",
        "router_model": settings.OLLAMA_ROUTER_MODEL,
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
        "available": available,
        "ollama": ollama_status,
    }
