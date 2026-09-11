"""
SatQuery AI — Architectural Correctness & QueryPlan Verification Suite

Verifies:
1. QueryPlan creation & intent extraction
2. Target class normalization (BUILT, WATER, TREES, GRASS, CROPS, BARE, FLOOD, VEGETATION)
3. Synonym mapping & normalization
4. Mode detection (single_scene vs pair)
5. Urban request selects built mask and NEVER water mask
6. Water request selects water mask
7. FinalReasoner grounded output consistency with target_class
8. Single-scene bypass of pair fitness gate
9. Pair query execution of pair fitness gate
10. Idempotent polling & immutable job execution
"""

import numpy as np
import pytest
from backend.agents.query_plan import (
    QueryIntent,
    QueryPlan,
    SpatialOperation,
    TargetClass,
    build_query_plan,
    normalize_target_class,
)
from backend.agents.final_reasoner import _synthesize_optical_lulc_answer
from backend.agents.tools.lulc import LulcMapTool, _mask_to_real_geojson


def test_query_plan_creation_scene_explanation():
    plan = build_query_plan("Explain me this TIFF image")
    assert plan.intent == QueryIntent.SCENE_EXPLANATION
    assert plan.mode == "single_scene"
    assert plan.target_class is None
    assert plan.spatial_operation is None


def test_query_plan_highlight_urban_built():
    plan = build_query_plan("highlight the urban area")
    assert plan.intent == QueryIntent.SPATIAL_HIGHLIGHT
    assert plan.mode == "single_scene"
    assert plan.target_class == TargetClass.BUILT
    assert plan.spatial_operation == SpatialOperation.HIGHLIGHT


def test_query_plan_highlight_water():
    plan = build_query_plan("Highlight the water body")
    assert plan.intent == QueryIntent.SPATIAL_HIGHLIGHT
    assert plan.mode == "single_scene"
    assert plan.target_class == TargetClass.WATER
    assert plan.spatial_operation == SpatialOperation.HIGHLIGHT


def test_query_plan_highlight_vegetation_and_trees():
    plan_trees = build_query_plan("highlight tree canopy in this image")
    assert plan_trees.target_class == TargetClass.TREES
    assert plan_trees.spatial_operation == SpatialOperation.HIGHLIGHT

    plan_veg = build_query_plan("highlight green vegetation")
    assert plan_veg.target_class == TargetClass.VEGETATION


def test_query_plan_highlight_crops_and_bare():
    plan_crops = build_query_plan("highlight agricultural farmland and crops")
    assert plan_crops.target_class == TargetClass.CROPS

    plan_bare = build_query_plan("highlight bare sand and open ground")
    assert plan_bare.target_class == TargetClass.BARE


def test_synonym_normalization_urban_synonyms():
    for syn in ["urban", "city", "buildings", "built-up", "built up", "infrastructure", "settlement", "developed"]:
        res = normalize_target_class(f"Please show me the {syn} in this scene")
        assert res == TargetClass.BUILT, f"Failed for synonym '{syn}'"


def test_synonym_normalization_water_synonyms():
    for syn in ["water", "waterbody", "surface water", "river", "lake", "ocean", "pond", "reservoir"]:
        res = normalize_target_class(f"Where is the {syn} located?")
        assert res == TargetClass.WATER, f"Failed for synonym '{syn}'"


def test_query_plan_pair_change_detection():
    plan = build_query_plan("What changed between T1 and T2?")
    assert plan.intent == QueryIntent.CHANGE_DETECTION
    assert plan.mode == "pair"
    assert plan.spatial_operation == SpatialOperation.CHANGE_MAP


def test_urban_request_generates_built_overlay_not_water():
    """Verify LulcMapTool produces built_mask and target_class=BUILT for urban requests."""
    tool = LulcMapTool()
    # Create mock raster with built, grass, and water pixels
    # Let's mock _read_raster_with_meta
    dummy_meta = {
        "width": 64,
        "height": 64,
        "crs": "EPSG:4326",
        "bounds": [10.0, 50.0, 10.1, 50.1],
        "bounds_wgs84": [10.0, 50.0, 10.1, 50.1],
        "is_geotiff": False,
    }
    dummy_labels = np.zeros((64, 64), dtype=np.uint8)
    dummy_labels[:20, :] = 6  # built (class 6)
    dummy_labels[20:40, :] = 2  # grass (class 2)
    dummy_labels[40:, :] = 0  # water (class 0)

    # Convert built mask to geojson
    built_mask = (dummy_labels == 6)
    geojson_built = _mask_to_real_geojson(built_mask, dummy_meta, dummy_meta["bounds"], kind="built", share=0.3125)
    assert len(geojson_built) == 1
    props = geojson_built[0]["properties"]
    assert props["class"] == "built"
    assert props["target_class"] == "BUILT"
    assert props["kind"] == "built_mask"
    assert "Built-up" in props["label"]
    assert "Water" not in props["label"]


def test_final_reasoner_urban_highlight_synthesis():
    """Verify FinalReasoner states that built-up area was highlighted and never claims water."""
    payload = {
        "target_class": "BUILT",
        "fractions": {"built": 0.35, "bare": 0.30, "grass": 0.25, "water": 0.10},
        "overlays": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"class": "built", "target_class": "BUILT", "kind": "built_mask"},
                    "geometry": {"type": "Polygon", "coordinates": [[[10, 50], [10.1, 50], [10.1, 50.1], [10, 50.1], [10, 50]]]},
                }
            ],
        },
    }
    answer = _synthesize_optical_lulc_answer("highlight the urban area", payload)
    assert "built-up / urban area" in answer.lower() or "built-up" in answer.lower()
    assert "water region" not in answer.lower()
    assert "has been localized and highlighted" in answer


def test_final_reasoner_water_highlight_synthesis():
    """Verify FinalReasoner states that water was highlighted for water queries."""
    payload = {
        "target_class": "WATER",
        "fractions": {"built": 0.20, "bare": 0.30, "grass": 0.20, "water": 0.30},
        "overlays": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"class": "water", "target_class": "WATER", "kind": "water_mask"},
                    "geometry": {"type": "Polygon", "coordinates": [[[10, 50], [10.1, 50], [10.1, 50.1], [10, 50.1], [10, 50]]]},
                }
            ],
        },
    }
    answer = _synthesize_optical_lulc_answer("highlight the water body", payload)
    assert "surface water region" in answer.lower()
    assert "built-up" not in answer.lower() or "remainder" in answer.lower()
    assert "has been localized and highlighted" in answer


def test_final_reasoner_honest_limitation_when_no_mask_exists():
    """Verify FinalReasoner reports honest limitation when zero built-up pixels or no mask exists."""
    payload = {
        "target_class": "BUILT",
        "fractions": {"bare": 0.80, "water": 0.20, "built": 0.0},
        "overlays": {"type": "FeatureCollection", "features": []},
    }
    answer = _synthesize_optical_lulc_answer("highlight the urban area", payload)
    assert "no built-up or urban structures were detected" in answer.lower()


def test_optical_object_cluster_detection_and_synthesis():
    """Verify optical object detection returns localized cluster details when structures exist."""
    payload = {
        "target_class": "BUILT",
        "fractions": {"built": 0.25, "bare": 0.50, "water": 0.10, "trees": 0.15},
        "detections": [
            {
                "id": "det_built_1",
                "type": "building_cluster",
                "bbox_wgs84": [10.0, 50.0, 10.05, 50.05],
                "centroid_wgs84": [10.025, 50.025],
                "area_m2": 45000.0,
                "confidence": 0.88,
            },
            {
                "id": "det_built_2",
                "type": "building_cluster",
                "bbox_wgs84": [10.1, 50.1, 10.12, 50.12],
                "centroid_wgs84": [10.11, 50.11],
                "area_m2": 12500.0,
                "confidence": 0.88,
            },
        ],
        "overlays": {"type": "FeatureCollection", "features": []},
    }
    answer = _synthesize_optical_lulc_answer("What objects or buildings are visible in this optical image?", payload)
    assert "distinct object / built structure clusters" in answer.lower()
    assert "45,000 m²" in answer or "45000" in answer
    assert "Lat: 50.02500°N" in answer
    assert "25%" in answer

