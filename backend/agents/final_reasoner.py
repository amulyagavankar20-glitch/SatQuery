"""Final evidence-grounded Qwen reasoning node support."""

from __future__ import annotations

import json
from typing import Any

import httpx

from backend.config import settings


def synthesize_final_answer(query: str, evidence: list[dict[str, Any]]) -> str:
    """Ask the same configured Qwen model to explain specialist evidence.

    This intentionally sends evidence, not raw specialist instructions.  If the
    local Qwen endpoint is unavailable, callers receive a controlled error and
    must not present a fabricated final answer.
    """
    prompt = (
        "You are SatQuery's final evidence reasoner. Answer the analyst using only "
        "the structured specialist evidence below. State uncertainty and do not invent "
        "objects, measurements, locations, or model results.\n\n"
        f"Question: {query}\n\nEvidence:\n{json.dumps(evidence, default=str)}\n\n"
        "Return a concise answer followed by an Evidence section."
    )
    endpoint = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": settings.OLLAMA_ROUTER_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "top_k": 1},
    }
    try:
        response = httpx.post(endpoint, json=payload, timeout=settings.OLLAMA_TIMEOUT_SECONDS)
        response.raise_for_status()
        answer = str(response.json().get("response", "")).strip()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Final Qwen reasoning is unavailable: {exc}") from exc
    if not answer:
        raise RuntimeError("Final Qwen reasoning returned an empty answer.")
    return answer
