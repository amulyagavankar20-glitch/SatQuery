import json
from typing import Any

import httpx
from pydantic import ValidationError

from backend.config import settings
from backend.schemas import RouteRequest, RouteResponse


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
You are the SatQuery AI query router. Your only job is to map the user's intent to a specific structured routing plan.
You must NOT answer the user's question directly.
You must NOT execute code, SQL, or arbitrary tools.
You must NOT generate filesystem paths.
You receive TEXT ONLY. You will never receive raw image pixels.

Distinguish INPUT CONFIGURATION from USER INTENT.
For example: just because two optical images are provided, it does not mean the task is CHANGE_DETECTION. The user must explicitly ask for change or comparison.

Available capabilities / tools:
{json.dumps(available_tools, indent=2)}

Constraints:
{json.dumps(constraints, indent=2)}

You MUST output your response as valid JSON matching this exact JSON schema:
{self.schema_json}
<|im_end|>
<|im_start|>user
User Query: {request.query}
Input Class / Normalized Metadata: {json.dumps(request.manifest, default=str)}
<|im_end|>
<|im_start|>assistant
"""

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
            raise QwenRouterError(f"Failed to communicate with Qwen router: {e}")
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
            raise QwenRouterError(f"Failed to communicate with Qwen router: {e}")
        except ValidationError as e:
            raise QwenRouterError(f"Router produced invalid structured output: {e}")
        except json.JSONDecodeError as e:
            raise QwenRouterError(f"Router output was not valid JSON: {e}")

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
            return RouteResponse.model_validate(response_body)
        return RouteResponse.model_validate_json(response_body)
