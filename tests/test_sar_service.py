"""
Tests for SARChat Service, Tool, and Quantitative GIS Radar Analyzer.
"""

from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
import pytest
from PIL import Image

from backend.services.sar_service import SARChatService, get_sar_service, load_sar_image_to_pil
from backend.services.sar_analyzer import (
    compute_sar_scene_statistics,
    parse_sarchat_detections,
    render_sar_visualization_products,
)
from backend.agents.tools.sarchat import SARChatTool
from backend.agents.tools.base import ToolResult


def _create_sample_sar_geotiff(path: Path, width: int = 128, height: int = 128) -> Path:
    """Helper to generate a synthetically calibrated 2-band (VV, VH) Sentinel-1 GeoTIFF."""
    transform = from_origin(77.5900, 12.9800, 0.0001, 0.0001)
    
    # Band 1: VV (linear scale), Band 2: VH (linear scale)
    vv = np.full((height, width), 0.05, dtype=np.float32)  # moderate backscatter
    vh = np.full((height, width), 0.01, dtype=np.float32)

    # Add high-backscatter urban patch (double-bounce)
    vv[30:60, 30:60] = 0.8
    vh[30:60, 30:60] = 0.2

    # Add low-backscatter water patch (specular reflection)
    vv[80:110, 80:110] = 0.001
    vh[80:110, 80:110] = 0.0001

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=2,
        dtype=np.float32,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(vv, 1)
        dst.write(vh, 2)
        dst.set_band_description(1, "VV")
        dst.set_band_description(2, "VH")

    return path


def test_sar_service_initialization():
    """Verify SARChatService singleton initialization and device resolution."""
    service = get_sar_service()
    assert service is not None
    assert service.device in ("cuda", "mps", "cpu")
    assert service.transform is not None


def test_sar_preprocessing_geotiff(tmp_path):
    """Verify calibrated dual-pol GeoTIFF converts to normalized 3-channel RGB PIL image."""
    tif_path = _create_sample_sar_geotiff(tmp_path / "sentinel1_sample.tif")
    pil_img = load_sar_image_to_pil(tif_path)
    assert isinstance(pil_img, Image.Image)
    assert pil_img.mode == "RGB"
    assert pil_img.size == (128, 128)


def test_sar_scene_statistics_computation(tmp_path):
    """Verify radiometric backscatter statistics calculate urban, water, and terrain percentages."""
    tif_path = _create_sample_sar_geotiff(tmp_path / "sentinel1_stats.tif")
    stats = compute_sar_scene_statistics(tif_path)
    assert "urban_percent" in stats
    assert "water_percent" in stats
    assert "vegetation_percent" in stats
    assert "mean_vv_db" in stats
    assert "mean_vh_db" in stats
    assert stats["urban_percent"] > 0.0
    assert stats["water_percent"] > 0.0


def test_sar_detections_parsing_with_geotransform(tmp_path):
    """Verify bounding box string parsing into WGS84 coordinates and pixel bounds."""
    tif_path = _create_sample_sar_geotiff(tmp_path / "sentinel1_dets.tif")
    raw_answer = "Identified industrial complex located at [234, 234, 468, 468] in the radar image."
    detections = parse_sarchat_detections(raw_answer, tif_path=tif_path)
    assert len(detections) == 1
    det = detections[0]
    assert det["id"] == "det_1"
    assert det["bbox_pixel"][0] < det["bbox_pixel"][2]
    assert det["bbox_wgs84"] is not None
    assert len(det["bbox_wgs84"]) == 4


def test_sar_visualizations_rendering(tmp_path):
    """Verify rendering of static SAR products (composite, vv, vh, overlay)."""
    tif_path = _create_sample_sar_geotiff(tmp_path / "sentinel1_vis.tif")
    output_dir = tmp_path / "processed"
    products = render_sar_visualization_products(tif_path, output_dir=output_dir)
    assert "composite" in products
    assert "vv" in products
    assert "vh" in products
    assert "overlay" in products
    assert Path(products["composite"]).exists()
    assert Path(products["overlay"]).exists()
