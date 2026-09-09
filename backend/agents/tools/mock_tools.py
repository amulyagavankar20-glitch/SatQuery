"""Mock specialist tools for Stage 4 orchestration.

Each mock implements the :class:`BaseTool` contract defined in
``backend.agents.tools.base``. The tools return deterministic, clearly marked
outputs (prefixed with ``MOCK_``) and never perform any real scientific
computation.

Tool IDs registered here MUST match the IDs used in:
  - ToolSelector.TASK_TO_TOOLS
  - executor._TOOL_IMPLEMENTATIONS
  - graph.py node invocations
  - ToolRegistry DB entries
"""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from .base import BaseTool


# ──────────────────────────────────────────────────────────────────────────────
# GeoChat VQA  (tool_id: geochat_vqa)
# ──────────────────────────────────────────────────────────────────────────────
class MockGeochatVQA(BaseTool):
    """Mock implementation of the GeoChat VQA tool.

    Expected parameters:
        - ``question``: str
        - ``image_refs``: list of str (identifiers of preprocessed assets)
    """

    tool_id = "geochat_vqa"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "question" not in params or not isinstance(params["question"], str):
            raise ValueError("Missing or invalid 'question' for GeoChat VQA")
        if "image_refs" not in params or not isinstance(params["image_refs"], list):
            raise ValueError("Missing or invalid 'image_refs' for GeoChat VQA")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return f"MOCK_VQA_ANSWER to '{params['question']}'"

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        return "[MOCK] GeoChat VQA answered the question using mock inference."


# ──────────────────────────────────────────────────────────────────────────────
# GeoChat Describe  (tool_id: geochat_describe)
# Separate interface from geochat_vqa — generates a free-form description
# of a processed image/result without requiring a specific question.
# ──────────────────────────────────────────────────────────────────────────────
class MockGeochatDescribe(BaseTool):
    """Mock implementation of the GeoChat Describe tool.

    Expected parameters:
        - ``image_refs``: list of str (identifiers of preprocessed / result assets)
        - ``context``: optional str – additional context for the description
    """

    tool_id = "geochat_describe"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "image_refs" not in params or not isinstance(params["image_refs"], list):
            raise ValueError("Missing or invalid 'image_refs' for GeoChat Describe")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        context = params.get("context", "")
        return f"MOCK_DESCRIPTION: detected land-cover patterns. Context='{context}'"

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        return "[MOCK] GeoChat Describe produced a free-form description of the image."


# ──────────────────────────────────────────────────────────────────────────────
# Grounding  (tool_id: grounding)
# ──────────────────────────────────────────────────────────────────────────────
class MockGrounding(BaseTool):
    """Mock implementation of the grounding tool.

    Expected parameters:
        - ``text``: str
        - ``image_refs``: list of str
    """

    tool_id = "grounding"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "text" not in params or not isinstance(params["text"], str):
            raise ValueError("Missing or invalid 'text' for grounding")
        if "image_refs" not in params or not isinstance(params["image_refs"], list):
            raise ValueError("Missing or invalid 'image_refs' for grounding")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        target = params.get("text", "object")
        return {
            "grounding_target": target,
            "status": "success",
            "message": f"GeoGround successfully localized '{target}' in the spatial scene.",
            "detections": [
                {
                    "label": target,
                    "bbox_norm": [0.061, 0.170, 0.075, 0.182],
                    "image_position": "bottom-left",
                },
                {
                    "label": target,
                    "bbox_norm": [0.118, 0.094, 0.131, 0.105],
                    "image_position": "center",
                },
            ],
        }

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        return "[MOCK] Grounding performed on the provided text and images."


# ──────────────────────────────────────────────────────────────────────────────
# BIT Change Detection  (tool_id: bit_cd)
# ──────────────────────────────────────────────────────────────────────────────
class MockBitCD(BaseTool):
    """Mock implementation of the BIT change detection tool.

    Expected parameters:
        - ``pre_image``: str  – reference ID for the earlier tile/image
        - ``post_image``: str – reference ID for the later tile/image
    """

    tool_id = "bit_cd"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "pre_image" not in params or "post_image" not in params:
            raise ValueError("Both 'pre_image' and 'post_image' are required for BIT CD")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return "MOCK_BIT_CD_MASK"

    def postprocess(self, raw_output: Any) -> Any:
        return {"mask_id": raw_output}

    def explain_execution(self, result: Any) -> str:
        return "[MOCK] BIT change detection generated a deterministic mask identifier."


# ──────────────────────────────────────────────────────────────────────────────
# Align  (tool_id: align)
# Co-registration of bi-temporal optical image pairs before change detection.
# ──────────────────────────────────────────────────────────────────────────────
class MockAlign(BaseTool):
    """Mock implementation of the image alignment/co-registration tool for
    bi-temporal pairs prior to BIT change detection.

    Expected parameters:
        - ``pre_refs``: list of str – tile reference IDs for t1
        - ``post_refs``: list of str – tile reference IDs for t2
    """

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
        return "[MOCK] Align co-registered bi-temporal image pairs."


# ──────────────────────────────────────────────────────────────────────────────
# Vectorize  (tool_id: vectorize)
# Converts a change-detection mask into vector polygons.
# ──────────────────────────────────────────────────────────────────────────────
class MockVectorize(BaseTool):
    """Mock implementation of the mask vectorization tool.

    Expected parameters:
        - ``mask_id``: str – reference ID for the change mask produced by bit_cd
    """

    tool_id = "vectorize"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "mask_id" not in params:
            raise ValueError("'mask_id' is required for vectorize")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return f"MOCK_VECTOR_LAYER from {params['mask_id']}"

    def postprocess(self, raw_output: Any) -> Any:
        return {"vector_id": raw_output}

    def explain_execution(self, result: Any) -> str:
        return "[MOCK] Vectorize converted the change mask to vector polygons."


# ──────────────────────────────────────────────────────────────────────────────
# Coregister  (tool_id: coregister)
# Pixel-level co-registration of optical + SAR image pairs.
# ──────────────────────────────────────────────────────────────────────────────
class MockCoregister(BaseTool):
    """Mock implementation of the optical-SAR co-registration tool.

    Expected parameters:
        - ``optical_refs``: list of str
        - ``sar_refs``: list of str
    """

    tool_id = "coregister"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "optical_refs" not in params or "sar_refs" not in params:
            raise ValueError("Both 'optical_refs' and 'sar_refs' are required for coregister")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return {"coregistered_optical": params["optical_refs"],
                "coregistered_sar": params["sar_refs"]}

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        return "[MOCK] Coregister aligned optical and SAR imagery to the same pixel grid."


# ──────────────────────────────────────────────────────────────────────────────
# Optical-SAR Fusion  (tool_id: fusion_s1s2)
# ──────────────────────────────────────────────────────────────────────────────
class MockFusion(BaseTool):
    """Mock implementation of the optical-SAR fusion tool.

    Expected parameters:
        - ``optical_ref``: str
        - ``sar_ref``: str
    """

    tool_id = "fusion_s1s2"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "optical_ref" not in params or "sar_ref" not in params:
            raise ValueError("Both 'optical_ref' and 'sar_ref' are required for fusion")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return "MOCK_FUSION_OUTPUT"

    def postprocess(self, raw_output: Any) -> Any:
        return {"fusion_id": raw_output}

    def explain_execution(self, result: Any) -> str:
        return "[MOCK] Fusion combined optical and SAR inputs into a deterministic output."


# ──────────────────────────────────────────────────────────────────────────────
# Agreement  (tool_id: agreement)
# Cross-modal consistency check between optical and SAR evidence.
# ──────────────────────────────────────────────────────────────────────────────
class MockAgreement(BaseTool):
    """Mock implementation of the optical/SAR agreement tool.

    Expected parameters:
        - ``fusion_id``: str – reference to the fusion output
    """

    tool_id = "agreement"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "fusion_id" not in params:
            raise ValueError("'fusion_id' is required for agreement")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return {"agreement_score": "MOCK_HIGH", "fusion_ref": params["fusion_id"]}

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        return "[MOCK] Agreement assessed cross-modal consistency between optical and SAR."


# ──────────────────────────────────────────────────────────────────────────────
# MobileSAM  (tool_id: mobile_sam)
# ──────────────────────────────────────────────────────────────────────────────
class MockMobileSAM(BaseTool):
    """Mock implementation of the MobileSAM segmentation tool.

    Expected parameters:
        - ``image_ref``: str
        - ``prompt``: str
    """

    tool_id = "mobile_sam"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "image_ref" not in params or "prompt" not in params:
            raise ValueError("'image_ref' and 'prompt' are required for MobileSAM")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        return f"MOCK_SAM_SEGMENT_{params['prompt'].upper()}"

    def postprocess(self, raw_output: Any) -> Any:
        return {"segment_id": raw_output}

    def explain_execution(self, result: Any) -> str:
        return "[MOCK] MobileSAM produced a deterministic segmentation identifier."
