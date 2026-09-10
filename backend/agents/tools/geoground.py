"""Qwen-callable optical/Sentinel-2 GeoGround tool."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.agents.tools.base import BaseTool
from backend.inference import get_geoground_runtime


class GeoGroundTool(BaseTool):
    """Adapter that keeps GeoGround S2-only and returns structured evidence."""

    tool_id = "geoground_analyze"

    def validate(self, params: Mapping[str, Any]) -> None:
        if not params.get("image_refs"):
            raise ValueError("GeoGround requires at least one preprocessed optical image.")
        if str(params.get("modality", "OPTICAL")).upper() != "OPTICAL":
            raise ValueError("GeoGround accepts only optical/Sentinel-2 inputs; SAR is not permitted.")
        if not str(params.get("question", "")).strip():
            raise ValueError("GeoGround requires a non-empty question.")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return get_geoground_runtime().analyze(
            list(params["image_refs"]), str(params["question"]), task=str(params.get("task", "SINGLE_VQA"))
        )

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        return "GeoGround evaluated S2 optical imagery and returned structured optical evidence."
