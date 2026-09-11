"""STAC service to fetch and crop Sentinel-2 Cloud-Optimized GeoTIFFs (COGs)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

logger = logging.getLogger(__name__)

STAC_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"


def search_and_crop_sentinel2(
    bbox: list[float],
    output_path: Path,
    *,
    max_cloud_cover: float = 30.0,
) -> dict[str, Any]:
    """
    Search Sentinel-2 L2A imagery via STAC for `bbox` [west, south, east, north]
    and stream crop a GeoTIFF directly to `output_path`.
    """
    if len(bbox) != 4:
        raise ValueError("bbox must contain exactly 4 values: [west, south, east, north]")

    w, s, e, n = bbox
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": [w, s, e, n],
        "limit": 5,
        "query": {
            "eo:cloud_cover": {"lt": max_cloud_cover}
        },
        "sortby": [
            {"field": "properties.datetime", "direction": "desc"}
        ]
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(STAC_SEARCH_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("STAC search failed with query constraints, trying without cloud filter: %s", exc)
        payload.pop("query", None)
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(STAC_SEARCH_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

    features = data.get("features", [])
    if not features:
        raise ValueError(f"No Sentinel-2 satellite imagery found for bbox {bbox}")

    feature = features[0]
    properties = feature.get("properties", {})
    datetime_str = properties.get("datetime", "")
    cloud_cover = properties.get("eo:cloud_cover", 0.0)
    assets = feature.get("assets", {})

    visual_href = assets.get("visual", {}).get("href")
    if not visual_href:
        # Fallback to red asset if visual is unavailable
        visual_href = assets.get("red", {}).get("href")

    if not visual_href:
        raise ValueError("No compatible visual or RGB raster asset found in STAC metadata")

    from rasterio.env import Env

    logger.info("Streaming COG crop from STAC asset: %s", visual_href)

    with Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff",
        GDAL_HTTP_TIMEOUT="10",
        GDAL_HTTP_MAX_RETRY="2",
    ):
        with rasterio.open(visual_href) as src:
            # Transform WGS84 bbox into raster's target CRS
            transformed_bbox = transform_bounds("EPSG:4326", src.crs, w, s, e, n)
            window = from_bounds(*transformed_bbox, transform=src.transform)

            # Read RGB window
            data_arr = src.read(window=window)
            win_transform = src.window_transform(window)

            profile = src.profile.copy()
            profile.update({
                "driver": "GTiff",
                "height": data_arr.shape[1],
                "width": data_arr.shape[2],
                "transform": win_transform,
                "count": data_arr.shape[0],
                "dtype": data_arr.dtype,
            })

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, "w", **profile) as dst:
                dst.write(data_arr)

    # Save preview composite PNG for web UI and artifacts
    try:
        from PIL import Image
        import numpy as np
        proc_dir = output_path.parent.parent / "processed"
        proc_dir.mkdir(parents=True, exist_ok=True)
        composite_path = proc_dir / "composite.png"

        if data_arr.shape[0] >= 3:
            rgb = np.transpose(data_arr[:3], (1, 2, 0))
        else:
            rgb = np.transpose(np.repeat(data_arr[:1], 3, axis=0), (1, 2, 0))

        if rgb.dtype != np.uint8:
            rgb = ((rgb - rgb.min()) / (rgb.max() - rgb.min() + 1e-6) * 255).astype(np.uint8)

        img = Image.fromarray(rgb)
        img.save(composite_path, "PNG")
        logger.info("Saved composite preview PNG to %s", composite_path)
    except Exception as exc:
        logger.warning("Could not render preview composite PNG: %s", exc)

    return {
        "stac_id": feature.get("id"),
        "acquired_at": datetime_str,
        "cloud_cover": cloud_cover,
        "output_path": str(output_path.resolve()),
        "sensor": "Sentinel-2",
        "bbox": bbox,
    }
