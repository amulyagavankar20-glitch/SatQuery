import json
from typing import Any

import httpx
from pydantic import ValidationError

from backend.config import settings
from backend.schemas import RouteRequest, RouteResponse, RouterTask, RouterTool


class QwenRouterError(Exception):
    pass


class QwenRouter:
    """
    Text-only router powered by Qwen2.5-3B-Instruct.
    Responsible for distinguishing USER INTENT from INPUT CONFIGURATION.
    """

    def __init__(
        self,
        ollama_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        base = (ollama_url or settings.OLLAMA_BASE_URL).rstrip("/")
        if base.endswith("/api/generate"):
            self.ollama_url = base
        else:
            self.ollama_url = f"{base}/api/generate"
        self.model = model or settings.OLLAMA_ROUTER_MODEL
        self.timeout = timeout if timeout is not None else settings.OLLAMA_TIMEOUT_SECONDS
        self.response_schema = RouteResponse.model_json_schema()
        self.schema_json = json.dumps(self.response_schema, indent=2)

    def build_prompt(self, request: RouteRequest, available_tools: list[str], constraints: list[str]) -> str:
        return f"""<|im_start|>system
You are the SatQuery AI query intent classifier. Your only job is to map the user's intent to a specific structured intent schema.
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
{self.schema_json}
<|im_end|>
<|im_start|>user
User Query: {request.query}
Input Class / Normalized Metadata: {json.dumps(request.manifest, default=str)}
<|im_end|>
<|im_start|>assistant
"""

    def validate_intent(self, route_resp: RouteResponse) -> RouteResponse:
        """
        Validate semantic consistency of the structured intent returned by Qwen.
        Raises QwenRouterError if the intent contains contradictions or unsupported tasks.
        """
        task = route_resp.task
        if not isinstance(task, RouterTask) and task not in RouterTask.__members__.values():
            raise QwenRouterError(f"Unsupported task in router output: {task}")

        # Semantic flag consistency validation
        if task in (RouterTask.CHANGE_VQA, RouterTask.CHANGE_DETECTION):
            if not route_resp.requires_change_analysis:
                raise QwenRouterError(
                    f"Intent contradiction: task '{task.value}' requires requires_change_analysis=True"
                )
            if route_resp.requires_optical_sar_analysis:
                raise QwenRouterError(
                    f"Intent contradiction: task '{task.value}' cannot require requires_optical_sar_analysis=True"
                )

        if task == RouterTask.GROUNDING:
            if not route_resp.requires_grounding:
                raise QwenRouterError(
                    f"Intent contradiction: task '{task.value}' requires requires_grounding=True"
                )
            if route_resp.requires_change_analysis:
                raise QwenRouterError(
                    f"Intent contradiction: task '{task.value}' cannot require requires_change_analysis=True"
                )

        if task == RouterTask.OPTICAL_SAR_ANALYSIS:
            if not route_resp.requires_optical_sar_analysis:
                raise QwenRouterError(
                    f"Intent contradiction: task '{task.value}' requires requires_optical_sar_analysis=True"
                )
            if route_resp.requires_change_analysis:
                raise QwenRouterError(
                    f"Intent contradiction: task '{task.value}' cannot require requires_change_analysis=True"
                )

        if task in (RouterTask.SINGLE_VQA, RouterTask.CAPTIONING):
            if route_resp.requires_change_analysis:
                raise QwenRouterError(
                    f"Intent contradiction: task '{task.value}' cannot have requires_change_analysis=True"
                )
            if route_resp.requires_optical_sar_analysis:
                raise QwenRouterError(
                    f"Intent contradiction: task '{task.value}' cannot have requires_optical_sar_analysis=True"
                )

        return route_resp

    async def route(self, request: RouteRequest) -> RouteResponse:
        available_tools = [
            "geospatial_validator", "geochat_vqa", "geochat_describe", 
            "bit_cd", "fusion_s1s2", "mobilesam", "vectorizer"
        ]
        constraints = [
            "Never hallucinate tool names. Only use tools from the provided list.",
            "Never invent tasks. Only use tasks from the enum in the schema.",
            "If the query asks for change, task MUST be CHANGE_DETECTION or CHANGE_VQA.",
            "If the query asks to identify or describe a single image, task MUST be SINGLE_VQA or CAPTIONING."
        ]
        
        prompt = self.build_prompt(request, available_tools, constraints)
        payload = self._build_payload(prompt)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.ollama_url, json=payload)
                response.raise_for_status()
                return self._parse_response(response.json())
        except httpx.HTTPError as e:
            from src.logger import logging
            logging.warning(f"[Router] Ollama unreachable ({e}), using deterministic fallback intent classifier.")
            return self._fallback_route(request)
        except ValidationError as e:
            raise QwenRouterError(f"Router produced invalid structured output: {e}")
        except json.JSONDecodeError as e:
            raise QwenRouterError(f"Router output was not valid JSON: {e}")

    def route_sync(self, request: RouteRequest) -> RouteResponse:
        """Synchronous route used by LangGraph sync nodes (no nested event loop)."""
        available_tools = [
            "geospatial_validator", "geochat_vqa", "geochat_describe",
            "bit_cd", "fusion_s1s2", "mobilesam", "vectorizer"
        ]
        constraints = [
            "Never hallucinate tool names. Only use tools from the provided list.",
            "Never invent tasks. Only use tasks from the enum in the schema.",
            "If the query asks for change, task MUST be CHANGE_DETECTION or CHANGE_VQA.",
            "If the query asks to identify or describe a single image, task MUST be SINGLE_VQA or CAPTIONING."
        ]
        prompt = self.build_prompt(request, available_tools, constraints)
        payload = self._build_payload(prompt)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.ollama_url, json=payload)
                response.raise_for_status()
                return self._parse_response(response.json())
        except httpx.HTTPError as e:
            from src.logger import logging
            logging.warning(f"[Router] Ollama unreachable ({e}), using deterministic fallback intent classifier.")
            return self._fallback_route(request)
        except ValidationError as e:
            raise QwenRouterError(f"Router produced invalid structured output: {e}")
        except json.JSONDecodeError as e:
            raise QwenRouterError(f"Router output was not valid JSON: {e}")

    def _fallback_route(self, request: RouteRequest) -> RouteResponse:
        """Heuristic fallback used when Ollama server is offline/unreachable in dev environment."""
        q = (request.query or "").lower()

        if any(w in q for w in ["change", "changed", "difference", "compare", "between", "increased", "decreased"]):
            task = RouterTask.CHANGE_VQA if ("?" in q or any(w in q for w in ["what", "how", "has", "did"])) else RouterTask.CHANGE_DETECTION
            return RouteResponse(
                task=task,
                requires_change_analysis=True,
                tools=[RouterTool.GEOSPATIAL_VALIDATOR, RouterTool.BIT_CD],
            )
        
        if any(w in q for w in ["ground", "locate", "segment", "highlight", "bounding", "box"]):
            return RouteResponse(
                task=RouterTask.GROUNDING,
                requires_grounding=True,
                tools=[RouterTool.GEOSPATIAL_VALIDATOR, RouterTool.GEOCHAT_VQA],
            )

        if any(w in q for w in ["fuse", "fusion", "optical and sar", "sar and optical"]):
            return RouteResponse(
                task=RouterTask.OPTICAL_SAR_ANALYSIS,
                requires_optical_sar_analysis=True,
                tools=[RouterTool.GEOSPATIAL_VALIDATOR, RouterTool.FUSION_S1S2],
            )

        if any(w in q for w in ["describe", "caption", "overview"]):
            return RouteResponse(
                task=RouterTask.CAPTIONING,
                tools=[RouterTool.GEOSPATIAL_VALIDATOR, RouterTool.GEOCHAT_DESCRIBE],
            )

        # Default single-image visual question answering
        return RouteResponse(
            task=RouterTask.SINGLE_VQA,
            tools=[RouterTool.GEOSPATIAL_VALIDATOR, RouterTool.GEOCHAT_VQA],
        )

    def _build_payload(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "prompt": prompt,
            # JSON-schema constrained decoding (architecture §1 / §6)
            "format": self.response_schema,
            "stream": False,
            "raw": True,  # We handle the prompt formatting ourselves
            "options": {
                "temperature": 0.0,
                "top_k": 1,  # Greedy decoding
            },
        }

    def _parse_response(self, result: dict[str, Any]) -> RouteResponse:
        response_body: str | dict[str, Any] = result.get("response", "{}")
        if isinstance(response_body, dict):
            parsed = RouteResponse.model_validate(response_body)
        else:
            parsed = RouteResponse.model_validate_json(response_body)
        return self.validate_intent(parsed)
