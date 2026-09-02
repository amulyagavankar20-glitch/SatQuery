"""Qwen2.5-3B query router service used by the FastAPI /route endpoint."""

from fastapi import HTTPException

from backend.agents.router import QwenRouter, QwenRouterError
from backend.schemas import RouteRequest, RouteResponse


async def route_query_with_qwen(request: RouteRequest) -> RouteResponse:
    """Map a user query + raster manifest to a constrained routing plan."""
    router = QwenRouter()
    try:
        return await router.route(request)
    except QwenRouterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
