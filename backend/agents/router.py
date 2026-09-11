"""
SatQuery AI — Agent Query Intent Router

Uses a Vision-Language Model (VLM) via OpenRouter (environment-driven via VLM_MODEL)
to classify user query intent into a structured RouteResponse.
Strictly distinguishes USER INTENT from INPUT CONFIGURATION.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from backend.config import settings
from backend.schemas import RouteRequest, RouteResponse, RouterTask, RouterTool
from backend.services.vlm import (
    VLMClient,
    VLMError,
    get_vlm_client,
)
from src.logger import logging


class RouterError(Exception):
    """Raised when structured routing fails and cannot be recovered."""
    pass


# Backward compatibility alias
QwenRouterError = RouterError


class VLMRouter:
    """
    Text-only query intent classifier powered by VLM via OpenRouter.
    Responsible for distinguishing USER INTENT from INPUT CONFIGURATION.
    """

    def __init__(
        self,
        client: VLMClient | None = None,
        timeout: float | None = None,
    ):
        self.client = client or get_vlm_client()
        self.timeout = timeout if timeout is not None else settings.OPENROUTER_TIMEOUT_SECONDS
        self.response_schema = RouteResponse.model_json_schema()
        self.schema_json = json.dumps(self.response_schema, indent=2)

    def build_system_prompt(self) -> str:
        return f"""You are the SatQuery AI query intent classifier. Your only job is to map the user's intent to a specific structured intent schema.
You must NOT answer the user's question directly.
You must NOT execute code, SQL, or arbitrary tools.
You must NOT generate filesystem paths.
You receive TEXT ONLY. You will never receive raw image pixels.

Distinguish INPUT CONFIGURATION from USER INTENT.
For example: just because two optical images are provided, it does not mean the task is CHANGE_DETECTION. The user must explicitly ask for change or comparison.

Constraints:
- You must NOT select, invent, or substitute models or tools.
- Never invent tasks. Only use tasks from the closed enum: SINGLE_VQA, CAPTIONING, GROUNDING, CHANGE_DETECTION, CHANGE_VQA, OPTICAL_SAR_ANALYSIS.
- If the query asks for change or differences between timestamps, task MUST be CHANGE_DETECTION or CHANGE_VQA, and requires_change_analysis must be true.
- If the query asks to ground, locate, or segment specific objects, task MUST be GROUNDING and requires_grounding must be true.
- If the query asks to fuse or analyze optical and SAR data together, task MUST be OPTICAL_SAR_ANALYSIS and requires_optical_sar_analysis must be true.
- If the query asks to identify or answer questions about a single image, task MUST be SINGLE_VQA.
- If the query asks to describe an image in general, task MUST be CAPTIONING.

You MUST output your response as valid JSON matching this exact JSON schema:
{self.schema_json}"""

    def build_user_prompt(self, request: RouteRequest) -> str:
        return f"""User Query: {request.query}
Input Class / Normalized Metadata: {json.dumps(request.manifest, default=str)}"""

    def validate_intent(self, route_resp: RouteResponse) -> RouteResponse:
        """
        Validate semantic consistency of the structured intent returned by VLM.
        Raises RouterError if the intent contains contradictions or unsupported tasks.
        """
        task = route_resp.task
        if not isinstance(task, RouterTask) and task not in RouterTask.__members__.values():
            raise RouterError(f"Unsupported task in router output: {task}")

        # Semantic flag consistency validation
        if task in (RouterTask.CHANGE_VQA, RouterTask.CHANGE_DETECTION):
            if not route_resp.requires_change_analysis:
                raise RouterError(
                    f"Intent contradiction: task '{task.value}' requires requires_change_analysis=True"
                )
            if route_resp.requires_optical_sar_analysis:
                raise RouterError(
                    f"Intent contradiction: task '{task.value}' cannot require requires_optical_sar_analysis=True"
                )

        if task == RouterTask.GROUNDING:
            if not route_resp.requires_grounding:
                raise RouterError(
                    f"Intent contradiction: task '{task.value}' requires requires_grounding=True"
                )
            if route_resp.requires_change_analysis:
                raise RouterError(
                    f"Intent contradiction: task '{task.value}' cannot require requires_change_analysis=True"
                )

        if task == RouterTask.OPTICAL_SAR_ANALYSIS:
            if not route_resp.requires_optical_sar_analysis:
                raise RouterError(
                    f"Intent contradiction: task '{task.value}' requires requires_optical_sar_analysis=True"
                )
            if route_resp.requires_change_analysis:
                raise RouterError(
                    f"Intent contradiction: task '{task.value}' cannot require requires_change_analysis=True"
                )

        if task in (RouterTask.SINGLE_VQA, RouterTask.CAPTIONING):
            if route_resp.requires_change_analysis:
                raise RouterError(
                    f"Intent contradiction: task '{task.value}' cannot have requires_change_analysis=True"
                )
            if route_resp.requires_optical_sar_analysis:
                raise RouterError(
                    f"Intent contradiction: task '{task.value}' cannot have requires_optical_sar_analysis=True"
                )

        return route_resp

    def _extract_json_block(self, text: str) -> str:
        """Extracts JSON object from model output if wrapped in markdown code blocks."""
        cleaned = text.strip()
        # Look for ```json ... ``` blocks
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Look for raw { ... }
        match_raw = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match_raw:
            return match_raw.group(1).strip()
        return cleaned

    def _parse_raw_response(self, raw_text: str) -> RouteResponse:
        json_str = self._extract_json_block(raw_text)
        dict_data = json.loads(json_str)
        if not isinstance(dict_data, dict):
            raise RouterError("Router model did not return a JSON object")
        if dict_data.get("tools") is None:
            dict_data["tools"] = []
        if isinstance(dict_data.get("tools"), list):
            cleaned = []
            for item in dict_data["tools"]:
                if item is None:
                    continue
                cleaned.append(item.value if hasattr(item, "value") else item)
            dict_data["tools"] = cleaned
        parsed = RouteResponse.model_validate(dict_data)
        return self.validate_intent(parsed)

    async def route(self, request: RouteRequest) -> RouteResponse:
        """VLM (OpenRouter) with deterministic fallback."""
        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(request)
        vlm_error: str | None = None

        try:
            raw_response = await self.client.generate_text_async(
                prompt=user_prompt,
                system_prompt=system_prompt,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            parsed = self._parse_raw_response(raw_response)
            parsed.reasoning = f"VLM OpenRouter intent classifier ({self.client.model})"
            return parsed
        except (VLMError, ValidationError, json.JSONDecodeError, Exception) as exc:
            vlm_error = str(exc)
            logging.warning(
                f"[Router] VLM OpenRouter classification failed ({exc}). Falling back to deterministic rules."
            )
            return self._fallback_route(
                request,
                error_reason=f"vlm: {vlm_error}",
            )

    def route_sync(self, request: RouteRequest) -> RouteResponse:
        """Synchronous VLM router used by LangGraph nodes."""
        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(request)
        vlm_error: str | None = None

        try:
            raw_response = self.client.generate_text_sync(
                prompt=user_prompt,
                system_prompt=system_prompt,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            parsed = self._parse_raw_response(raw_response)
            parsed.reasoning = f"VLM OpenRouter intent classifier ({self.client.model})"
            return parsed
        except (VLMError, ValidationError, json.JSONDecodeError, Exception) as exc:
            vlm_error = str(exc)
            logging.warning(
                f"[Router] VLM OpenRouter classification failed ({exc}). Falling back to deterministic rules."
            )
            return self._fallback_route(
                request,
                error_reason=f"vlm: {vlm_error}",
            )

    def _fallback_route(self, request: RouteRequest, error_reason: str = "") -> RouteResponse:
        """
        Deterministic fallback intent classifier used when VLM API is offline or unconfigured.
        Explicitly marked with fallback reasoning for auditability.
        """
        q = (request.query or "").lower()
        reason = f"Deterministic fallback rule classifier (VLM unavailable: {error_reason})" if error_reason else "Deterministic rule classifier fallback"

        if any(w in q for w in ["change", "changed", "difference", "compare", "between", "increased", "decreased"]):
            task = RouterTask.CHANGE_VQA if ("?" in q or any(w in q for w in ["what", "how", "has", "did"])) else RouterTask.CHANGE_DETECTION
            return RouteResponse(
                task=task,
                requires_change_analysis=True,
                tools=[RouterTool.GEOSPATIAL_VALIDATOR, RouterTool.BIT_CD],
                reasoning=reason,
            )

        if any(w in q for w in ["ground", "locate", "segment", "highlight", "bounding", "box"]):
            return RouteResponse(
                task=RouterTask.GROUNDING,
                requires_grounding=True,
                tools=[RouterTool.GEOSPATIAL_VALIDATOR, RouterTool.LULC_MAP],
                reasoning=reason,
            )

        if any(w in q for w in ["fuse", "fusion", "optical and sar", "sar and optical"]):
            return RouteResponse(
                task=RouterTask.OPTICAL_SAR_ANALYSIS,
                requires_optical_sar_analysis=True,
                tools=[RouterTool.GEOSPATIAL_VALIDATOR, RouterTool.FUSION_S1S2],
                reasoning=reason,
            )

        if any(w in q for w in ["describe", "caption", "overview"]):
            return RouteResponse(
                task=RouterTask.CAPTIONING,
                tools=[RouterTool.GEOSPATIAL_VALIDATOR, RouterTool.LULC_MAP],
                reasoning=reason,
            )

        # Default single-image visual question answering
        return RouteResponse(
            task=RouterTask.SINGLE_VQA,
            tools=[RouterTool.GEOSPATIAL_VALIDATOR, RouterTool.LULC_MAP],
            reasoning=reason,
        )


# Backward compatibility alias
QwenRouter = VLMRouter
