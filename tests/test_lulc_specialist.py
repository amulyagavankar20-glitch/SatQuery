"""Tests for lulc_map specialist tool and Dynamic World land cover."""

from pathlib import Path
import pytest
import numpy as np
from backend.agents.tools.lulc import LulcMapTool
from backend.agents.tools.dynamic_world_infer import run_dynamic_world


def test_lulc_map_tool_instantiation():
    tool = LulcMapTool()
    assert tool.tool_id == "lulc_map"


def test_dynamic_world_inference():
    weights = Path("weights/dynamic_world.pt")
    if weights.exists():
        # 9-band Sentinel-2 synthetic stack
        stack9 = np.random.uniform(500, 3000, size=(9, 64, 64)).astype(np.float32)
        labels = run_dynamic_world(stack9, weights)
        assert labels.shape == (64, 64)
        assert labels.dtype == np.uint8


def test_lulc_pixel_level_water_mask_and_geojson_generation(tmp_path):
    """Verify lulc_map generates real pixel-level GeoTIFF mask and valid GeoJSON polygons."""
    import rasterio
    from rasterio.transform import from_bounds
    from backend.agents.tools.lulc import LulcMapTool

    tif_path = tmp_path / "water_scene.tif"
    # Create a 64x64 scene with a distinct water body on left half (blue-dominant, low greenness)
    r = np.full((64, 64), 200, dtype=np.uint8)
    g = np.full((64, 64), 160, dtype=np.uint8)
    b = np.full((64, 64), 80, dtype=np.uint8)
    # Water region on left (cols 0..20)
    r[:, :20] = 30
    g[:, :20] = 50
    b[:, :20] = 120
    data = np.stack([r, g, b], axis=0)

    transform = from_bounds(72.5, 19.0, 72.7, 19.2, 64, 64)
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

    tool = LulcMapTool()
    res = tool.execute({
        "image_refs": [str(tif_path)],
        "question": "Highlight the water body",
        "bounds": [72.5, 19.0, 72.7, 19.2],
        "job_id": "test-job-mask",
    })

    assert res.status == "success"
    payload = res.result
    assert "fractions" in payload
    fractions = payload["fractions"]
    water_frac = fractions.get("water", 0.0) + fractions.get("flooded_vegetation", 0.0)
    assert 0.25 <= water_frac <= 0.35  # ~20/64 = 31.25%

    # Spatial outputs check
    assert "spatial_outputs" in payload
    assert payload["spatial_outputs"]["has_spatial_mask"] is True
    assert "overlays" in payload
    features = payload["overlays"]["features"]
    assert len(features) >= 1
    water_feat = features[0]
    assert water_feat["properties"]["kind"] in ("water_mask", "mask")
    assert water_feat["geometry"]["type"] in ("Polygon", "MultiPolygon")

    # Verify coordinates are within bounding box
    coords = water_feat["geometry"]["coordinates"]
    flat_coords = []
    def _flatten(c):
        if isinstance(c[0], (int, float)):
            flat_coords.append(c)
        else:
            for sub in c:
                _flatten(sub)
    _flatten(coords)
    assert len(flat_coords) > 0
    for lon, lat in flat_coords:
        assert 72.49 <= lon <= 72.71
        assert 18.99 <= lat <= 19.21


def test_lulc_zero_water_scene_no_fake_mask(tmp_path):
    """Verify scenes with no water do not produce fake water mask polygons."""
    import rasterio
    from rasterio.transform import from_bounds
    from backend.agents.tools.lulc import LulcMapTool
    from backend.agents.final_reasoner import _synthesize_optical_lulc_answer

    tif_path = tmp_path / "dry_scene.tif"
    r = np.full((64, 64), 220, dtype=np.uint8)
    g = np.full((64, 64), 180, dtype=np.uint8)
    b = np.full((64, 64), 90, dtype=np.uint8)
    data = np.stack([r, g, b], axis=0)

    transform = from_bounds(72.5, 19.0, 72.7, 19.2, 64, 64)
    with rasterio.open(
        tif_path, "w", driver="GTiff", height=64, width=64, count=3, dtype=np.uint8, crs="EPSG:4326", transform=transform
    ) as dst:
        dst.write(data)

    tool = LulcMapTool()
    res = tool.execute({
        "image_refs": [str(tif_path)],
        "question": "Highlight the water body",
        "bounds": [72.5, 19.0, 72.7, 19.2],
    })

    payload = res.result
    assert payload["fractions"]["water"] == 0.0
    assert len(payload["overlays"]["features"]) == 0

    ans = _synthesize_optical_lulc_answer("Highlight the water body", payload)
    assert "No surface water was detected" in ans or "0%" in ans

