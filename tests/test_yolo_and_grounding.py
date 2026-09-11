"""
SatQuery AI — Comprehensive Tests for EO YOLO Specialist, Mask Validation, and AnalysisObjects
"""

import os
import tempfile
import pytest
import numpy as np
from pathlib import Path
from shapely.geometry import Polygon, mapping

from backend.schemas import AnalysisObject, RouterTask, InputClass
from backend.services.mask_validator import (
    validate_mask_array,
    validate_geometry,
    compute_geodetic_metrics,
    validate_and_build_analysis_object,
)
from backend.services.yolo_specialist import (
    EOYOLOSpecialist,
    EOYOLODatasetPreparer,
    EO_YOLO_CLASSES,
)
from backend.agents.tools.yolo_detector import YOLODetectorTool
from backend.agents.tools.executor import run_tool
from backend.agents.tool_selector import ToolSelector
from backend.agents.final_reasoner import FinalReasoner
from backend.agents.tools.base import ToolResult


def test_analysis_object_schema():
    """Verify AnalysisObject instantiation and serialization."""
    geom = {
        "type": "Polygon",
        "coordinates": [[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]],
    }
    obj = AnalysisObject(
        object_id="test_obj_1",
        target="building",
        modality="OPTICAL",
        sensor="Sentinel-2",
        geometry=geom,
        bbox=[77.5, 12.9, 77.6, 13.0],
        centroid=[77.55, 12.95],
        label="Commercial Building Cluster",
        confidence=0.92,
        source_model="EO-YOLO-RemoteSensing",
        provenance={"algorithm": "yolov8_rs"},
    )
    assert obj.object_id == "test_obj_1"
    assert obj.confidence == 0.92
    assert obj.modality == "OPTICAL"
    dumped = obj.model_dump()
    assert dumped["target"] == "building"
    assert dumped["bbox"] == [77.5, 12.9, 77.6, 13.0]


def test_mask_validator_array():
    """Verify raster mask array validation rules."""
    # 1. Valid mask
    valid_mask = np.zeros((100, 100), dtype=bool)
    valid_mask[20:40, 20:40] = True
    is_valid, reason = validate_mask_array(valid_mask)
    assert is_valid is True
    assert reason is None

    # 2. Empty mask
    empty_mask = np.zeros((100, 100), dtype=bool)
    is_valid, reason = validate_mask_array(empty_mask)
    assert is_valid is False
    assert "empty" in reason.lower()

    # 3. Degenerate full-frame mask
    full_mask = np.ones((100, 100), dtype=bool)
    is_valid, reason = validate_mask_array(full_mask, allow_full_scene=False)
    assert is_valid is False
    assert "suspicious" in reason.lower()


def test_mask_validator_geometry():
    """Verify GeoJSON polygon validation and fake mask rejection."""
    scene_bounds = [77.0, 12.0, 78.0, 13.0]

    # 1. Valid contained polygon
    poly = Polygon([(77.2, 12.2), (77.4, 12.2), (77.4, 12.4), (77.2, 12.4), (77.2, 12.2)])
    is_valid, geom, reason = validate_geometry(mapping(poly), scene_bounds_wgs84=scene_bounds)
    assert is_valid is True
    assert geom is not None

    # 2. Out-of-bounds polygon
    oob_poly = Polygon([(85.0, 20.0), (86.0, 20.0), (86.0, 21.0), (85.0, 21.0), (85.0, 20.0)])
    is_valid, geom, reason = validate_geometry(mapping(oob_poly), scene_bounds_wgs84=scene_bounds)
    assert is_valid is False
    assert "exceed scene bounds" in reason.lower()

    # 3. Degenerate full scene bounding box passed off as detection (Fake mask rejection)
    scene_box = Polygon([
        (scene_bounds[0], scene_bounds[1]),
        (scene_bounds[2], scene_bounds[1]),
        (scene_bounds[2], scene_bounds[3]),
        (scene_bounds[0], scene_bounds[3]),
        (scene_bounds[0], scene_bounds[1]),
    ])
    is_valid, geom, reason = validate_geometry(mapping(scene_box), scene_bounds_wgs84=scene_bounds)
    assert is_valid is False
    assert "fake mask" in reason.lower()


def test_geodetic_metrics():
    """Verify area in m^2 and centroid calculations."""
    poly = Polygon([(77.0, 12.0), (77.01, 12.0), (77.01, 12.01), (77.0, 12.01), (77.0, 12.0)])
    area_m2, centroid, bbox = compute_geodetic_metrics(mapping(poly))
    assert area_m2 > 1000.0
    assert len(centroid) == 2
    assert 77.0 <= centroid[0] <= 77.01
    assert 12.0 <= centroid[1] <= 12.01


def test_eo_yolo_dataset_prep():
    """Verify dataset YAML generation for EO YOLO."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "eo_yolo.yaml"
        res_path = EOYOLODatasetPreparer.create_yolo_dataset_yaml(
            dataset_dir=tmpdir,
            train_path="images/train",
            val_path="images/val",
            yaml_output_path=yaml_path,
        )
        assert res_path.is_file()
        content = res_path.read_text()
        assert "building" in content
        assert "water_body" in content
        assert "vessel_ship" in content


def test_eo_yolo_modality_safety():
    """Verify EO YOLO strictly refuses SAR inputs (§1, §2, §5)."""
    specialist = EOYOLOSpecialist.get_instance()
    with tempfile.NamedTemporaryFile(suffix=".tif") as tmp:
        # Should raise ValueError when modality is SAR
        with pytest.raises(ValueError) as exc:
            specialist.detect(raster_path=tmp.name, modality="SAR")
        assert "Incompatible modality" in str(exc.value)


def test_eo_yolo_detector_tool_execution():
    """Verify YOLODetectorTool executes and returns structured results."""
    tool = YOLODetectorTool()
    
    # 1. Validation check on missing image refs
    with pytest.raises(ValueError):
        tool.validate({})

    # 2. Validation check refusing SAR
    with pytest.raises(ValueError):
        tool.validate({"image_refs": ["test.tif"], "modality": "SAR"})

    # 3. Execution via run_tool
    res = run_tool("yolo_detector", {"image_refs": ["non_existent.tif"], "modality": "OPTICAL"})
    assert res.tool_id == "yolo_detector"
    assert res.status == "success"
    assert res.result.get("count") == 0


def test_tool_selector_capability_matrix():
    """Verify ToolSelector routing and capability enforcement for yolo_detector."""
    selector = ToolSelector()
    assert "yolo_detector" in selector.CAPABILITY_MATRIX
    cap = selector.CAPABILITY_MATRIX["yolo_detector"]
    assert "SINGLE_OPTICAL" in cap["modalities"]
    assert "SINGLE_SAR" not in cap["modalities"]


def test_final_reasoner_synthesis_grounding():
    """Verify FinalReasoner synthesizes YOLO and specialist evidence cleanly."""
    reasoner = FinalReasoner()
    
    yolo_result = ToolResult(
        tool_id="yolo_detector",
        status="success",
        result={
            "count": 2,
            "objects": [
                {
                    "object_id": "obj_1",
                    "label": "Commercial Building Cluster",
                    "confidence": 0.89,
                    "centroid": [77.52, 12.95],
                    "area_m2": 15400.0,
                },
                {
                    "object_id": "obj_2",
                    "label": "Water Body Region",
                    "confidence": 0.94,
                    "centroid": [77.58, 12.98],
                    "area_m2": 45000.0,
                },
            ],
        },
        explanation="Detected 2 objects",
    )
    
    summary = reasoner._fallback_synthesis(
        query="Detect and ground infrastructure in this image",
        specialist_results=[yolo_result],
    )
    
    assert "Commercial Building Cluster" in summary
    assert "Water Body Region" in summary
    assert "89.0%" in summary
    assert "15,400.0 m²" in summary
    assert "coarse estimates mapped from" not in summary.lower()
