"""
Specialist Tool: SARChat VQA & SAR Image Interpretation (tool_id: sarchat_vqa)

Uses SARChat-InternVL2.5-2B for question answering and scene understanding on SAR imagery.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from backend.agents.tools.base import BaseTool
from backend.services.sar_service import get_sar_service
from backend.services.sar_analyzer import (
    compute_sar_scene_statistics,
    parse_sarchat_detections,
    render_sar_visualization_products,
)
from src.logger import logging


class SARChatTool(BaseTool):
    """
    Specialist tool for SAR image understanding, VQA, and interpretation
    powered by SARChat-InternVL2.5-2B, coupled with quantitative GIS raster analysis.
    """

    tool_id = "sarchat_vqa"

    def __init__(self) -> None:
        self.sar_service = get_sar_service()

    def validate(self, params: Mapping[str, Any]) -> None:
        if "question" not in params or not isinstance(params["question"], str) or not params["question"].strip():
            raise ValueError("Missing or empty 'question' for SARChat VQA")
        if "image_refs" not in params or not isinstance(params["image_refs"], list) or not params["image_refs"]:
            raise ValueError("Missing or empty 'image_refs' for SARChat VQA")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        question = params["question"]
        image_ref = params["image_refs"][0]

        # 1. Run SARChat VLM inference
        model_result = self.sar_service.infer(image_source=image_ref, question=question)
        raw_answer = model_result.get("answer", "")

        # 2. Compute quantitative GIS raster backscatter statistics
        scene_stats = {}
        if Path(image_ref).exists() and Path(image_ref).suffix.lower() in (".tif", ".tiff"):
            try:
                scene_stats = compute_sar_scene_statistics(image_ref)
            except Exception as e:
                logging.warning(f"[SAR] Failed computing scene statistics for {image_ref}: {e}")

        # 3. Parse bounding boxes and derive geographic / pixel detections
        detections = parse_sarchat_detections(raw_answer, tif_path=image_ref)

        # 4. Generate multi-channel visualization products (composite, vv, vh, overlay)
        visualizations = {}
        if Path(image_ref).exists() and Path(image_ref).suffix.lower() in (".tif", ".tiff"):
            try:
                # Save into the processed directory for the job
                job_dir = Path(image_ref).parent.parent / "processed"
                if not job_dir.exists():
                    job_dir = Path(image_ref).parent
                vis_paths = render_sar_visualization_products(
                    tif_path=image_ref,
                    output_dir=job_dir,
                    detections=detections,
                )
                visualizations = {k: str(v) for k, v in vis_paths.items()}
            except Exception as e:
                logging.warning(f"[SAR] Failed rendering visualizations: {e}")

        scene_tags = []
        if scene_stats:
            try:
                from backend.agents.tools.bigearthnet import scene_tags as ben_tags

                water = float(scene_stats.get("water_percent") or 0) / 100.0
                built = float(scene_stats.get("urban_percent") or 0) / 100.0
                veg = float(scene_stats.get("vegetation_percent") or 0) / 100.0
                other = float(scene_stats.get("other_percent") or 0) / 100.0
                scene_tags = ben_tags(
                    {
                        "water": water,
                        "built": built,
                        "trees": veg * 0.4,
                        "grass": veg * 0.35,
                        "crops": veg * 0.25,
                        "bare": other,
                    }
                )
                if scene_tags and "BigEarthNet-19" not in raw_answer:
                    raw_answer = (
                        f"{raw_answer}\n\n**Scene tags** (BigEarthNet-19 names from SAR "
                        "backscatter fractions — not a BEN-S1 trained net)\n"
                        + " · ".join(t["name"] for t in scene_tags)
                    )
            except Exception as e:
                logging.warning(f"[SAR] Failed mapping BEN-19 tags: {e}")

        return {
            "answer": raw_answer,
            "model": model_result.get("model", "SARChat-InternVL2.5-2B"),
            "modality": "SAR",
            "latency_ms": model_result.get("latency_ms"),
            "scene_statistics": scene_stats,
            "scene_tags": scene_tags,
            "detections": detections,
            "visualizations": visualizations,
            "status": model_result.get("status", "success"),
        }

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        return "[SAR] SARChat-InternVL2.5-2B and GIS raster backscatter analysis evaluated scene features, detections, and composition."

