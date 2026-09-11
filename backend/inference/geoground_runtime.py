"""Local GeoGround runtime boundary.

GeoGround is strictly an optical/Sentinel-2 specialist.  Its eventual model
loader belongs here; the agent-facing tool must never send SAR data to it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.config import settings


class GeoGroundRuntime:
    """Owns the future local GeoGround model lifecycle.

    The explicit unavailable response keeps the orchestration contract honest
    until a tested local GeoGround checkpoint is configured.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path or settings.GEOGROUND_MODEL_PATH

    def is_available(self) -> bool:
        return bool(self.model_path) and Path(self.model_path).exists()

    def analyze(self, image_paths: list[str], question: str, *, task: str) -> dict[str, Any]:
        if not self.is_available():
            raise RuntimeError(
                "GeoGround is not configured. Set GEOGROUND_MODEL_PATH to a tested local "
                "GeoGround checkpoint before enabling optical inference."
            )
        raise NotImplementedError(
            "GeoGround loading is intentionally isolated here; integrate the validated "
            "LLaVA/GeoGround loader without changing the agent tool contract."
        )


_runtime: GeoGroundRuntime | None = None


def get_geoground_runtime() -> GeoGroundRuntime:
    global _runtime
    if _runtime is None:
        _runtime = GeoGroundRuntime()
    return _runtime
