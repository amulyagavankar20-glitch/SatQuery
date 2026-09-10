"""
SatQuery AI — Cross-Modal Optical + SAR Preprocessing Pipeline
"""
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import transform_bounds

from backend.exceptions import (
    InsufficientOverlapError,
    InvalidRasterError,
    PreprocessingError,
)
from backend.schemas import InputClass, Modality, PreprocessResult, TilePair, TileReference
from backend.services.geospatial import compute_spatial_overlap, reproject_and_resample_raster
from backend.services.preprocessing.base import BasePreprocessor
from backend.services.preprocessing.sar import SARPreprocessor
from backend.utils import create_job_directory
from src.logger import logging


class OpticalSARPreprocessor(BasePreprocessor):
    """
    Dedicated preprocessor for OPTICAL_SAR cross-modal pairs (e.g., Sentinel-2 + Sentinel-1).
    
    Handles CRS differences, pixel resolution disparity, cross-sensor spatial alignment,
    independent sensor-specific calibration (optical RGB composite + SAR speckle/dB normalization),
    and produces synchronized multi-modal tile pairs for independent specialist
    analysis. It does not fuse S1 and S2 imagery.
    """

    def __init__(
        self,
        tile_size: int = 256,
        stride: int | None = None,
        apply_sar_speckle_filter: bool = True,
        p_min_optical: float = 2.0,
        p_max_optical: float = 98.0,
        p_min_sar: float = 1.0,
        p_max_sar: float = 99.0,
    ):
        self.tile_size = tile_size
        self.stride = stride or tile_size
        self.apply_sar_speckle_filter = apply_sar_speckle_filter
        self.p_min_optical = p_min_optical
        self.p_max_optical = p_max_optical
        self.p_min_sar = p_min_sar
        self.p_max_sar = p_max_sar

    def preprocess(
        self,
        assets: list[dict[str, Any]],
        job_id: str,
        job_storage_dir: Path | None = None,
    ) -> PreprocessResult:
        """
        Execute cross-modal optical + SAR alignment and paired tiling.
        """
        if len(assets) < 2:
            raise PreprocessingError("Optical-SAR preprocessing requires both optical and SAR assets.")

        # Identify optical vs SAR asset
        optical_asset = None
        sar_asset = None

        for a in assets:
            mod = str(a.get("modality", "")).upper()
            if mod == Modality.OPTICAL.value and optical_asset is None:
                optical_asset = a
            elif mod == Modality.SAR.value and sar_asset is None:
                sar_asset = a

        if not optical_asset or not sar_asset:
            # Fallback assignment
            optical_asset = assets[0]
            sar_asset = assets[1]

        opt_path = Path(str(optical_asset.get("file_path")))
        sar_path = Path(str(sar_asset.get("file_path")))

        if not opt_path.exists() or not sar_path.exists():
            raise InvalidRasterError("One or both Optical / SAR raster files do not exist.")

        dirs = create_job_directory(job_id, base_dir=job_storage_dir)
        processed_dir = dirs["processed"]
        tiles_dir = dirs["tiles"]

        proc_opt_dir = processed_dir / "optical"
        proc_sar_dir = processed_dir / "sar"
        tiles_opt_dir = tiles_dir / "optical"
        tiles_sar_dir = tiles_dir / "sar"

        for d in (proc_opt_dir, proc_sar_dir, tiles_opt_dir, tiles_sar_dir):
            d.mkdir(parents=True, exist_ok=True)

        steps = ["validate_optical_and_sar_rasters", "calculate_cross_modal_intersection"]

        try:
            with rasterio.open(opt_path) as src_opt, rasterio.open(sar_path) as src_sar:
                crs_opt = src_opt.crs.to_string() if src_opt.crs else "EPSG:4326"
                crs_sar = src_sar.crs.to_string() if src_sar.crs else "EPSG:4326"

                spatial_rel = compute_spatial_overlap(
                    bounds1=[src_opt.bounds.left, src_opt.bounds.bottom, src_opt.bounds.right, src_opt.bounds.top],
                    crs1=crs_opt,
                    bounds2=[src_sar.bounds.left, src_sar.bounds.bottom, src_sar.bounds.right, src_sar.bounds.top],
                    crs2=crs_sar,
                )

                if not spatial_rel.has_sufficient_overlap or not spatial_rel.intersection_bbox_wgs84:
                    raise InsufficientOverlapError(
                        "Optical and SAR rasters do not share sufficient geographic intersection."
                    )

                # Reference grid: Use Optical CRS and Optical resolution
                target_crs = CRS.from_string(crs_opt)
                x_res = abs(src_opt.transform.a)
                y_res = abs(src_opt.transform.e)

                if target_crs.is_geographic:
                    inter_bounds = spatial_rel.intersection_bbox_wgs84
                else:
                    inter_bounds = list(
                        transform_bounds(
                            "EPSG:4326",
                            target_crs,
                            *spatial_rel.intersection_bbox_wgs84,
                        )
                    )

                left, bottom, right, top = inter_bounds
                grid_w = max(1, int(round((right - left) / x_res)))
                grid_h = max(1, int(round((top - bottom) / y_res)))
                grid_transform = from_bounds(left, bottom, right, top, grid_w, grid_h)

            steps.append("reproject_and_resample_both_to_common_spatial_grid")
            aligned_opt_tif = proc_opt_dir / f"aligned_optical_{opt_path.stem}.tif"
            aligned_sar_tif = proc_sar_dir / f"aligned_sar_{sar_path.stem}.tif"

            reproject_and_resample_raster(
                src_path=opt_path,
                dst_path=aligned_opt_tif,
                target_crs=crs_opt,
                target_bounds=[left, bottom, right, top],
                target_resolution=(x_res, y_res),
                resampling_method=Resampling.bilinear,
            )
            reproject_and_resample_raster(
                src_path=sar_path,
                dst_path=aligned_sar_tif,
                target_crs=crs_opt,
                target_bounds=[left, bottom, right, top],
                target_resolution=(x_res, y_res),
                resampling_method=Resampling.bilinear,
            )

            # Modality-specific preprocessing on aligned grids
            steps.append("modality_specific_preprocessing_and_normalization")
            with rasterio.open(aligned_opt_tif) as s_opt, rasterio.open(aligned_sar_tif) as s_sar:
                # Optical processing: 3 channels
                opt_count = s_opt.count
                if opt_count >= 3:
                    opt_data = s_opt.read([1, 2, 3])
                else:
                    opt_data = np.repeat(s_opt.read(1)[np.newaxis, :, :], 3, axis=0)
                norm_optical = self.normalize_percentile(
                    opt_data, p_min=self.p_min_optical, p_max=self.p_max_optical
                )

                # SAR processing: dB calibration & speckle filtering
                sar_count = s_sar.count
                sar_raw = [s_sar.read(i + 1).astype(np.float32) for i in range(min(sar_count, 2))]
                sar_calibrated = []
                for b in sar_raw:
                    db = 10.0 * np.log10(np.maximum(b, 1e-6))
                    if self.apply_sar_speckle_filter:
                        db = SARPreprocessor.simple_speckle_filter(db, window_size=3)
                    sar_calibrated.append(db)
                sar_data = np.stack(sar_calibrated, axis=0)
                norm_sar = self.normalize_percentile(
                    sar_data, p_min=self.p_min_sar, p_max=self.p_max_sar
                )
                if norm_sar.shape[0] == 1:
                    norm_sar_3ch = np.repeat(norm_sar, 3, axis=0)
                elif norm_sar.shape[0] == 2:
                    ratio = np.clip(
                        (norm_sar[0].astype(np.float32) / (norm_sar[1].astype(np.float32) + 1.0)) * 128.0,
                        0,
                        255,
                    ).astype(np.uint8)
                    norm_sar_3ch = np.stack([norm_sar[0], norm_sar[1], ratio], axis=0)
                else:
                    norm_sar_3ch = norm_sar[:3]

            preview_opt_png = proc_opt_dir / f"preview_optical_{opt_path.stem}.png"
            preview_sar_png = proc_sar_dir / f"preview_sar_{sar_path.stem}.png"
            self.save_png_preview(preview_opt_png, norm_optical)
            self.save_png_preview(preview_sar_png, norm_sar_3ch)

            steps.append("generate_paired_cross_modal_tiles")
            windows = self.generate_tile_windows(
                width=grid_w,
                height=grid_h,
                tile_size=self.tile_size,
                stride=self.stride,
            )

            tile_references: list[TileReference] = []
            tile_pairs: list[TilePair] = []

            source_id_opt = str(optical_asset.get("asset_id") or opt_path.stem)
            source_id_sar = str(sar_asset.get("asset_id") or sar_path.stem)

            for idx, (col_off, row_off, w, h) in enumerate(windows):
                opt_slice = norm_optical[:, row_off : row_off + h, col_off : col_off + w]
                sar_slice = norm_sar_3ch[:, row_off : row_off + h, col_off : col_off + w]

                if w < self.tile_size or h < self.tile_size:
                    padded_opt = np.zeros((3, self.tile_size, self.tile_size), dtype=np.uint8)
                    padded_sar = np.zeros((3, self.tile_size, self.tile_size), dtype=np.uint8)
                    padded_opt[:, :h, :w] = opt_slice
                    padded_sar[:, :h, :w] = sar_slice
                    opt_to_save, sar_to_save = padded_opt, padded_sar
                else:
                    opt_to_save, sar_to_save = opt_slice, sar_slice

                tile_name_opt = f"tile_opt_{idx:04d}.png"
                tile_name_sar = f"tile_sar_{idx:04d}.png"

                tile_path_opt = tiles_opt_dir / tile_name_opt
                tile_path_sar = tiles_sar_dir / tile_name_sar

                self.save_png_preview(tile_path_opt, opt_to_save)
                self.save_png_preview(tile_path_sar, sar_to_save)

                opt_id = f"tile_{idx:04d}_opt"
                sar_id = f"tile_{idx:04d}_sar"

                ref_opt = self.create_tile_reference(
                    tile_index=idx,
                    source_asset_id=source_id_opt,
                    modality=Modality.OPTICAL.value,
                    file_path=tile_path_opt,
                    col_off=col_off,
                    row_off=row_off,
                    tile_w=w,
                    tile_h=h,
                    parent_transform=grid_transform,
                    crs=crs_opt,
                    pair_tag="optical",
                    pair_tile_id=sar_id,
                    acquired_at=optical_asset.get("acquired_at"),
                )

                ref_sar = self.create_tile_reference(
                    tile_index=idx,
                    source_asset_id=source_id_sar,
                    modality=Modality.SAR.value,
                    file_path=tile_path_sar,
                    col_off=col_off,
                    row_off=row_off,
                    tile_w=w,
                    tile_h=h,
                    parent_transform=grid_transform,
                    crs=crs_opt,
                    pair_tag="sar",
                    pair_tile_id=opt_id,
                    acquired_at=sar_asset.get("acquired_at"),
                )

                tile_references.extend([ref_opt, ref_sar])
                tile_pairs.append(
                    TilePair(
                        pair_index=idx,
                        tile_id_1=opt_id,
                        tile_id_2=sar_id,
                        file_path_1=str(tile_path_opt.resolve()),
                        file_path_2=str(tile_path_sar.resolve()),
                        tag_1="optical",
                        tag_2="sar",
                        bounds=ref_opt.bounds,
                        crs=crs_opt,
                    )
                )

            steps.append("preserve_cross_modal_spatial_reference_mapping")

            return PreprocessResult(
                input_class=InputClass.OPTICAL_SAR,
                success=True,
                processed_assets=[
                    {
                        "tag": "optical",
                        "source_asset_id": source_id_opt,
                        "aligned_tif": str(aligned_opt_tif.resolve()),
                        "preview_png": str(preview_opt_png.resolve()),
                    },
                    {
                        "tag": "sar",
                        "source_asset_id": source_id_sar,
                        "aligned_tif": str(aligned_sar_tif.resolve()),
                        "preview_png": str(preview_sar_png.resolve()),
                        "speckle_filtered": self.apply_sar_speckle_filter,
                    },
                ],
                tile_references=tile_references,
                tile_pairs=tile_pairs,
                preprocessing_steps=steps,
                spatial_reference={
                    "crs": crs_opt,
                    "transform": [float(x) for x in grid_transform],
                    "width": grid_w,
                    "height": grid_h,
                    "intersection_bounds": inter_bounds,
                },
                output_paths={
                    "processed_optical_dir": str(proc_opt_dir.resolve()),
                    "processed_sar_dir": str(proc_sar_dir.resolve()),
                    "tiles_optical_dir": str(tiles_opt_dir.resolve()),
                    "tiles_sar_dir": str(tiles_sar_dir.resolve()),
                },
                warnings=[],
                errors=[],
                metadata={
                    "tile_pair_count": len(tile_pairs),
                    "tile_size": self.tile_size,
                    "stride": self.stride,
                },
            )
        except Exception as e:
            logging.error(f"Error in optical-SAR preprocessing: {e}")
            raise PreprocessingError(f"Optical-SAR preprocessing failed: {e}")
