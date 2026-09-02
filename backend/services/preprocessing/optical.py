"""
SatQuery AI — Optical Preprocessing Pipeline
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


class OpticalPreprocessor(BasePreprocessor):
    """
    Dedicated preprocessor for SINGLE_OPTICAL imagery.
    
    Generates normalized 3-channel (RGB) composites, handles nodata/clouds,
    and produces georeferenced model-ready tiles for VLM / GeoChat ingestion.
    """

    def __init__(
        self,
        tile_size: int = 256,
        stride: int | None = None,
        p_min: float = 2.0,
        p_max: float = 98.0,
    ):
        self.tile_size = tile_size
        self.stride = stride or tile_size
        self.p_min = p_min
        self.p_max = p_max

    def preprocess(
        self,
        asset_dict: dict[str, Any],
        job_id: str,
        job_storage_dir: Path | None = None,
    ) -> PreprocessResult:
        """
        Execute full optical preprocessing workflow on a single optical asset.
        """
        file_path_str = asset_dict.get("file_path")
        if not file_path_str:
            raise PreprocessingError("Asset dictionary missing 'file_path'.")
        
        file_path = Path(file_path_str)
        if not file_path.exists():
            raise InvalidRasterError(f"Optical raster file does not exist: {file_path}")

        # Ensure job storage structure
        dirs = create_job_directory(job_id, base_dir=job_storage_dir)
        processed_dir = dirs["processed"]
        tiles_dir = dirs["tiles"]

        steps = ["validate_optical_raster", "read_bands_and_metadata"]

        try:
            with rasterio.open(file_path) as src:
                count = src.count
                width = src.width
                height = src.height
                transform = src.transform
                crs = src.crs.to_string() if src.crs else "EPSG:4326"
                nodata = src.nodatavals[0] if src.nodatavals else None

                # Read raster bands
                if count >= 3:
                    # Multi-band / RGB optical
                    data = src.read([1, 2, 3])
                else:
                    # Single band / Panchromatic optical -> duplicate to 3-channel for VLM
                    single_band = src.read(1)
                    data = np.stack([single_band, single_band, single_band], axis=0)

            steps.append("handle_nodata_and_cloud_mask")
            # Apply cloud fraction annotation from metadata if present
            cloud_fraction = asset_dict.get("cloud_fraction")
            
            steps.append("percentile_normalization_and_rgb_composite")
            norm_rgb = self.normalize_percentile(
                data,
                p_min=self.p_min,
                p_max=self.p_max,
                nodata=nodata,
            )

            # Save full composite in processed/
            composite_tif_path = processed_dir / f"composite_optical_{file_path.stem}.tif"
            composite_png_path = processed_dir / f"composite_optical_{file_path.stem}.png"

            self.save_geotiff(composite_tif_path, norm_rgb, transform, crs, nodata=None)
            self.save_png_preview(composite_png_path, norm_rgb)
            steps.append("save_processed_composite")

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
                # Extract tile slice (3, h, w)
                tile_data = norm_rgb[:, row_off : row_off + h, col_off : col_off + w]

                # If edge tile is smaller than tile_size, pad to square tile_size for model
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
                    modality=Modality.OPTICAL.value,
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
                input_class=InputClass.SINGLE_OPTICAL,
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
                        "cloud_fraction": cloud_fraction,
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
            logging.error(f"Error in optical preprocessing: {e}")
            raise PreprocessingError(f"Optical preprocessing failed: {e}")
