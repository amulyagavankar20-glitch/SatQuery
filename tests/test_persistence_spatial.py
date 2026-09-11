"""
Tests for PostGIS SpatialFeature Persistence.
"""

import uuid
from unittest.mock import MagicMock
import pytest
from geoalchemy2.shape import to_shape
from backend.services.persistence import _persist_spatial_features
from backend.models import SpatialFeature
from backend.agents.tools.base import ToolResult


def test_persist_sar_detection_spatial_feature():
    """Verify that SAR detections are converted to PostGIS SpatialFeature polygons with SRID 4326."""
    db_mock = MagicMock()
    job_uuid = uuid.uuid4()

    sar_payload = {
        "answer": "Detected radar backscatter structure",
        "detections": [
            {
                "id": "det_1",
                "type": "industrial_facility",
                "bbox_wgs84": [77.5946, 12.9716, 77.6046, 12.9816],
                "confidence": 0.92,
                "image_position": "top-right",
            }
        ]
    }
    tool_res = ToolResult(
        tool_id="sarchat_vqa",
        status="success",
        result=sar_payload,
        explanation="SAR detection",
    )

    state = {"specialist_results": [tool_res], "spatial_evidence": []}

    _persist_spatial_features(db_mock, job_uuid, state)

    assert db_mock.add.called
    added_obj = db_mock.add.call_args[0][0]
    assert isinstance(added_obj, SpatialFeature)
    assert added_obj.job_id == job_uuid
    assert added_obj.feature_type == "DETECTION"
    assert added_obj.class_label == "industrial_facility"
    assert added_obj.confidence == 0.92
    assert added_obj.properties["id"] == "det_1"

    # Verify geometry is valid WGS84 polygon
    geom_shape = to_shape(added_obj.geometry)
    assert geom_shape.geom_type == "Polygon"
    bounds = geom_shape.bounds
    assert pytest.approx(bounds[0], 0.0001) == 77.5946
    assert pytest.approx(bounds[1], 0.0001) == 12.9716


def test_persist_bit_change_polygon_spatial_feature():
    """Verify that BIT change detection GeoJSON features are stored in SpatialFeature table."""
    db_mock = MagicMock()
    job_uuid = uuid.uuid4()

    bit_payload = {
        "statistics": {"change_percentage": 3.2, "changed_area_m2": 32000.0},
        "geojson": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "class": "surface_change",
                        "area_m2": 15400.0,
                        "cluster_id": 1,
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [77.5900, 12.9700],
                            [77.5950, 12.9700],
                            [77.5950, 12.9750],
                            [77.5900, 12.9750],
                            [77.5900, 12.9700],
                        ]],
                    },
                }
            ],
        },
    }
    tool_res = ToolResult(
        tool_id="bit_cd",
        status="success",
        result=bit_payload,
        explanation="BIT change detection",
    )

    state = {"specialist_results": [tool_res], "spatial_evidence": []}

    _persist_spatial_features(db_mock, job_uuid, state)

    assert db_mock.add.called
    added_obj = db_mock.add.call_args[0][0]
    assert isinstance(added_obj, SpatialFeature)
    assert added_obj.job_id == job_uuid
    assert added_obj.feature_type == "CHANGE_POLYGON"
    assert added_obj.class_label == "surface_change"
    assert added_obj.area_m2 == 15400.0
    assert added_obj.confidence == 1.0

    # Verify geometry shape
    geom_shape = to_shape(added_obj.geometry)
    assert geom_shape.geom_type == "Polygon"
    assert len(geom_shape.exterior.coords) == 5


def test_persist_empty_spatial_evidence_safe():
    """Verify that empty or invalid spatial evidence does not raise exceptions."""
    db_mock = MagicMock()
    job_uuid = uuid.uuid4()

    state = {"specialist_results": [], "spatial_evidence": []}
    _persist_spatial_features(db_mock, job_uuid, state)
    assert not db_mock.add.called
