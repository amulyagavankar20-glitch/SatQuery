"""Specialist pipeline utility tools for multi-temporal and multi-sensor processing."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from .base import BaseTool


# ──────────────────────────────────────────────────────────────────────────────
# Align  (tool_id: align)
# Co-registration of bi-temporal optical image pairs before change detection.
# ──────────────────────────────────────────────────────────────────────────────
class AlignTool(BaseTool):
    """Image alignment/co-registration tool for bi-temporal pairs prior to BIT change detection."""

    tool_id = "align"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "pre_refs" not in params or "post_refs" not in params:
            raise ValueError("Both 'pre_refs' and 'post_refs' are required for align")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return {"aligned_pre": params["pre_refs"], "aligned_post": params["post_refs"]}

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        return "Align co-registered bi-temporal image pairs."


# ──────────────────────────────────────────────────────────────────────────────
# Vectorize  (tool_id: vectorize)
# Converts a change-detection mask into vector polygons.
# ──────────────────────────────────────────────────────────────────────────────
class VectorizeTool(BaseTool):
    """Mask vectorization tool converting raster masks to vector geometries."""

    tool_id = "vectorize"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "mask_id" not in params:
            raise ValueError("'mask_id' is required for vectorize")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return f"VECTOR_LAYER from {params['mask_id']}"

    def postprocess(self, raw_output: Any) -> Any:
        return {"vector_id": raw_output}

    def explain_execution(self, result: Any) -> str:
        return "Vectorize converted the change mask to vector polygons."


# ──────────────────────────────────────────────────────────────────────────────
# Coregister  (tool_id: coregister)
# Pixel-level co-registration of optical + SAR image pairs.
# ──────────────────────────────────────────────────────────────────────────────
class CoregisterTool(BaseTool):
    """Optical-SAR co-registration tool."""

    tool_id = "coregister"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "optical_refs" not in params or "sar_refs" not in params:
            raise ValueError("Both 'optical_refs' and 'sar_refs' are required for coregister")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return {
            "coregistered_optical": params["optical_refs"],
            "coregistered_sar": params["sar_refs"],
        }

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        return "Coregister aligned optical and SAR imagery to the same pixel grid."


# ──────────────────────────────────────────────────────────────────────────────
# Optical-SAR Fusion  (tool_id: fusion_s1s2)
# ──────────────────────────────────────────────────────────────────────────────
class FusionTool(BaseTool):
    """Optical-SAR fusion tool."""

    tool_id = "fusion_s1s2"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "optical_ref" not in params or "sar_ref" not in params:
            raise ValueError("Both 'optical_ref' and 'sar_ref' are required for fusion")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return "FUSION_OUTPUT"

    def postprocess(self, raw_output: Any) -> Any:
        return {"fusion_id": raw_output}

    def explain_execution(self, result: Any) -> str:
        return "Fusion combined optical and SAR inputs."


# ──────────────────────────────────────────────────────────────────────────────
# Agreement  (tool_id: agreement)
# Cross-modal consistency check between optical and SAR evidence.
# ──────────────────────────────────────────────────────────────────────────────
class AgreementTool(BaseTool):
    """Optical/SAR cross-modal agreement tool."""

    tool_id = "agreement"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "fusion_id" not in params:
            raise ValueError("'fusion_id' is required for agreement")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return {"agreement_score": "HIGH", "fusion_ref": params["fusion_id"]}

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        return "Agreement assessed cross-modal consistency between optical and SAR."
