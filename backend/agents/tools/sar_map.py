"""S1 specialist: reBEN ResNet50 (BigEarthNet-S1) + dual-pol backscatter."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Mapping

import numpy as np
import rasterio

from backend.agents.tools.base import BaseTool
from backend.services.sar_analyzer import (
    compute_sar_scene_statistics,
    render_sar_visualization_products,
)
from backend.services.sar_ben import BenS1Classifier
from src.logger import logging


class SarMapTool(BaseTool):
    tool_id = "sar_map"

    def validate(self, params: Mapping[str, Any]) -> None:
        if "image_refs" not in params or not params["image_refs"]:
            raise ValueError("sar_map requires image_refs")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        question = str(params.get("question") or "Describe this SAR scene")
        image_ref = str(params["image_refs"][0])
        path = Path(image_ref)

        scene_stats: dict[str, Any] = {}
        if path.suffix.lower() in {".tif", ".tiff"} and path.is_file():
            try:
                scene_stats = compute_sar_scene_statistics(path)
            except Exception as exc:
                logging.warning(f"[SAR] backscatter stats failed: {exc}")

        tags: list[dict[str, Any]] = []
        backend = "sar_backscatter"
        if path.suffix.lower() in {".tif", ".tiff"} and path.is_file():
            try:
                with rasterio.open(path) as src:
                    stack = src.read().astype(np.float32)
                if stack.shape[0] >= 2:
                    tags = BenS1Classifier.get_instance().predict(stack[:2])
                    backend = "reben_s1_resnet50"
            except Exception as exc:
                logging.warning(f"[SAR] reBEN S1 classifier failed: {exc}")

        visualizations: dict[str, str] = {}
        if path.suffix.lower() in {".tif", ".tiff"} and path.is_file():
            try:
                job_dir = path.parent.parent / "processed"
                if not job_dir.exists():
                    job_dir = path.parent
                vis = render_sar_visualization_products(tif_path=path, output_dir=job_dir, detections=[])
                visualizations = {k: str(v) for k, v in vis.items()}
            except Exception as exc:
                logging.warning(f"[SAR] visualization failed: {exc}")

        answer = _prose(question, scene_stats, tags, backend)
        talk = _try_gemma_talk(path, question, answer)
        if talk:
            answer = f"{talk}\n\n{answer}"

        return {
            "backend": backend,
            "answer": answer,
            "model": "BIFOLD-BigEarthNetv2-0/resnet50-s1-v0.2.0" if backend.startswith("reben") else "sar_backscatter",
            "modality": "SAR",
            "scene_statistics": scene_stats,
            "scene_tags": tags,
            "visualizations": visualizations,
            "status": "success",
        }

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        if isinstance(result, dict):
            return f"sar_map via {result.get('backend')}"
        return "SAR land-cover map produced."


def _prose(question: str, stats: dict[str, Any], tags: list[dict[str, Any]], backend: str) -> str:
    lines = [
        f"**Query:** {question}",
        "",
        "**S1 specialist** ("
        + (
            "reBEN ResNet50 · Sentinel-1 · trained on BigEarthNet v2"
            if backend.startswith("reben")
            else "VV/VH backscatter"
        )
        + ")",
    ]
    if stats:
        lines.append(
            f"Built-up {stats.get('urban_percent', 0)}% · water {stats.get('water_percent', 0)}% · "
            f"vegetation {stats.get('vegetation_percent', 0)}% · other {stats.get('other_percent', 0)}% "
            f"(VV {stats.get('mean_vv_db')} dB / VH {stats.get('mean_vh_db')} dB)."
        )
    if tags:
        lines.append("")
        lines.append("**Scene tags** (BigEarthNet-19 · S1-trained ResNet50)")
        lines.append(" · ".join(f"{t['name']} {int(t['score'] * 100)}" for t in tags))
    return "\n\n".join(lines)


def _try_gemma_talk(path: Path, question: str, evidence: str) -> str | None:
    try:
        from PIL import Image

        from backend.services.sar_service import load_sar_image_to_pil
        from backend.services.vlm import get_vlm_client

        img = load_sar_image_to_pil(path) if path.exists() else Image.new("RGB", (128, 128))
        client = get_vlm_client()
        prompt = (
            "You are reading a Sentinel-1 SAR composite (not optical RGB). "
            "Bright = built-up or rough; dark = water or smooth. "
            "Answer the question using the image and the specialist evidence. "
            "Do not invent coordinates.\n\n"
            f"Question: {question}\n\nEvidence:\n{evidence}"
        )
        return client.generate_multimodal_sync(prompt=prompt, images=[img], temperature=0.0).strip()
    except Exception as exc:
        logging.info(f"[SAR] Gemma talk skipped: {exc}")
        return None
