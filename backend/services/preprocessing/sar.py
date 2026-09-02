"""
SatQuery AI — SAR Preprocessing Pipeline
"""
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from backend.exceptions import InvalidRasterError, PreprocessingError
from backend.schemas import InputClass, Modality, PreprocessResult, TileReference
from backend.services.preprocessing.base import BasePreprocessor
from backend.utils import create_job_directory
from src.logger import logging


class SARPreprocessor(BasePreprocessor):
    """
    Dedicated preprocessor for SINGLE_SAR imagery (e.g., Sentinel-1, RISAT).
    
    Performs radiometric calibration / dB scaling, speckle reduction,
    contrast stretch normalization, and produces georeferenced model-ready tiles.
    Does NOT apply optical cloud masks.
    """

    def __init__(
        self,
        tile_size: int = 256,
        stride: int | None = None,
        apply_speckle_filter: bool = True,
        p_min: float = 1.0,
        p_max: float = 99.0,
    ):
        self.tile_size = tile_size
        self.stride = stride or tile_size
        self.apply_speckle_filter = apply_speckle_filter
        self.p_min = p_min
        self.p_max = p_max

    @staticmethod
    def simple_speckle_filter(img: np.ndarray, window_size: int = 3) -> np.ndarray:
        """
        Lightweight spatial mean/box filter for SAR speckle reduction.
        """
        pad = window_size // 2
        padded = np.pad(img, pad, mode="reflect")
        filtered = np.zeros_like(img, dtype=np.float32)
        
        # Vectorized 3x3 neighborhood box sum
        h, w = img.shape
        window_sum = np.zeros((h, w), dtype=np.float32)
        for di in range(window_size):
            for dj in range(window_size):
                window_sum += padded[di : di + h, dj : dj + w]
        
        filtered = window_sum / float(window_size * window_size)
        return filtered

    def preprocess(
        self,
        asset_dict: dict[str, Any],
        job_id: str,
        job_storage_dir: Path | None = None,
    ) -> PreprocessResult:
        """
        Execute full SAR preprocessing workflow on a single SAR asset.
        """
        file_path_str = asset_dict.get("file_path")
        if not file_path_str:
            raise PreprocessingError("Asset dictionary missing 'file_path'.")
        
        file_path = Path(file_path_str)
        if not file_path.exists():
            raise InvalidRasterError(f"SAR raster file does not exist: {file_path}")

        dirs = create_job_directory(job_id, base_dir=job_storage_dir)
        processed_dir = dirs["processed"]
        tiles_dir = dirs["tiles"]

        steps = ["validate_sar_raster", "read_polarization_and_metadata"]

        try:
            with rasterio.open(file_path) as src:
                count = src.count
                width = src.width
                height = src.height
                transform = src.transform
                crs = src.crs.to_string() if src.crs else "EPSG:4326"
                nodata = src.nodatavals[0] if src.nodatavals else None

                # Read SAR amplitude / intensity channels
                raw_bands = [src.read(i + 1).astype(np.float32) for i in range(min(count, 2))]

            steps.append("sar_decibel_calibration")
            calibrated_bands = []
            for b in raw_bands:
                # Convert linear backscatter intensity to logarithmic dB scale
                # clip to avoid log of 0/negative
                positive = np.maximum(b, 1e-6)
                db_band = 10.0 * np.log10(positive)
                calibrated_bands.append(db_band)

            steps.append("sar_speckle_filtering")
            filtered_bands = []
            for b in calibrated_bands:
                if self.apply_speckle_filter:
                    f_b = self.simple_speckle_filter(b, window_size=3)
                else:
                    f_b = b
                filtered_bands.append(f_b)

            steps.append("sar_contrast_normalization")
            sar_data = np.stack(filtered_bands, axis=0)
            norm_sar = self.normalize_percentile(
                sar_data,
                p_min=self.p_min,
                p_max=self.p_max,
                nodata=nodata,
            )

            # If 1 band (e.g. VV only), duplicate to 3-channel for VLM model readiness
            if norm_sar.shape[0] == 1:
                norm_sar_3ch = np.repeat(norm_sar, 3, axis=0)
            elif norm_sar.shape[0] == 2:
                # 2 bands (e.g. VV, VH) -> construct false color (VV, VH, VV/VH ratio)
                ratio = np.clip(
                    (norm_sar[0].astype(np.float32) / (norm_sar[1].astype(np.float32) + 1.0)) * 128.0,
                    0,
                    255,
                ).astype(np.uint8)
                norm_sar_3ch = np.stack([norm_sar[0], norm_sar[1], ratio], axis=0)
            else:
                norm_sar_3ch = norm_sar[:3]

            composite_tif_path = processed_dir / f"composite_sar_{file_path.stem}.tif"
            composite_png_path = processed_dir / f"composite_sar_{file_path.stem}.png"

            self.save_geotiff(composite_tif_path, norm_sar_3ch, transform, crs, nodata=None)
            self.save_png_preview(composite_png_path, norm_sar_3ch)
            steps.append("save_processed_sar_composite")

            # Generate tiles
            steps.append("slice_model_ready_tiles")
            windows = self.generate_tile_windows(
                width=width,
                height=height,
                tile_size=self.tile_size,
                stride=self.stride,
            )

            tile_references: list[TileReference] = []
            source_id = str(asset_dict.get("asset_id") or file_path.stem)
            acquired_at = asset_dict.get("acquired_at")

            for idx, (col_off, row_off, w, h) in enumerate(windows):
                tile_data = norm_sar_3ch[:, row_off : row_off + h, col_off : col_off + w]

                if w < self.tile_size or h < self.tile_size:
                    padded_tile = np.zeros((3, self.tile_size, self.tile_size), dtype=np.uint8)
                    padded_tile[:, :h, :w] = tile_data
                    tile_data_to_save = padded_tile
                else:
                    tile_data_to_save = tile_data

                tile_name = f"tile_{idx:04d}_{file_path.stem}.png"
                tile_file_path = tiles_dir / tile_name
                self.save_png_preview(tile_file_path, tile_data_to_save)

                tile_ref = self.create_tile_reference(
                    tile_index=idx,
                    source_asset_id=source_id,
                    modality=Modality.SAR.value,
                    file_path=tile_file_path,
                    col_off=col_off,
                    row_off=row_off,
                    tile_w=w,
                    tile_h=h,
                    parent_transform=transform,
                    crs=crs,
                    acquired_at=acquired_at,
                )
                tile_references.append(tile_ref)

            steps.append("preserve_spatial_tile_references")

            return PreprocessResult(
                input_class=InputClass.SINGLE_SAR,
                success=True,
                processed_assets=[
                    {
                        "source_asset_id": source_id,
                        "composite_tif": str(composite_tif_path.resolve()),
                        "composite_png": str(composite_png_path.resolve()),
                        "width": width,
                        "height": height,
                        "channels": 3,
                        "crs": crs,
                        "speckle_filtered": self.apply_speckle_filter,
                    }
                ],
                tile_references=tile_references,
                tile_pairs=None,
                preprocessing_steps=steps,
                spatial_reference={
                    "crs": crs,
                    "transform": [float(x) for x in transform],
                    "width": width,
                    "height": height,
                    "bounds": asset_dict.get("bounds"),
                },
                output_paths={
                    "composite_tif": str(composite_tif_path.resolve()),
                    "composite_png": str(composite_png_path.resolve()),
                    "tiles_dir": str(tiles_dir.resolve()),
                },
                warnings=[],
                errors=[],
                metadata={
                    "tile_count": len(tile_references),
                    "tile_size": self.tile_size,
                    "stride": self.stride,
                },
            )
        except Exception as e:
            logging.error(f"Error in SAR preprocessing: {e}")
            raise PreprocessingError(f"SAR preprocessing failed: {e}")
