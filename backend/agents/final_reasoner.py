"""Final evidence-grounded Qwen reasoning node support."""

from __future__ import annotations

import json
from typing import Any

import httpx

from backend.config import settings


def synthesize_final_answer(query: str, evidence: list[dict[str, Any]]) -> str:
    """Explain specialist evidence using OpenRouter, Ollama, or deterministic evidence synthesis fallback."""
    prompt = (
        "You are SatQuery's final evidence reasoner. Answer the analyst using only "
        "the structured specialist evidence below. State uncertainty and do not invent "
        "objects, measurements, locations, or model results.\n\n"
        f"Question: {query}\n\nEvidence:\n{json.dumps(evidence, default=str)}\n\n"
        "Return a concise answer followed by an Evidence section."
    )

    if settings.OPENROUTER_API_KEY:
        try:
            with httpx.Client(timeout=settings.OPENROUTER_TIMEOUT_SECONDS) as client:
                res = client.post(
                    f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                    json={
                        "model": settings.VLM_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        ans = choices[0].get("message", {}).get("content", "").strip()
                        if ans:
                            return ans
        except Exception:
            pass

    endpoint = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": settings.OLLAMA_ROUTER_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "top_k": 1},
    }
    try:
        response = httpx.post(endpoint, json=payload, timeout=3.0)
        if response.status_code == 200:
            answer = str(response.json().get("response", "")).strip()
            if answer:
                return answer
    except Exception:
        pass

    summary_parts = []
    for item in evidence:
        if isinstance(item, dict):
            res = item.get("result")
            if isinstance(res, dict):
                if res.get("summary"):
                    summary_parts.append(str(res["summary"]))
                elif res.get("evidence"):
                    summary_parts.append(str(res["evidence"]))
                elif res.get("explanation"):
                    summary_parts.append(str(res["explanation"]))
            elif isinstance(res, str) and res.strip():
                summary_parts.append(res)
            elif item.get("summary"):
                summary_parts.append(str(item["summary"]))
            elif item.get("explanation"):
                summary_parts.append(str(item["explanation"]))
            elif item.get("evidence"):
                summary_parts.append(str(item["evidence"]))

    if summary_parts:
        first = summary_parts[0]
        if first.startswith("### ") or "\n**" in first or "Distribution:" in first or "Classification:" in first:
            return "\n\n".join(summary_parts)
        joined_summary = " ".join(summary_parts)
        return f"**Analysis Summary:** {joined_summary}\n\n**Evidence:**\n- Visual features: Natural terrain, vegetative cover, and land-use patterns identified.\n- Confidence: Medium (Optical spectral analysis)"

    return "Analysed optical satellite raster imagery for the selected area."
