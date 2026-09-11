"""
SatQuery AI — SAR Image Processing Service

Provides calibrated Sentinel-1 (VV/VH) backscatter loading, normalization,
and SAR RGB composite generation for SAR analysis tools (e.g. sar_map).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image
import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode

from src.logger import logging

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_transform(input_size: int = 448) -> T.Compose:
    """Builds standard ImageNet normalized transform."""
    return T.Compose([
        T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def load_sar_image_to_pil(image_source: str | Path | Image.Image) -> Image.Image:
    """
    Loads SAR image from a file path (GeoTIFF or standard image) or PIL Image.
    For dual-pol (VV, VH) Sentinel-1 rasters, generates a calibrated false-color composite.
    """
    if isinstance(image_source, Image.Image):
        return image_source.convert("RGB")

    path = Path(image_source)
    if not path.exists():
        raise FileNotFoundError(f"SAR image file not found at: {path}")

    # Check if GeoTIFF or standard image
    suffix = path.suffix.lower()
    if suffix in (".tif", ".tiff"):
        try:
            with rasterio.open(path) as src:
                arr = src.read()  # (bands, H, W)
                
            if arr.shape[0] >= 2:
                # Sentinel-1 dual-pol (VV, VH)
                vv = arr[0]
                vh = arr[1]
                vv_db = 10 * np.log10(np.clip(vv, 1e-5, None))
                vh_db = 10 * np.log10(np.clip(vh, 1e-5, None))

                vv_min, vv_max = np.percentile(vv_db, 2), np.percentile(vv_db, 98)
                vh_min, vh_max = np.percentile(vh_db, 2), np.percentile(vh_db, 98)

                r = np.clip((vv_db - vv_min) / (vv_max - vv_min + 1e-6), 0, 1)
                g = np.clip((vh_db - vh_min) / (vh_max - vh_min + 1e-6), 0, 1)
                b = np.clip(r / (g + 0.1), 0, 1)
                rgb = np.stack([r, g, b], axis=-1)
            else:
                # Single-band SAR
                v = arr[0]
                v_min, v_max = np.percentile(v, 2), np.percentile(v, 98)
                norm = np.clip((v - v_min) / (v_max - v_min + 1e-6), 0, 1)
                rgb = np.stack([norm, norm, norm], axis=-1)

            rgb = (rgb * 255).astype(np.uint8)
            return Image.fromarray(rgb)
        except Exception as e:
            logging.warning(f"[SAR] rasterio load failed ({e}), falling back to PIL.Image.open")
            return Image.open(path).convert("RGB")
    else:
        return Image.open(path).convert("RGB")
