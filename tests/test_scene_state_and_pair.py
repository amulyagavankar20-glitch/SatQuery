"""SatQuery AI — Comprehensive Tests for Scene State, Pair Gates, and Modality Routing."""

from __future__ import annotations

import pytest
from backend.agents.graph import app
from backend.agents.state import GraphState
from backend.schemas import InputClass, RouterTask
from backend.services.geospatial import compute_spatial_overlap
from backend.services.input_classifier import InputClassifier
from backend.agents.tools.lulc import _classify_optical_scene, _read_raster_with_meta
import numpy as np


def test_single_image_query_does_not_execute_pair_fitness_gate():
    """Verify single-image explanation queries bypass pair_fitness_gate."""
    initial_state: GraphState = {
        "job_id": "test-single-bypass",
        "session_id": "sess-single-1",
        "user_query": "Explain this TIFF image",
        "input_class": "SINGLE_OPTICAL",
        "assets": [{"filename": "S2_T1.tif", "modality": "OPTICAL", "file_path": "data/S2_T1.tif"}],
        "asset_metadata": {"input_class": "SINGLE_OPTICAL"},
        "pair_fitness": {"compatible": False, "has_sufficient_overlap": False},
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
        "injected_task": "SINGLE_VQA",
    }

    result = app.invoke(initial_state)
    visited = [e["node"] for e in result.get("execution_trace", [])]

    # pair_fitness_gate MUST NOT be executed for a single-image query
    assert "pair_fitness_gate" not in visited
    assert result["status"] == "completed"
    assert "Insufficient spatial overlap" not in (result.get("refusal_reason") or "")


def test_pair_query_executes_pair_fitness_gate_and_refuses_non_overlapping():
    """Verify change/pair query executes pair_fitness_gate and catches non-overlapping pairs."""
    initial_state: GraphState = {
        "job_id": "test-pair-gate",
        "session_id": "sess-pair-1",
        "user_query": "What changed between T1 and T2?",
        "input_class": "BI_TEMPORAL",
        "assets": [
            {"filename": "T1.tif", "modality": "OPTICAL", "file_path": "data/T1.tif"},
            {"filename": "T2.tif", "modality": "OPTICAL", "file_path": "data/T2.tif"},
        ],
        "asset_metadata": {"input_class": "BI_TEMPORAL", "mode": "pair"},
        "pair_fitness": {"compatible": False, "has_sufficient_overlap": False, "reason": "Insufficient spatial overlap between image pair."},
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
    }

    result = app.invoke(initial_state)
    visited = [e["node"] for e in result.get("execution_trace", [])]

    # pair_fitness_gate MUST execute for a pair query
    assert "pair_fitness_gate" in visited
    assert result["status"] == "refused"
    assert "Insufficient spatial overlap between image pair" in (result.get("refusal_reason") or "")


def test_pair_gate_with_sufficient_overlap_proceeds():
    """Verify pair query with verified overlap proceeds past pair_fitness_gate."""
    initial_state: GraphState = {
        "job_id": "test-pair-gate-ok",
        "session_id": "sess-pair-2",
        "user_query": "What changed between these images?",
        "input_class": "BI_TEMPORAL",
        "assets": [
            {"filename": "T1.tif", "modality": "OPTICAL", "file_path": "data/T1.tif"},
            {"filename": "T2.tif", "modality": "OPTICAL", "file_path": "data/T2.tif"},
        ],
        "asset_metadata": {"input_class": "BI_TEMPORAL", "mode": "pair"},
        "pair_fitness": {"compatible": True, "has_sufficient_overlap": True, "iou": 0.85},
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
        "injected_task": "CHANGE_DETECTION",
    }

    result = app.invoke(initial_state)
    visited = [e["node"] for e in result.get("execution_trace", [])]

    assert "pair_fitness_gate" in visited
    assert "query_router" in visited
    assert result["status"] != "refused"


def test_stale_pair_fitness_does_not_contaminate_switched_single_scene():
    """Verify that when 2 assets exist in the session, a single-scene query on T2 succeeds without pair failure."""
    initial_state: GraphState = {
        "job_id": "test-switch-single",
        "session_id": "sess-switch-1",
        "user_query": "Describe the land cover in this scene",
        "input_class": "BI_TEMPORAL",
        "assets": [
            {"filename": "T1.tif", "modality": "OPTICAL", "file_path": "data/T1.tif"},
            {"filename": "T2.tif", "modality": "OPTICAL", "file_path": "data/T2.tif"},
        ],
        "asset_metadata": {"input_class": "BI_TEMPORAL", "active_slot": "T2", "mode": "single_scene"},
        "pair_fitness": {"compatible": False, "has_sufficient_overlap": False, "reason": "Insufficient spatial overlap between image pair."},
        "warnings": [],
        "status": "running",
        "specialist_results": [],
        "execution_trace": [],
        "injected_task": "CAPTIONING",
    }

    result = app.invoke(initial_state)
    visited = [e["node"] for e in result.get("execution_trace", [])]

    assert "pair_fitness_gate" not in visited
    assert result["status"] == "completed"
    assert "Insufficient spatial overlap" not in (result.get("refusal_reason") or "")


def test_spatial_overlap_reprojection_handling():
    """Verify compute_spatial_overlap correctly handles different CRS projections (e.g. UTM vs WGS84)."""
    # Footprint 1 in UTM Zone 43N (EPSG:32643) covering Mumbai area
    # ~ (72.865, 19.064, 72.890, 19.087) in WGS84
    utm_bounds = [275380.0, 2108600.0, 277940.0, 2111160.0]
    utm_crs = "EPSG:32643"

    # Footprint 2 in WGS84 (EPSG:4326) directly over Mumbai
    wgs_bounds = [72.860, 19.060, 72.895, 19.090]
    wgs_crs = "EPSG:4326"

    rel = compute_spatial_overlap(utm_bounds, utm_crs, wgs_bounds, wgs_crs)
    assert rel.has_sufficient_overlap is True
    assert rel.iou > 0.4
    assert rel.intersection_bbox_wgs84 is not None


def test_spatial_overlap_disjoint_returns_false():
    """Verify disjoint footprints return has_sufficient_overlap = False."""
    bounds1 = [72.0, 19.0, 72.1, 19.1]
    bounds2 = [75.0, 25.0, 75.1, 25.1]

    rel = compute_spatial_overlap(bounds1, "EPSG:4326", bounds2, "EPSG:4326")
    assert rel.has_sufficient_overlap is False
    assert rel.iou == 0.0
    assert rel.intersection_bbox_wgs84 is None


def test_input_classifier_permissive_on_disjoint_ingest():
    """Verify InputClassifier permits ingestion of non-overlapping dual rasters without premature refusal."""
    classifier = InputClassifier()
    asset_inputs = [
        {"filename": "scene_a.tif", "sensor": "Sentinel-2", "bounds": [72.0, 19.0, 72.1, 19.1], "crs": "EPSG:4326", "modality": "OPTICAL"},
        {"filename": "scene_b.tif", "sensor": "Sentinel-2", "bounds": [75.0, 25.0, 75.1, 25.1], "crs": "EPSG:4326", "modality": "OPTICAL"},
    ]
    analysis = classifier.analyzer.analyze_inputs(asset_inputs)
    classification = classifier.classify(asset_inputs, analysis_metadata=analysis)

    # Ingest is valid (files uploaded), but spatial relationship notes lack of overlap
    assert classification.valid is True
    assert classification.refusal_reason is None
    assert classification.spatial_relationship is not None
    assert classification.spatial_relationship.has_sufficient_overlap is False
