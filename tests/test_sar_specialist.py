"""Tests for sar_map specialist tool and SAR backscatter radiometry."""

import pytest
import numpy as np
from backend.agents.tools.sar_map import SarMapTool
from backend.services.sar_ben import BenS1Classifier


def test_sar_map_tool_instantiation():
    tool = SarMapTool()
    assert tool.tool_id == "sar_map"


def test_sar_ben_classifier_instance():
    classifier = BenS1Classifier.get_instance()
    assert classifier is not None
    assert classifier.is_available() is True, "reBEN ResNet50 weights must be available"


def test_sar_ben_classifier_predict():
    classifier = BenS1Classifier.get_instance()
    # 2-channel VV/VH dummy tensor (linear amplitude)
    stack = np.random.uniform(0.01, 0.5, size=(2, 120, 120)).astype(np.float32)
    tags = classifier.predict(stack, top_k=3)
    assert len(tags) > 0
    assert "name" in tags[0]
    assert "score" in tags[0]


def test_sar_asset_graph_routing_to_sar_map(tmp_path):
    """Verify SAR single asset query routes to sar_map and never to lulc_map."""
    import rasterio
    from rasterio.transform import from_bounds
    from backend.agents.graph import app
    from backend.agents.state import GraphState

    # Create dummy 2-band float32 SAR GeoTIFF
    tif_path = tmp_path / "S1_T1.tif"
    arr = np.random.uniform(0.01, 0.5, size=(2, 64, 64)).astype(np.float32)
    transform = from_bounds(72.8, 19.0, 72.9, 19.1, 64, 64)
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=64,
        width=64,
        count=2,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(arr)

    initial_state: GraphState = {
        "job_id": "test-sar-graph-job",
        "session_id": "sess-sar-1",
        "user_query": "Explain me the SAR image",
        "input_class": "SINGLE_SAR",
        "assets": [{"filename": "S1_T1.tif", "modality": "SAR", "file_path": str(tif_path)}],
        "asset_metadata": {"input_class": "SINGLE_SAR"},
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
    }

    result = app.invoke(initial_state)
    visited = [e["node"] for e in result.get("execution_trace", [])]

    # Verify routing
    assert "sar_map" in visited
    assert "lulc_map" not in visited
    assert result["status"] == "completed"

    answer = result.get("final_answer", "")
    assert "optical satellite image" not in answer.lower()
    assert "SAR" in answer or "Sentinel-1" in answer or "backscatter" in answer.lower()


def test_sar_modality_recovery_from_optical_wording(tmp_path):
    """Verify 'Explain this optical image' on a SAR asset recovers to SAR and runs sar_map."""
    import rasterio
    from rasterio.transform import from_bounds
    from backend.agents.graph import app
    from backend.agents.state import GraphState

    tif_path = tmp_path / "S1_T1.tif"
    arr = np.random.uniform(0.01, 0.5, size=(2, 64, 64)).astype(np.float32)
    transform = from_bounds(72.8, 19.0, 72.9, 19.1, 64, 64)
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=64,
        width=64,
        count=2,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(arr)

    initial_state: GraphState = {
        "job_id": "test-sar-recovery-job",
        "session_id": "sess-sar-2",
        "user_query": "Explain this optical image",
        "input_class": "SINGLE_SAR",
        "assets": [{"filename": "S1_T1.tif", "modality": "SAR", "file_path": str(tif_path)}],
        "asset_metadata": {"input_class": "SINGLE_SAR"},
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
    }

    result = app.invoke(initial_state)
    visited = [e["node"] for e in result.get("execution_trace", [])]

    assert "sar_map" in visited
    assert "lulc_map" not in visited
    assert result["status"] == "completed"
    assert "Your uploaded image is SAR/radar, not optical" in result.get("modality_recovery_note", "")

