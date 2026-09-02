"""
SatQuery AI — Preprocessing Base Class & Shared Raster Operations
"""
import math
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine, from_bounds
from rasterio.warp import transform_bounds
from rasterio.windows import Window
from shapely.geometry import box

from backend.exceptions import PreprocessingError
from backend.schemas import TileReference
from src.logger import logging


class BasePreprocessor:
    """
    Base preprocessor providing normalized image normalization,
    spatial transform preservation, and deterministic tiling grids.
    """

    @staticmethod
    def normalize_percentile(
        data: np.ndarray,
        p_min: float = 2.0,
        p_max: float = 98.0,
        nodata: Optional[float] = None,
    ) -> np.ndarray:
        """
        Normalize multi-channel or single-channel raster array using percentile stretch
        to [0, 255] uint8.
        """
        if data.size == 0:
            return data.astype(np.uint8)

        normalized = np.zeros_like(data, dtype=np.float32)
        
        # Handle 2D or 3D (bands, height, width)
        is_3d = data.ndim == 3
        bands = data.shape[0] if is_3d else 1

        for b in range(bands):
            band = data[b] if is_3d else data
            
            # Mask nodata or inf/nan values
            mask = np.isfinite(band)
            if nodata is not None:
                mask = mask & (band != nodata)

            valid_pixels = band[mask]
            if valid_pixels.size == 0:
                continue

            low = np.percentile(valid_pixels, p_min)
            high = np.percentile(valid_pixels, p_max)

            if high > low:
                stretched = (band - low) / (high - low)
                stretched = np.clip(stretched, 0.0, 1.0) * 255.0
            else:
                stretched = np.zeros_like(band, dtype=np.float32)

            if is_3d:
                normalized[b] = stretched
            else:
                normalized = stretched

        return np.round(normalized).astype(np.uint8)

    @staticmethod
    def generate_tile_windows(
        width: int,
        height: int,
        tile_size: int = 256,
        stride: Optional[int] = None,
    ) -> List[Tuple[int, int, int, int]]:
        """
        Compute standard tiling windows across the raster dimension.
        Returns a list of (col_off, row_off, tile_width, tile_height).
        """
        step = stride if stride and stride > 0 else tile_size
        windows = []

        for row_off in range(0, height, step):
            for col_off in range(0, width, step):
                # Clamp window width and height to raster boundaries
                w = min(tile_size, width - col_off)
                h = min(tile_size, height - row_off)
                if w > 0 and h > 0:
                    windows.append((col_off, row_off, w, h))

        return windows

    @classmethod
    def save_geotiff(
        cls,
        output_path: Path,
        data: np.ndarray,
        transform: Affine,
        crs: str,
        nodata: Optional[float] = None,
    ) -> None:
        """Save a numpy raster array as a georeferenced GeoTIFF."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        is_3d = data.ndim == 3
        count = data.shape[0] if is_3d else 1
        height = data.shape[1] if is_3d else data.shape[0]
        width = data.shape[2] if is_3d else data.shape[1]
        dtype = data.dtype

        crs_obj = CRS.from_string(crs) if crs else CRS.from_string("EPSG:4326")

        with rasterio.open(
            output_path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=count,
            dtype=dtype,
            crs=crs_obj,
            transform=transform,
            nodata=nodata,
        ) as dst:
            if is_3d:
                for i in range(count):
                    dst.write(data[i], i + 1)
            else:
                dst.write(data, 1)

    @classmethod
    def save_png_preview(
        cls,
        output_path: Path,
        rgb_data: np.ndarray,
    ) -> None:
        """Save an RGB/Grayscale uint8 array as a PNG preview."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if rgb_data.ndim == 3:
            # (bands, H, W) -> (H, W, bands)
            if rgb_data.shape[0] in (3, 4):
                img_arr = np.transpose(rgb_data[:3], (1, 2, 0))
            elif rgb_data.shape[0] == 1:
                img_arr = rgb_data[0]
            else:
                img_arr = rgb_data[0]
        else:
            img_arr = rgb_data

        img = Image.fromarray(img_arr)
        img.save(output_path, format="PNG")

    @classmethod
    def create_tile_reference(
        cls,
        tile_index: int,
        source_asset_id: str,
        modality: str,
        file_path: Path,
        col_off: int,
        row_off: int,
        tile_w: int,
        tile_h: int,
        parent_transform: Affine,
        crs: str,
        pair_tag: Optional[str] = None,
        pair_tile_id: Optional[str] = None,
        acquired_at: Optional[Any] = None,
    ) -> TileReference:
        """
        Construct a strongly-typed TileReference preserving exact geographic bounds
        and coordinate transforms for a single tile.
        """
        # Calculate tile spatial transform and bounds in native CRS
        tile_transform = rasterio.windows.transform(
            Window(col_off, row_off, tile_w, tile_h), parent_transform
        )
        min_x, max_y = tile_transform * (0, 0)
        max_x, min_y = tile_transform * (tile_w, tile_h)
        
        # Ensure ordered [min_x, min_y, max_x, max_y]
        left = min(min_x, max_x)
        right = max(min_x, max_x)
        bottom = min(min_y, max_y)
        top = max(min_y, max_y)
        bounds = [left, bottom, right, top]

        # WGS84 bounding box
        bounds_wgs84 = bounds
        try:
            crs_obj = CRS.from_string(crs) if crs else CRS.from_string("EPSG:4326")
            if not crs_obj.is_geographic:
                bounds_wgs84 = list(transform_bounds(crs_obj, "EPSG:4326", left, bottom, right, top))
        except Exception:
            pass

        bbox_wkt = box(left, bottom, right, top).wkt

        tile_id = f"tile_{tile_index:04d}_{modality.lower()}"
        if pair_tag:
            tile_id = f"{tile_id}_{pair_tag}"

        return TileReference(
            tile_id=tile_id,
            tile_index=tile_index,
            source_asset_id=source_asset_id,
            modality=modality,
            file_path=str(file_path.resolve()),
            col_off=col_off,
            row_off=row_off,
            width=tile_w,
            height=tile_h,
            bounds=[round(x, 6) for x in bounds],
            bounds_wgs84=[round(x, 6) for x in bounds_wgs84] if bounds_wgs84 else None,
            bbox_wkt=bbox_wkt,
            crs=crs,
            pair_tag=pair_tag,
            pair_tile_id=pair_tile_id,
            acquisition_date=acquired_at,
        )
