"""
SatQuery AI — Geospatial & Raster Manipulation Services
"""
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import Affine, from_bounds
from rasterio.warp import calculate_default_transform, reproject, transform_bounds
from rasterio.windows import Window
from shapely.geometry import Polygon, box, mapping, shape
from shapely.ops import transform as shapely_transform

from backend.exceptions import InvalidRasterError, UnsupportedFormatError
from backend.schemas import SpatialRelationship, TemporalRelationship
from src.logger import logging


def extract_raster_metadata(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Extract comprehensive geospatial and raster metadata from a file header
    without loading full image arrays into memory.
    """
    path = Path(file_path)
    if not path.exists():
        raise InvalidRasterError(f"Raster file not found: {file_path}")

    try:
        with rasterio.open(path) as src:
            bounds = [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top]
            crs_str = src.crs.to_string() if src.crs else "EPSG:4326"
            
            # Compute WGS84 bounds
            bounds_wgs84 = None
            if src.crs:
                try:
                    if src.crs.is_geographic:
                        bounds_wgs84 = bounds
                    else:
                        bounds_wgs84 = list(transform_bounds(src.crs, "EPSG:4326", *bounds))
                except Exception as e:
                    logging.warning(f"Could not transform bounds to WGS84: {e}")
                    bounds_wgs84 = bounds

            # Extract tags and metadata
            tags = src.tags()
            band_descriptions = [src.descriptions[i] or f"Band_{i+1}" for i in range(src.count)]

            # Check for acquisition date in tags
            acquired_at = None
            date_candidates = [
                tags.get("TIFFTAG_DATETIME"),
                tags.get("ACQUISITION_DATETIME"),
                tags.get("DATETIME"),
                tags.get("ACQUISITION_DATE"),
                tags.get("IMAGE_DATE"),
            ]
            for candidate in date_candidates:
                if candidate:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                        try:
                            acquired_at = datetime.strptime(candidate[:19], fmt[: len(candidate[:19])])
                            break
                        except ValueError:
                            continue
                if acquired_at:
                    break

            nodata_val = src.nodatavals[0] if src.nodatavals and src.nodatavals[0] is not None else None

            return {
                "file_path": str(path.resolve()),
                "filename": path.name,
                "driver": src.driver,
                "width": src.width,
                "height": src.height,
                "count": src.count,
                "dtypes": [str(d) for d in src.dtypes],
                "crs": crs_str,
                "transform": [float(x) for x in src.transform],
                "bounds": bounds,
                "bounds_wgs84": bounds_wgs84,
                "nodata": float(nodata_val) if nodata_val is not None else None,
                "band_descriptions": band_descriptions,
                "tags": tags,
                "acquired_at": acquired_at,
            }
    except rasterio.errors.RasterioError as e:
        raise InvalidRasterError(f"Failed reading raster metadata from {path.name}: {e}")
    except Exception as e:
        raise InvalidRasterError(f"Unexpected error inspecting raster {path.name}: {e}")


def compute_spatial_overlap(
    bounds1: List[float],
    crs1: str,
    bounds2: List[float],
    crs2: str,
    min_overlap_threshold: float = 0.10,
) -> SpatialRelationship:
    """
    Compute spatial intersection, overlap fraction, and IoU between two raster bounds.
    Transforms footprints into WGS84 for unified geometric analysis.
    """
    try:
        # Convert bounds1 to WGS84
        if crs1 and crs1.upper() != "EPSG:4326":
            b1_wgs = list(transform_bounds(CRS.from_string(crs1), "EPSG:4326", *bounds1))
        else:
            b1_wgs = bounds1

        # Convert bounds2 to WGS84
        if crs2 and crs2.upper() != "EPSG:4326":
            b2_wgs = list(transform_bounds(CRS.from_string(crs2), "EPSG:4326", *bounds2))
        else:
            b2_wgs = bounds2

        poly1 = box(*b1_wgs)
        poly2 = box(*b2_wgs)

        area1 = poly1.area
        area2 = poly2.area

        if area1 <= 0 or area2 <= 0:
            return SpatialRelationship(
                overlap_fraction_1=0.0,
                overlap_fraction_2=0.0,
                iou=0.0,
                intersection_bbox_wgs84=None,
                intersection_wkt=None,
                has_sufficient_overlap=False,
            )

        intersection = poly1.intersection(poly2)
        inter_area = intersection.area

        overlap_1 = float(inter_area / area1) if area1 > 0 else 0.0
        overlap_2 = float(inter_area / area2) if area2 > 0 else 0.0
        
        union_area = poly1.union(poly2).area
        iou = float(inter_area / union_area) if union_area > 0 else 0.0

        inter_bounds = list(intersection.bounds) if not intersection.is_empty else None
        inter_wkt = intersection.wkt if not intersection.is_empty else None

        # Sufficient overlap requires meaningful overlap on both or a high mutual fraction
        has_sufficient = (
            not intersection.is_empty
            and (overlap_1 >= min_overlap_threshold or overlap_2 >= min_overlap_threshold)
            and iou >= (min_overlap_threshold / 2.0)
        )

        return SpatialRelationship(
            overlap_fraction_1=round(overlap_1, 4),
            overlap_fraction_2=round(overlap_2, 4),
            iou=round(iou, 4),
            intersection_bbox_wgs84=inter_bounds,
            intersection_wkt=inter_wkt,
            has_sufficient_overlap=has_sufficient,
        )
    except Exception as e:
        logging.warning(f"Error computing spatial overlap: {e}")
        return SpatialRelationship(
            overlap_fraction_1=0.0,
            overlap_fraction_2=0.0,
            iou=0.0,
            intersection_bbox_wgs84=None,
            intersection_wkt=None,
            has_sufficient_overlap=False,
        )


def compute_temporal_relationship(
    date1: Optional[datetime],
    date2: Optional[datetime],
    min_distinct_seconds: float = 60.0,
) -> TemporalRelationship:
    """
    Analyze the temporal gap and chronological relationship between two acquisition timestamps.
    """
    if date1 is None or date2 is None:
        return TemporalRelationship(
            date_1=date1,
            date_2=date2,
            days_difference=None,
            is_distinct_time=False,
            is_chronological=True,
        )

    diff_seconds = abs((date2 - date1).total_seconds())
    days_diff = diff_seconds / 86400.0
    is_distinct = diff_seconds >= min_distinct_seconds
    is_chronological = date1 <= date2

    return TemporalRelationship(
        date_1=date1,
        date_2=date2,
        days_difference=round(days_diff, 4),
        is_distinct_time=is_distinct,
        is_chronological=is_chronological,
    )


def reproject_and_resample_raster(
    src_path: Union[str, Path],
    dst_path: Union[str, Path],
    target_crs: Optional[str] = None,
    target_bounds: Optional[List[float]] = None,
    target_resolution: Optional[Tuple[float, float]] = None,
    resampling_method: Resampling = Resampling.bilinear,
) -> Dict[str, Any]:
    """
    Reproject, crop to target bounds, and resample a raster to match a desired spatial reference.
    Preserves exact geospatial transform and headers.
    """
    src_p = Path(src_path)
    dst_p = Path(dst_path)
    dst_p.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(src_p) as src:
        dst_crs = CRS.from_string(target_crs) if target_crs else src.crs
        
        if target_bounds:
            # target_bounds is [left, bottom, right, top] in dst_crs
            left, bottom, right, top = target_bounds
            if target_resolution:
                x_res, y_res = target_resolution
            else:
                x_res = abs(src.transform.a)
                y_res = abs(src.transform.e)
                
            dst_width = max(1, int(round((right - left) / x_res)))
            dst_height = max(1, int(round((top - bottom) / y_res)))
            dst_transform = from_bounds(left, bottom, right, top, dst_width, dst_height)
        else:
            dst_transform, dst_width, dst_height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds, resolution=target_resolution
            )

        kwargs = src.meta.copy()
        kwargs.update({
            "crs": dst_crs,
            "transform": dst_transform,
            "width": dst_width,
            "height": dst_height,
        })

        with rasterio.open(dst_p, "w", **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=resampling_method,
                )

    return extract_raster_metadata(dst_p)
