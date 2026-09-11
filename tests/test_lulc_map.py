from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.agents.tools.bigearthnet import BEN19, scene_tags, try_resnet_tags
from backend.agents.tools.lulc import DW_CLASSES, LulcMapTool, _fractions, _spectral_labels


def test_spectral_covers_water_veg_built() -> None:
    h, w = 64, 64
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    rgb[:16, :, 1] = 0.7
    rgb[:16, :, 0] = 0.15
    rgb[:16, :, 2] = 0.15
    rgb[16:32, :, 2] = 0.55
    rgb[16:32, :, 0] = 0.1
    rgb[16:32, :, 1] = 0.2
    rgb[32:48] = 0.65
    rgb[48:] = 0.35
    fr = _fractions(_spectral_labels(rgb))
    assert set(fr) == set(DW_CLASSES)
    assert fr["water"] > 0.1
    assert fr["trees"] + fr["grass"] + fr["crops"] > 0.1
    assert fr["built"] > 0.05


def test_tool_requires_refs() -> None:
    tool = LulcMapTool()
    try:
        tool.validate({"image_refs": []})
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_scene_tags_are_ben19_not_dw_class_names() -> None:
    tags = scene_tags({"water": 0.4, "crops": 0.3, "built": 0.2, "trees": 0.1})
    names = {t["name"] for t in tags}
    assert names <= set(BEN19)
    assert "water" not in names
    assert "crops" not in names
    assert "built" not in names
    assert any(t["name"] == "Inland waters" for t in tags)
    assert all(t["source"] == "ben19_taxonomy" for t in tags)


def test_coastal_scene_tags_prefer_marine_waters() -> None:
    inland = scene_tags({"water": 0.8})
    coast = scene_tags({"water": 0.8}, coastal=True)
    assert inland[0]["name"] == "Inland waters"
    assert coast[0]["name"] == "Marine waters"


def test_resnet_stays_off_without_weights() -> None:
    assert try_resnet_tags("missing.tif") is None


def test_rgb_jpeg_is_spectral_fallback_not_dynamic_world() -> None:
    path = Path("web/public/demos/water.jpg")
    if not path.is_file():
        return
    out = LulcMapTool().infer({"image_refs": [str(path)], "question": "Highlight the water body"})
    assert out["backend"] == "spectral_fallback"
    assert out["fractions"]["water"] > 0.1
    names = {t["name"] for t in out["scene_tags"]}
    assert names <= set(BEN19)
    assert "Inland waters" in names
    assert "Dynamic World is not trained on BigEarthNet" in out["answer"]
