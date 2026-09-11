"""
Tests for BIT LEVIR ONNX Change Detection Service and Tool.
"""

import os
from pathlib import Path
import numpy as np
from PIL import Image
import pytest

from backend.services.bit_service import BITService
from backend.agents.tools.bit_cd import BITChangeDetectionTool
from backend.agents.tools.executor import _TOOL_IMPLEMENTATIONS, run_tool
from backend.agents.tools.base import ToolResult
from backend.agents.final_reasoner import FinalReasoner, format_rich_bit_change_answer


def test_bit_model_loading():
    """Verify that BIT ONNX model and external weights load successfully."""
    service = BITService.get_instance()
    session = service._load_session()
    assert session is not None
    assert len(service.providers) > 0
    assert service.input_name_1 == "img1"
    assert service.input_name_2 == "img2"
    assert service.output_name == "pred"


def test_bit_preprocessing():
    """Verify image preprocessing converts RGB to [-1.0, 1.0] float32 tensor."""
    service = BITService.get_instance()
    rgb = np.full((100, 100, 3), 255, dtype=np.uint8)
    tensor = service.preprocess_tensor(rgb)
    assert tensor.shape == (1, 3, 100, 100)
    assert tensor.dtype == np.float32
    assert np.isclose(tensor.max(), 1.0)

    rgb_dark = np.zeros((100, 100, 3), dtype=np.uint8)
    tensor_dark = service.preprocess_tensor(rgb_dark)
    assert np.isclose(tensor_dark.min(), -1.0)


def test_bit_inference_and_postprocessing(tmp_path):
    """Verify real ONNX inference produces binary change mask and GeoJSON metrics."""
    service = BITService.get_instance()

    img1 = np.zeros((256, 256, 3), dtype=np.uint8)
    img2 = np.zeros((256, 256, 3), dtype=np.uint8)
    # Add a mock change
    img2[60:120, 60:120] = 255

    res = service.run_change_detection(img1, img2, output_dir=tmp_path)
    assert res["success"] is True
    assert "statistics" in res
    assert "geojson" in res
    assert res["statistics"]["total_pixels"] == 256 * 256
    assert isinstance(res["summary"], str)


def test_bit_tool_registration():
    """Verify that bit_cd maps to BITChangeDetectionTool in executor registry."""
    assert "bit_cd" in _TOOL_IMPLEMENTATIONS
    assert _TOOL_IMPLEMENTATIONS["bit_cd"] is BITChangeDetectionTool


def test_bit_tool_execution(tmp_path):
    """Verify BITChangeDetectionTool runs and returns valid ToolResult structure."""
    tool = BITChangeDetectionTool()

    # Save two small sample PNGs
    p1 = tmp_path / "pre.png"
    p2 = tmp_path / "post.png"
    Image.new("RGB", (128, 128), color=(50, 50, 50)).save(p1)
    Image.new("RGB", (128, 128), color=(200, 200, 200)).save(p2)

    params = {
        "pre_image": str(p1),
        "post_image": str(p2),
        "input_refs": [str(p1), str(p2)],
    }
    result = tool.execute(params)
    assert isinstance(result, ToolResult)
    assert result.status == "success"
    assert "statistics" in result.result
    assert "geojson" in result.result


def test_final_reasoner_bit_synthesis():
    """Verify FinalReasoner formats rich BIT change detection results."""
    stats = {
        "change_percentage": 4.5,
        "changed_area_m2": 45000.0,
        "changed_area_km2": 0.045,
        "region_count": 3,
        "total_pixels": 1000000,
        "changed_pixels": 45000,
        "crs": "EPSG:4326",
    }
    dets = [
        {"centroid": [77.5946, 12.9716], "area_m2": 15000.0},
        {"centroid": [77.6000, 12.9800], "area_m2": 30000.0},
    ]
    formatted = format_rich_bit_change_answer(
        query="Detect urban growth between 2023 and 2024",
        summary="BIT identified 4.5% expansion.",
        statistics=stats,
        detections=dets,
    )
    assert "Optical Bi-Temporal Change Detection Analysis (BIT-LEVIR)" in formatted
    assert "4.50% of AOI" in formatted
    assert "45,000.0 m²" in formatted
    assert "Cluster #1" in formatted


def test_sar_pipeline_regression():
    """Verify that SARChat tool and service remain intact."""
    from backend.services.sar_service import get_sar_service
    from backend.agents.tools.sarchat import SARChatTool

    assert _TOOL_IMPLEMENTATIONS["sarchat_vqa"] is SARChatTool
    sar_service = get_sar_service()
    assert sar_service is not None


def test_bit_graph_execution_path_without_mocks(tmp_path):
    """Verify that LangGraph executes bit_cd directly without MockAlign or MockVectorize."""
    from backend.agents.graph import app
    from backend.schemas import InputClass, RouterTask

    p1 = tmp_path / "t1.png"
    p2 = tmp_path / "t2.png"
    Image.new("RGB", (64, 64), color=(30, 30, 30)).save(p1)
    Image.new("RGB", (64, 64), color=(200, 200, 200)).save(p2)

    initial_state = {
        "job_id": "test_job_123",
        "session_id": "test_session_123",
        "user_query": "Detect changes between T1 and T2 images",
        "input_class": InputClass.BI_TEMPORAL,
        "assets": [str(p1), str(p2)],
        "asset_metadata": {"assets": [str(p1), str(p2)]},
        "pair_fitness": {"score": 1.0},
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
        "injected_task": RouterTask.CHANGE_DETECTION.value,
    }

    result = app.invoke(initial_state)

    trace = result.get("execution_trace", [])
    node_names = [item["node"] if isinstance(item, dict) else item for item in trace]
    # Verify execution trace contains expected production nodes
    assert "preprocess" in node_names
    assert "bit_cd" in node_names
    assert "evidence_fusion" in node_names
    assert "report_generator" in node_names

    # Critical assertions: MockAlign and MockVectorize are NOT executed
    assert "align" not in node_names
    assert "vectorize" not in node_names

    # Verify specialist_results contains bit_cd result
    specialist_ids = [
        getattr(r, "tool_id", None) or (r.get("tool_id") if isinstance(r, dict) else None)
        for r in result.get("specialist_results", [])
    ]
    assert "bit_cd" in specialist_ids
    assert "align" not in specialist_ids
    assert "vectorize" not in specialist_ids

