"""
SatQuery AI — Generic Vision-Language Model (VLM) Service Client

Provides a unified server-side client for multimodal visual reasoning and query intent
classification via OpenRouter (environment-driven via VLM_MODEL).

Strict Architectural Rules:
- Server-side only: API keys are loaded from environment and NEVER exposed to frontend.
- Cost Safety: Strictly restricted to free-tier models (model must end with ':free').
  Zero paid-model fallback.
- Security: Credentials and Authorization headers are masked in all logs and errors.
- Multimodal: Supports text-only and image+text multimodal message structures with
  automatic in-memory raster conversion for GeoTIFFs and standard formats.
"""

from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from backend.config import settings
from src.logger import logging


# ============================================================================
# Exceptions Hierarchy
# ============================================================================

class VLMError(Exception):
    """Base exception for VLM service."""
    pass


class VLMConfigError(VLMError):
    """Raised when configuration or API keys are missing/invalid."""
    pass


class VLMCostSafetyError(VLMError):
    """Raised when a non-free model is requested to prevent unexpected API costs."""
    pass


class VLMAuthError(VLMError):
    """Raised on HTTP 401/403 authentication failures."""
    pass


class VLMRateLimitError(VLMError):
    """Raised on HTTP 429 rate limit errors."""
    pass


class VLMModelUnavailableError(VLMError):
    """Raised when the specified free model is unavailable or overloaded."""
    pass


class VLMTimeoutError(VLMError):
    """Raised on connection or request timeout."""
    pass


# Backward compatibility aliases
QwenVLError = VLMError
QwenVLConfigError = VLMConfigError
QwenVLCostSafetyError = VLMCostSafetyError
QwenVLAuthError = VLMAuthError
QwenVLRateLimitError = VLMRateLimitError
QwenVLModelUnavailableError = VLMModelUnavailableError
QwenVLTimeoutError = VLMTimeoutError


# ============================================================================
# Helpers
# ============================================================================

def _sanitize_error_message(msg: str, secret: str | None) -> str:
    """Masks secrets and bearer tokens from error strings."""
    if not msg:
        return ""
    sanitized = msg
    if secret and secret in sanitized:
        sanitized = sanitized.replace(secret, "[REDACTED_API_KEY]")
    # Mask any lingering Bearer tokens or API keys
    sanitized = re.sub(r"Bearer\s+[\w\-\.]+", "Bearer [REDACTED_TOKEN]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"sk-[a-zA-Z0-9_\-]{20,}", "[REDACTED_KEY]", sanitized)
    return sanitized


def _encode_image_to_data_uri(image_input: str | Path | bytes | Image.Image) -> str:
    """
    Converts local image files (PNG, JPG, GeoTIFF) or bytes into a data URI.
    If input is already an HTTP URL or data URI, returns it directly.
    """
    if isinstance(image_input, str):
        if image_input.startswith("http://") or image_input.startswith("https://") or image_input.startswith("data:image/"):
            return image_input
        image_path = Path(image_input)
    elif isinstance(image_input, Path):
        image_path = image_input
    else:
        image_path = None

    if image_path is not None:
        if not image_path.exists():
            raise FileNotFoundError(f"Image asset file not found at: {image_path}")

        suffix = image_path.suffix.lower()
        if suffix in [".tif", ".tiff"]:
            # Convert multi-band/geotiff to RGB PNG in-memory
            try:
                import rasterio
                import numpy as np
                with rasterio.open(image_path) as src:
                    arr = src.read()
                    if arr.shape[0] >= 3:
                        rgb = arr[:3]
                    elif arr.shape[0] == 2:
                        rgb = np.stack([arr[0], arr[1], arr[0]])
                    else:
                        rgb = np.stack([arr[0], arr[0], arr[0]])
                    # Normalize to 0-255 uint8
                    p2, p98 = np.percentile(rgb, (2, 98))
                    if p98 > p2:
                        stretched = np.clip((rgb - p2) / (p98 - p2) * 255.0, 0, 255).astype(np.uint8)
                    else:
                        stretched = np.clip(rgb, 0, 255).astype(np.uint8)
                    img = Image.fromarray(np.transpose(stretched, (1, 2, 0)))
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
                    return f"data:image/png;base64,{b64_str}"
            except Exception as e:
                # Fallback to standard PIL open
                logging.warning(f"[VLM] rasterio read failed for {image_path}, falling back to PIL: {e}")
                img = Image.open(image_path).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
                return f"data:image/png;base64,{b64_str}"

        # Standard web image formats
        mime_type = "image/png"
        if suffix in [".jpg", ".jpeg"]:
            mime_type = "image/jpeg"
        elif suffix == ".webp":
            mime_type = "image/webp"

        raw_bytes = image_path.read_bytes()
        b64_str = base64.b64encode(raw_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{b64_str}"

    if isinstance(image_input, Image.Image):
        buf = io.BytesIO()
        image_input.convert("RGB").save(buf, format="PNG")
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64_str}"

    if isinstance(image_input, bytes):
        b64_str = base64.b64encode(image_input).decode("utf-8")
        return f"data:image/png;base64,{b64_str}"

    raise ValueError(f"Unsupported image input type: {type(image_input)}")


# ============================================================================
# VLMClient
# ============================================================================

class VLMClient:
    """
    Unified OpenRouter client for Vision-Language Model (VLM) text and multimodal requests.
    Enforces cost safety, server-side secret protection, and error sanitization.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        provider: str | None = None,
    ):
        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = (settings.OPENROUTER_API_KEY or "").strip()

        if model is not None and model.strip():
            self.model = model.strip()
        elif settings.VLM_MODEL and settings.VLM_MODEL.strip():
            self.model = settings.VLM_MODEL.strip()
        else:
            raise VLMConfigError(
                "VLM_MODEL is not configured. Please configure VLM_MODEL in your environment or .env file."
            )

        if base_url is not None:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = (settings.OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1").rstrip("/")

        self.timeout = timeout if timeout is not None else settings.OPENROUTER_TIMEOUT_SECONDS
        self.provider = provider or settings.VLM_PROVIDER
        self.enforce_free = getattr(settings, "VLM_COST_SAFETY_ENFORCE_FREE", True)

        # STRICT FREE-MODEL COST SAFETY CHECK
        # To prevent unexpected paid charges, the model must be an explicitly configured free tier model.
        if self.enforce_free:
            if not self.model.endswith(":free") or self.model in ("openrouter/auto", "openrouter/free"):
                raise VLMCostSafetyError(
                    f"Model '{self.model}' is not an explicitly pinned free-tier model (must end with ':free' and cannot be auto/free router). "
                    f"SatQuery AI strictly enforces $0 / ₹0 free OpenRouter API usage to prevent unexpected billing."
                )

    @property
    def is_configured(self) -> bool:
        """Returns True if the client has a valid API key configured."""
        return bool(self.api_key)

    def _get_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise VLMConfigError(
                "OPENROUTER_API_KEY is not configured in the server environment. "
                "Please configure OPENROUTER_API_KEY in .env to use the VLM service."
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://satquery.ai",
            "X-Title": "SatQuery AI",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        if max_tokens:
            payload["max_tokens"] = max_tokens
        return payload

    def _parse_completion_response(self, response_data: dict[str, Any]) -> str:
        """Extracts and validates message content from OpenRouter response."""
        if "error" in response_data:
            err = response_data["error"]
            err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise VLMError(f"OpenRouter API returned error: {_sanitize_error_message(err_msg, self.api_key)}")

        choices = response_data.get("choices")
        if not choices or not isinstance(choices, list):
            raise VLMError("OpenRouter response did not contain valid 'choices'.")

        first_choice = choices[0]
        message = first_choice.get("message", {})
        content = message.get("content")

        if content is None:
            finish_reason = first_choice.get("finish_reason", "unknown")
            raise VLMError(f"Empty content returned by model (finish_reason: {finish_reason}).")

        # Strip optional reasoning / thinking tags if present
        if isinstance(content, str):
            cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return cleaned if cleaned else content.strip()

        return str(content)

    def _handle_http_error(self, exc: Exception) -> None:
        """Translates HTTP and network errors to clean, safe VLMError exceptions."""
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            text = exc.response.text
            sanitized = _sanitize_error_message(text, self.api_key)

            if status in (401, 403):
                raise VLMAuthError(f"OpenRouter authentication failed ({status}): {sanitized}") from exc
            if status == 429:
                raise VLMRateLimitError(f"OpenRouter free-tier rate limit exceeded ({status}): {sanitized}") from exc
            if status in (404, 503):
                raise VLMModelUnavailableError(
                    f"Free model '{self.model}' is currently unavailable on OpenRouter ({status}): {sanitized}"
                ) from exc
            raise VLMError(f"OpenRouter API HTTP {status} error: {sanitized}") from exc

        if isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
            raise VLMTimeoutError(f"OpenRouter request timed out after {self.timeout}s.") from exc

        if isinstance(exc, httpx.RequestError):
            sanitized = _sanitize_error_message(str(exc), self.api_key)
            raise VLMError(f"OpenRouter connection failure: {sanitized}") from exc

        sanitized = _sanitize_error_message(str(exc), self.api_key)
        raise VLMError(f"Unexpected VLM error: {sanitized}") from exc

    # ────────────────────────────────────────────────────────────────────────
    # Core Chat Completion Methods
    # ────────────────────────────────────────────────────────────────────────

    async def chat_async(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Asynchronous chat completion call to OpenRouter."""
        headers = self._get_headers()
        payload = self._build_payload(messages, response_format, temperature, max_tokens)
        endpoint = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                return self._parse_completion_response(resp.json())
        except Exception as exc:
            self._handle_http_error(exc)
            raise

    def chat_sync(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Synchronous chat completion call to OpenRouter."""
        headers = self._get_headers()
        payload = self._build_payload(messages, response_format, temperature, max_tokens)
        endpoint = f"{self.base_url}/chat/completions"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                return self._parse_completion_response(resp.json())
        except Exception as exc:
            self._handle_http_error(exc)
            raise

    # ────────────────────────────────────────────────────────────────────────
    # High-Level Text and Multimodal Generators
    # ────────────────────────────────────────────────────────────────────────

    async def generate_text_async(
        self,
        prompt: str,
        system_prompt: str | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Send a text-only prompt to VLM."""
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self.chat_async(messages, response_format=response_format, temperature=temperature)

    def generate_text_sync(
        self,
        prompt: str,
        system_prompt: str | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Synchronous text-only prompt to VLM."""
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat_sync(messages, response_format=response_format, temperature=temperature)

    async def generate_multimodal_async(
        self,
        prompt: str,
        images: list[str | Path | bytes | Image.Image],
        system_prompt: str | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Send a multimodal (text + images) request to VLM."""
        user_content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        for img in images:
            data_uri = _encode_image_to_data_uri(img)
            user_content.append({
                "type": "image_url",
                "image_url": {"url": data_uri},
            })

        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_content})

        return await self.chat_async(messages, response_format=response_format, temperature=temperature)

    def generate_multimodal_sync(
        self,
        prompt: str,
        images: list[str | Path | bytes | Image.Image],
        system_prompt: str | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Synchronous multimodal (text + images) request to VLM."""
        user_content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        for img in images:
            data_uri = _encode_image_to_data_uri(img)
            user_content.append({
                "type": "image_url",
                "image_url": {"url": data_uri},
            })

        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_content})

        return self.chat_sync(messages, response_format=response_format, temperature=temperature)


# ============================================================================
# Singleton Accessor & Backward Compatibility Aliases
# ============================================================================

_vlm_client: VLMClient | None = None


def get_vlm_client() -> VLMClient:
    """Returns the shared VLMClient instance."""
    global _vlm_client
    if _vlm_client is None:
        _vlm_client = VLMClient()
    return _vlm_client


# Backward compatibility alias
QwenVLClient = VLMClient
get_qwen_vl_client = get_vlm_client
