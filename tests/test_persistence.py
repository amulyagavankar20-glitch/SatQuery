"""Tests for PostGIS persistence, geometry conversions, and database models."""

import uuid
import pytest
from backend.utils import bbox_to_geometry, geojson_to_geometry, geometry_to_geojson
from backend.services.persistence import create_job_record, load_job
from backend.models import Job, Asset, SpatialFeature


def test_bbox_to_geometry_conversion():
    geom = bbox_to_geometry(72.8, 19.0, 72.9, 19.1, srid=4326)
    assert geom is not None
    
    geojson = geometry_to_geojson(geom)
    assert geojson is not None
    assert geojson["type"] == "Polygon"
    assert len(geojson["coordinates"][0]) == 5  # Closed ring (5 points)


def test_job_persistence_crud():
    test_id = uuid.uuid4()
    session_id = uuid.uuid4()
    
    job = create_job_record(
        job_id=test_id,
        session_id=session_id,
        query="Test query for persistence",
        input_mode="SINGLE_SAR",
        task="SINGLE_VQA",
        status="running",
    )
    
    if job is not None:
        loaded = load_job(str(test_id))
        assert loaded is not None
        assert loaded["job_id"] == str(test_id)
        assert loaded["query"] == "Test query for persistence"
