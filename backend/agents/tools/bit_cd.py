"""
Specialist Tool: BIT Change Detection (tool_id: bit_cd)

Uses the Bitemporal Image Transformer (BIT) ONNX model for optical change detection
and surface alteration assessment.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from backend.agents.tools.base import BaseTool
from backend.services.bit_service import BITService
from src.logger import logging


class BITChangeDetectionTool(BaseTool):
    """
    Specialist tool for optical change detection powered by BIT-LEVIR ONNX runtime.
    Produces quantitative change metrics, GeoJSON polygon detections, and visualization overlays.
    """

    tool_id = "bit_cd"

    def __init__(self) -> None:
        self.bit_service = BITService.get_instance()

    def validate(self, params: Mapping[str, Any]) -> None:
        pre = params.get("pre_image")
        post = params.get("post_image")
        input_refs = params.get("input_refs", [])

        # Require either pre/post image paths or at least 2 input_refs
        has_pair = (pre and post and pre != "pre_placeholder" and post != "post_placeholder")
        has_refs = len(input_refs) >= 2

        if not has_pair and not has_refs and not (pre and post):
            raise ValueError("BIT Change Detection requires two temporal images (pre_image and post_image).")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        pre_source = params.get("pre_image")
        post_source = params.get("post_image")
        input_refs = params.get("input_refs", [])

        # Resolve actual image sources from input_refs if placeholders are present
        if (not pre_source or pre_source == "pre_placeholder") and len(input_refs) >= 2:
            pre_source = input_refs[0]
            post_source = input_refs[1]
        elif (not post_source or post_source == "post_placeholder") and len(input_refs) >= 2:
            post_source = input_refs[1]

        # Determine job / output directory for artifacts
        output_dir = None
        if isinstance(pre_source, (str, Path)) and Path(pre_source).exists():
            parent_dir = Path(pre_source).parent
            if parent_dir.name in ("raw", "tiles", "processed"):
                output_dir = parent_dir.parent / "processed"
            else:
                output_dir = parent_dir / "processed"
        elif input_refs and Path(str(input_refs[0])).exists():
            output_dir = Path(str(input_refs[0])).parent / "processed"
        else:
            output_dir = Path("data/jobs/bit_change_detection")

        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            res = self.bit_service.run_change_detection(
                pre_source=pre_source,
                post_source=post_source,
                output_dir=output_dir,
            )

            stats = res.get("statistics", {})
            geojson = res.get("geojson", {})
            features = geojson.get("features", [])
            overlay_path = res.get("overlay_path")
            summary = res.get("summary", "")

            # Save binary mask to file for downstream vectorization/caching
            mask = res.get("mask")
            mask_path = str(output_dir / "bit_change_mask.png")
            if mask is not None:
                from PIL import Image
                Image.fromarray((mask * 255).astype("uint8")).save(mask_path)

            return {
                "mask_id": mask_path,
                "statistics": stats,
                "detections": [f["properties"] for f in features],
                "geojson": geojson,
                "overlay_path": overlay_path,
                "summary": summary,
                "elapsed_seconds": res.get("elapsed_seconds", 0.0),
                "answer": summary,
            }

        except Exception as e:
            logging.error(f"[BIT_CD] Real inference error: {e}", exc_info=True)
            # If model cannot be loaded (e.g. test environment without weights), return error
            return {
                "error": str(e),
                "mask_id": "ERROR_BIT_CD_FAILED",
                "statistics": {"change_percentage": 0.0, "changed_pixels": 0, "region_count": 0},
                "summary": f"BIT change detection encountered an error: {e}",
            }

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        if isinstance(result, dict) and "statistics" in result:
            stats = result["statistics"]
            pct = stats.get("change_percentage", 0.0)
            regions = stats.get("region_count", 0)
            area = stats.get("changed_area_m2", 0.0)
            return (
                f"BIT LEVIR ONNX analyzed bi-temporal optical rasters and identified {pct:.2f}% "
                f"change ({area} m²) across {regions} polygon cluster(s)."
            )
        return "BIT change detection completed."
