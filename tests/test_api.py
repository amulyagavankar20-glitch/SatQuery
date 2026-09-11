"""Tests for FastAPI HTTP endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "postgres" in data
    assert "model_slots_count" in data


def test_models_endpoint():
    res = client.get("/models")
    assert res.status_code == 200
    data = res.json()
    assert "model_slots" in data
    slots = data["model_slots"]
    slot_ids = [s["slot_id"] for s in slots]
    assert "specialist_sar_map" in slot_ids
    assert "specialist_lulc_map" in slot_ids
    assert "specialist_bit_cd" in slot_ids
