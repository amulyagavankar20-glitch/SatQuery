"""
Specialist Tool: Earth Observation YOLO Detector (tool_id: yolo_detector)

Executes remote sensing object detection and instance grounding on optical satellite imagery.
Generates georeferenced AnalysisObjects with bounding boxes and contour geometries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Mapping

from backend.agents.tools.base import BaseTool
from backend.services.yolo_specialist import EOYOLOSpecialist
from src.logger import logging


class YOLODetectorTool(BaseTool):
    """
    Specialist tool for optical remote sensing object detection powered by EO-YOLO.
    Produces structured AnalysisObjects containing bounding boxes, centroids, and labels.
    """

    tool_id = "yolo_detector"

    def __init__(self) -> None:
        self.specialist = EOYOLOSpecialist.get_instance()

    def validate(self, params: Mapping[str, Any]) -> None:
        if "image_refs" not in params or not params["image_refs"]:
            raise ValueError("yolo_detector requires image_refs")
        
        modality = str(params.get("modality") or "OPTICAL").upper()
        if "SAR" in modality:
            raise ValueError("yolo_detector only operates on optical imagery and cannot process SAR data.")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        image_refs = params.get("image_refs", [])
        if not image_refs:
            return {"objects": [], "count": 0}

        path = Path(image_refs[0])
        modality = str(params.get("modality") or "OPTICAL")
        target_classes = params.get("target_classes")
        bounds = params.get("bounds")
        scene_id = params.get("scene_id")
        asset_id = params.get("asset_id")

        objects = self.specialist.detect(
            raster_path=path,
            modality=modality,
            target_classes=target_classes,
            bounds=bounds,
            scene_id=scene_id,
            asset_id=asset_id,
        )

        return {
            "objects": [obj.model_dump() for obj in objects],
            "count": len(objects),
            "source_model": "EO-YOLO-RemoteSensing",
        }

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        count = result.get("count", 0) if isinstance(result, dict) else 0
        return f"EO YOLO object detection identified {count} georeferenced spatial objects."

    def execute(self, params: Mapping[str, Any]):
        result = super().execute(params)
        payload = result.result
        if isinstance(payload, dict) and result.status == "success":
            objects = payload.get("objects") or []
            conf = max([float(o.get("confidence", 0.0)) for o in objects], default=0.85) if objects else 0.85
            features = []
            for i, o in enumerate(objects, 1):
                geom = o.get("geometry")
                if geom:
                    features.append({
                        "type": "Feature",
                        "properties": {
                            "id": o.get("object_id", f"yolo_{i}"),
                            "feature_type": "DETECTION",
                            "kind": "grounding",
                            "class": o.get("target", "object"),
                            "label": o.get("label", f"Object #{i}"),
                            "confidence": float(o.get("confidence", 0.85)),
                            "fill": "#ff4757",
                            "stroke": "#ff6b81",
                        },
                        "geometry": geom,
                    })
            return result.model_copy(update={"confidence": conf, "spatial_refs": features})
        return result

