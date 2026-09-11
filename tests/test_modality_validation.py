"""SatQuery AI — Regression Tests for Modality Validation and Visualization Flow."""

from __future__ import annotations

import pytest
from backend.agents.graph import app, _check_modality_intent_mismatch
from backend.agents.state import GraphState
from backend.schemas import InputClass, RouterTask


def test_modality_mismatch_detection_helper():
    # SAR wording with generic intent on optical -> recoverable to optical
    action, msg = _check_modality_intent_mismatch(
        query="What objects are visible in this SAR image?",
        input_class="SINGLE_OPTICAL",
        assets=[{"filename": "S2_T2.tif", "modality": "OPTICAL"}],
    )
    assert action == "RECOVER_TO_OPTICAL"
    assert "Your uploaded image is optical, not SAR. I'll analyze it as an optical image." in msg

    # Hard SAR physics query on optical -> unrecoverable refusal
    action_refuse, msg_refuse = _check_modality_intent_mismatch(
        query="Analyze the dual-pol VV and VH backscatter and polarimetric properties",
        input_class="SINGLE_OPTICAL",
        assets=[{"filename": "S2_T2.tif", "modality": "OPTICAL"}],
    )
    assert action_refuse == "REFUSE"
    assert "requires SAR/radar" in msg_refuse

    # Hard Optical spectral query on SAR -> unrecoverable refusal
    action_sar, msg_sar = _check_modality_intent_mismatch(
        query="Show the optical RGB bands and NDVI vegetation index",
        input_class="SINGLE_SAR",
        assets=[{"filename": "S1_IW.tif", "modality": "SAR"}],
    )
    assert action_sar == "REFUSE"
    assert "require" in msg_sar.lower() and "optical" in msg_sar.lower()

    # SAR query + SAR asset -> OK (no mismatch)
    action_ok, msg_ok = _check_modality_intent_mismatch(
        query="What objects are visible in this SAR image?",
        input_class="SINGLE_SAR",
        assets=[{"filename": "S1_IW.tif", "modality": "SAR"}],
    )
    assert action_ok is None
    assert msg_ok is None

    # Optical query + Optical asset -> OK (no mismatch)
    action_opt_ok, msg_opt_ok = _check_modality_intent_mismatch(
        query="What is the land cover distribution?",
        input_class="SINGLE_OPTICAL",
        assets=[{"filename": "S2_T2.tif", "modality": "OPTICAL"}],
    )
    assert action_opt_ok is None
    assert msg_opt_ok is None


def test_graph_recovers_sar_wording_on_optical_asset():
    """Verify SAR wording with generic visual intent on OPTICAL asset is recovered and analyzed as optical."""
    initial_state: GraphState = {
        "job_id": "test-sar-opt-recovery",
        "session_id": "test-session-1",
        "user_query": "What objects are visible in this SAR image?",
        "input_class": "SINGLE_OPTICAL",
        "assets": [{"filename": "S2_T2.tif", "modality": "OPTICAL", "file_path": "data/S2_T2.tif"}],
        "asset_metadata": {"input_class": "SINGLE_OPTICAL"},
        "pair_fitness": None,
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
    }

    result = app.invoke(initial_state)

    assert result["status"] == "completed"
    assert "Your uploaded image is optical, not SAR. I'll analyze it as an optical image." in (result.get("final_answer") or "")
    # Ensure optical specialist was executed (lulc_map or yolo_detector), NOT sar_map
    visited = [e["node"] for e in result.get("execution_trace", [])]
    assert ("lulc_map" in visited or "yolo_detector" in visited)
    assert "sar_map" not in visited


def test_graph_refuses_hard_sar_physics_on_optical_asset():
    """Verify true SAR physics request on OPTICAL asset is refused."""
    initial_state: GraphState = {
        "job_id": "test-sar-physics-refusal",
        "session_id": "test-session-1b",
        "user_query": "Analyze dual-pol VV backscatter and polarimetric properties",
        "input_class": "SINGLE_OPTICAL",
        "assets": [{"filename": "S2_T2.tif", "modality": "OPTICAL", "file_path": "data/S2_T2.tif"}],
        "asset_metadata": {"input_class": "SINGLE_OPTICAL"},
        "pair_fitness": None,
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
    }

    result = app.invoke(initial_state)

    assert result["status"] == "refused"
    assert "requires SAR/radar" in (result.get("refusal_reason") or "")


def test_graph_refuses_optical_query_on_sar_asset():
    """Verify Optical query + SAR asset is refused."""
    initial_state: GraphState = {
        "job_id": "test-opt-sar-mismatch",
        "session_id": "test-session-2",
        "user_query": "Analyze the optical true color RGB bands in this scene",
        "input_class": "SINGLE_SAR",
        "assets": [{"filename": "S1_GRD.tif", "modality": "SAR", "file_path": "data/S1_GRD.tif"}],
        "asset_metadata": {"input_class": "SINGLE_SAR"},
        "pair_fitness": None,
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
    }

    result = app.invoke(initial_state)

    assert result["status"] == "refused"
    assert "require" in (result.get("refusal_reason") or "").lower()

    visited = [e["node"] for e in result.get("execution_trace", [])]
    assert "sar_map" not in visited
    assert "lulc_map" not in visited


def test_execution_trace_does_not_duplicate_nodes():
    """Verify execution trace does not record adjacent identical nodes."""
    initial_state: GraphState = {
        "job_id": "test-trace-dedup",
        "session_id": "test-session-3",
        "user_query": "Describe the scene.",
        "input_class": "SINGLE_OPTICAL",
        "assets": [],
        "asset_metadata": {"input_class": "SINGLE_OPTICAL"},
        "pair_fitness": None,
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
        "injected_task": "CAPTIONING",
    }

    result = app.invoke(initial_state)
    visited = [e["node"] for e in result.get("execution_trace", [])]

    # No node should appear more than once in the execution sequence
    seen = set()
    duplicates = []
    for node in visited:
        if node in seen:
            duplicates.append(node)
        seen.add(node)

    assert len(duplicates) == 0, f"Duplicate nodes found in execution trace: {duplicates}"


def test_final_reasoner_optical_lulc_synthesis_grounding():
    """Verify FinalReasoner synthesizes natural language answers based on query and does not invent objects."""
    from backend.agents.final_reasoner import _synthesize_optical_lulc_answer

    fractions = {"bare": 0.89, "water": 0.11, "vegetation": 0.0, "built": 0.0}

    # Test 1: "Explain this TIFF image"
    ans_explain = _synthesize_optical_lulc_answer("Explain this TIFF image.", fractions, method="spectral_fallback")
    assert "bare" in ans_explain.lower() or "open" in ans_explain.lower()
    assert "89%" in ans_explain or "89" in ans_explain
    assert "11%" in ans_explain or "11" in ans_explain
    # Verify no raw debug headers
    assert "Land Cover Classification (Optical spectral fallback)" not in ans_explain
    assert "Pixel map" not in ans_explain

    # Test 2: "What percentage of the image is water?"
    ans_water = _synthesize_optical_lulc_answer("What percentage of the image is water?", fractions, method="spectral_fallback")
    assert "11%" in ans_water or "11" in ans_water
    assert "water" in ans_water.lower()

    # Test 3: "What objects are visible?" (Grounding check: aggregate fractions must not claim object detection)
    ans_obj = _synthesize_optical_lulc_answer("What objects are visible in this scene?", fractions, method="spectral_fallback")
    assert "no discrete object instances" in ans_obj.lower() or "object" in ans_obj.lower()
    assert "89%" in ans_obj


def test_ingest_preview_generation_raster(tmp_path):
    """Verify raster ingest creates high-fidelity RGB preview PNG alongside raw TIFF."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_bounds
    from backend.services.job_view import resolve_composite_path

    # Create dummy GeoTIFF inside job's raw/ directory
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    tif_path = raw_dir / "sample_scene.tif"
    data = np.random.randint(20, 220, (3, 64, 64), dtype=np.uint8)
    transform = from_bounds(72.5, 23.0, 72.7, 23.2, 64, 64)
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=64,
        width=64,
        count=3,
        dtype=np.uint8,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(data)

    # Resolve composite preview path (should generate PNG preview on the fly if needed)
    preview = resolve_composite_path(tmp_path)
    assert preview is not None
    assert preview.exists()
    assert preview.suffix.lower() == ".png"

