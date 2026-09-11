"""
SatQuery AI — Bitemporal Preprocessing Pipeline
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
from backend.utils import create_job_directory
from src.logger import logging


class BitemporalPreprocessor(BasePreprocessor):
    """
    Dedicated preprocessor for BI_TEMPORAL imagery (e.g. T1 and T2 optical pairs).
    
    Performs spatial alignment, co-registration / resampling to a shared intersection grid,
    consistent radiometric normalization across timestamps, and produces strictly
    geographically-aligned paired tiles for change detection (BIT) and bitemporal analysis.
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
        assets: list[dict[str, Any]],
        job_id: str,
        job_storage_dir: Path | None = None,
    ) -> PreprocessResult:
        """
        Execute paired bitemporal alignment and synchronized tiling.
        """
        if len(assets) < 2:
            raise PreprocessingError("Bitemporal preprocessing requires at least 2 asset dictionaries.")

        # Sort chronologically if acquisition dates are present
        a1, a2 = assets[0], assets[1]
        d1 = a1.get("acquired_at")
        d2 = a2.get("acquired_at")
        if d1 and d2 and d1 > d2:
            a1, a2 = a2, a1  # Ensure a1 is T1 (earlier) and a2 is T2 (later)

        p1_str = a1.get("file_path")
        p2_str = a2.get("file_path")
        if not p1_str or not p2_str:
            raise PreprocessingError("Assets missing 'file_path'.")

        path1, path2 = Path(p1_str), Path(p2_str)
        if not path1.exists() or not path2.exists():
            raise InvalidRasterError("One or both bitemporal raster files do not exist.")

        dirs = create_job_directory(job_id, base_dir=job_storage_dir)
        processed_dir = dirs["processed"]
        tiles_dir = dirs["tiles"]

        proc_t1_dir = processed_dir / "t1"
        proc_t2_dir = processed_dir / "t2"
        tiles_t1_dir = tiles_dir / "t1"
        tiles_t2_dir = tiles_dir / "t2"

        for d in (proc_t1_dir, proc_t2_dir, tiles_t1_dir, tiles_t2_dir):
            d.mkdir(parents=True, exist_ok=True)

        steps = ["validate_t1_t2_rasters", "calculate_spatial_intersection"]

        try:
            # Inspect T1 and T2
            from backend.services.geospatial import _infer_fallback_bounds

            with rasterio.open(path1) as src1, rasterio.open(path2) as src2:
                has_georef_1 = src1.crs is not None and not getattr(src1.transform, "is_identity", False)
                has_georef_2 = src2.crs is not None and not getattr(src2.transform, "is_identity", False)
                
                crs1 = src1.crs.to_string() if src1.crs else "EPSG:4326"
                crs2 = src2.crs.to_string() if src2.crs else "EPSG:4326"

                if has_georef_1 and has_georef_2:
                    # Check spatial intersection
                    spatial_rel = compute_spatial_overlap(
                        bounds1=[src1.bounds.left, src1.bounds.bottom, src1.bounds.right, src1.bounds.top],
                        crs1=crs1,
                        bounds2=[src2.bounds.left, src2.bounds.bottom, src2.bounds.right, src2.bounds.top],
                        crs2=crs2,
                    )
                    if not spatial_rel.has_sufficient_overlap or not spatial_rel.intersection_bbox_wgs84:
                        raise InsufficientOverlapError(
                            "Bitemporal rasters do not share sufficient geographic intersection."
                        )

                    # Reference CRS & resolution: Use T1 CRS and resolution
                    target_crs = CRS.from_string(crs1)
                    x_res = abs(src1.transform.a)
                    y_res = abs(src1.transform.e)

                    # Calculate intersection bounding box in T1 CRS
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
                    # Snap to pixel grid
                    grid_w = max(1, int(round((right - left) / x_res)))
                    grid_h = max(1, int(round((top - bottom) / y_res)))
                    grid_transform = from_bounds(left, bottom, right, top, grid_w, grid_h)

                    steps.append("coregister_and_resample_t1_t2_to_common_grid")
                    aligned_t1_tif = proc_t1_dir / f"aligned_t1_{path1.stem}.tif"
                    aligned_t2_tif = proc_t2_dir / f"aligned_t2_{path2.stem}.tif"

                    # Resample both rasters onto the exact common intersection grid
                    reproject_and_resample_raster(
                        src_path=path1,
                        dst_path=aligned_t1_tif,
                        target_crs=crs1,
                        target_bounds=[left, bottom, right, top],
                        target_resolution=(x_res, y_res),
                        resampling_method=Resampling.bilinear,
                    )
                    reproject_and_resample_raster(
                        src_path=path2,
                        dst_path=aligned_t2_tif,
                        target_crs=crs1,
                        target_bounds=[left, bottom, right, top],
                        target_resolution=(x_res, y_res),
                        resampling_method=Resampling.bilinear,
                    )
                else:
                    # Unreferenced demo or presentation TIFF pair: align pixel arrays directly
                    fb = a1.get("bounds_wgs84") or a2.get("bounds_wgs84") or _infer_fallback_bounds(path1.name)
                    grid_w = src1.width
                    grid_h = src1.height
                    left, bottom, right, top = fb[0], fb[1], fb[2], fb[3]
                    grid_transform = from_bounds(left, bottom, right, top, grid_w, grid_h)
                    crs1 = "EPSG:4326"

                    aligned_t1_tif = proc_t1_dir / f"aligned_t1_{path1.stem}.tif"
                    aligned_t2_tif = proc_t2_dir / f"aligned_t2_{path2.stem}.tif"

                    d1 = src1.read()
                    d2 = src2.read()
                    if d2.shape[1:] != d1.shape[1:]:
                        from PIL import Image as _PILImg
                        # Resize T2 to match T1 shape
                        chans = []
                        for c in range(d2.shape[0]):
                            im = _PILImg.fromarray(d2[c]).resize((grid_w, grid_h), _PILImg.BILINEAR)
                            chans.append(np.array(im))
                        d2 = np.stack(chans, axis=0)

                    with rasterio.open(
                        aligned_t1_tif, "w", driver="GTiff", height=grid_h, width=grid_w,
                        count=d1.shape[0], dtype=d1.dtype, crs=crs1, transform=grid_transform
                    ) as dst1:
                        dst1.write(d1)

                    with rasterio.open(
                        aligned_t2_tif, "w", driver="GTiff", height=grid_h, width=grid_w,
                        count=d2.shape[0], dtype=d2.dtype, crs=crs1, transform=grid_transform
                    ) as dst2:
                        dst2.write(d2)

            steps.append("consistent_radiometric_normalization")
            with rasterio.open(aligned_t1_tif) as s1, rasterio.open(aligned_t2_tif) as s2:
                # Read 3 channels (RGB) or single channel duplicated
                count1 = s1.count
                count2 = s2.count
                data1 = s1.read([1, 2, 3]) if count1 >= 3 else np.repeat(s1.read(1)[np.newaxis, :, :], 3, axis=0)
                data2 = s2.read([1, 2, 3]) if count2 >= 3 else np.repeat(s2.read(1)[np.newaxis, :, :], 3, axis=0)

            # Normalize T1 and T2 consistently
            norm1 = self.normalize_percentile(data1, p_min=self.p_min, p_max=self.p_max)
            norm2 = self.normalize_percentile(data2, p_min=self.p_min, p_max=self.p_max)

            # Save PNG previews
            preview_t1_png = proc_t1_dir / f"preview_t1_{path1.stem}.png"
            preview_t2_png = proc_t2_dir / f"preview_t2_{path2.stem}.png"
            self.save_png_preview(preview_t1_png, norm1)
            self.save_png_preview(preview_t2_png, norm2)

            steps.append("generate_paired_synchronized_tiles")
            windows = self.generate_tile_windows(
                width=grid_w,
                height=grid_h,
                tile_size=self.tile_size,
                stride=self.stride,
            )

            tile_references: list[TileReference] = []
            tile_pairs: list[TilePair] = []

            source_id_1 = str(a1.get("asset_id") or path1.stem)
            source_id_2 = str(a2.get("asset_id") or path2.stem)

            for idx, (col_off, row_off, w, h) in enumerate(windows):
                t1_slice = norm1[:, row_off : row_off + h, col_off : col_off + w]
                t2_slice = norm2[:, row_off : row_off + h, col_off : col_off + w]

                # Pad to square tile_size if boundary tile
                if w < self.tile_size or h < self.tile_size:
                    padded_1 = np.zeros((3, self.tile_size, self.tile_size), dtype=np.uint8)
                    padded_2 = np.zeros((3, self.tile_size, self.tile_size), dtype=np.uint8)
                    padded_1[:, :h, :w] = t1_slice
                    padded_2[:, :h, :w] = t2_slice
                    t1_to_save, t2_to_save = padded_1, padded_2
                else:
                    t1_to_save, t2_to_save = t1_slice, t2_slice

                tile_name_1 = f"tile_t1_{idx:04d}.png"
                tile_name_2 = f"tile_t2_{idx:04d}.png"

                tile_path_1 = tiles_t1_dir / tile_name_1
                tile_path_2 = tiles_t2_dir / tile_name_2

                self.save_png_preview(tile_path_1, t1_to_save)
                self.save_png_preview(tile_path_2, t2_to_save)

                t1_id = f"tile_{idx:04d}_t1"
                t2_id = f"tile_{idx:04d}_t2"

                ref1 = self.create_tile_reference(
                    tile_index=idx,
                    source_asset_id=source_id_1,
                    modality=Modality.OPTICAL.value,
                    file_path=tile_path_1,
                    col_off=col_off,
                    row_off=row_off,
                    tile_w=w,
                    tile_h=h,
                    parent_transform=grid_transform,
                    crs=crs1,
                    pair_tag="t1",
                    pair_tile_id=t2_id,
                    acquired_at=a1.get("acquired_at"),
                )

                ref2 = self.create_tile_reference(
                    tile_index=idx,
                    source_asset_id=source_id_2,
                    modality=Modality.OPTICAL.value,
                    file_path=tile_path_2,
                    col_off=col_off,
                    row_off=row_off,
                    tile_w=w,
                    tile_h=h,
                    parent_transform=grid_transform,
                    crs=crs1,
                    pair_tag="t2",
                    pair_tile_id=t1_id,
                    acquired_at=a2.get("acquired_at"),
                )

                tile_references.extend([ref1, ref2])
                tile_pairs.append(
                    TilePair(
                        pair_index=idx,
                        tile_id_1=t1_id,
                        tile_id_2=t2_id,
                        file_path_1=str(tile_path_1.resolve()),
                        file_path_2=str(tile_path_2.resolve()),
                        tag_1="t1",
                        tag_2="t2",
                        bounds=ref1.bounds,
                        crs=crs1,
                    )
                )

            steps.append("preserve_paired_spatial_reference_mapping")

            return PreprocessResult(
                input_class=InputClass.BI_TEMPORAL,
                success=True,
                processed_assets=[
                    {
                        "tag": "t1",
                        "source_asset_id": source_id_1,
                        "aligned_tif": str(aligned_t1_tif.resolve()),
                        "preview_png": str(preview_t1_png.resolve()),
                        "acquired_at": a1.get("acquired_at"),
                    },
                    {
                        "tag": "t2",
                        "source_asset_id": source_id_2,
                        "aligned_tif": str(aligned_t2_tif.resolve()),
                        "preview_png": str(preview_t2_png.resolve()),
                        "acquired_at": a2.get("acquired_at"),
                    },
                ],
                tile_references=tile_references,
                tile_pairs=tile_pairs,
                preprocessing_steps=steps,
                spatial_reference={
                    "crs": crs1,
                    "transform": [float(x) for x in grid_transform],
                    "width": grid_w,
                    "height": grid_h,
                    "intersection_bounds": inter_bounds,
                },
                output_paths={
                    "processed_t1_dir": str(proc_t1_dir.resolve()),
                    "processed_t2_dir": str(proc_t2_dir.resolve()),
                    "tiles_t1_dir": str(tiles_t1_dir.resolve()),
                    "tiles_t2_dir": str(tiles_t2_dir.resolve()),
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
            logging.error(f"Error in bitemporal preprocessing: {e}")
            raise PreprocessingError(f"Bitemporal preprocessing failed: {e}")
