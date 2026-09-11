"""
SatQuery AI — Mask & Spatial Evidence Validation Layer (§7, §8)

Validates raster segmentation masks and vectorized geometries before they are
registered as AnalysisObjects or exposed to the UI / reasoning layers.
Ensures:
- Real non-empty raster mask alignment
- Topological validity of polygons (via Shapely)
- Elimination of fake / degenerate masks (e.g. AOI bounding box as detection, ungrounded 100% fill)
- Coordinate containment within scene bounds in WGS84
- Precise geodetic area and centroid calculation
"""

from __future__ import annotations

import math
from typing import Any
import numpy as np
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely.ops import transform as shapely_transform
from shapely.validation import make_valid

try:
    import pyproj
    HAS_PYPROJ = True
except ImportError:
    pyproj = None
    HAS_PYPROJ = False

from backend.schemas import AnalysisObject
from src.logger import logging


def validate_mask_array(
    mask: np.ndarray,
    min_pixels: int = 4,
    max_fraction: float = 0.995,
    allow_full_scene: bool = False,
) -> tuple[bool, str | None]:
    """
    Validates a 2D binary/boolean raster mask.
    Rejects completely empty masks or ungrounded full-frame rectangles.
    """
    if not isinstance(mask, np.ndarray):
        return False, "Mask must be a numpy ndarray"
    
    if mask.ndim != 2:
        return False, f"Mask must be 2D, got shape {mask.shape}"
    
    total_pixels = mask.size
    if total_pixels == 0:
        return False, "Mask has 0 pixels"
    
    foreground_count = int(np.count_nonzero(mask))
    if foreground_count < min_pixels:
        return False, f"Mask is effectively empty ({foreground_count} foreground pixels < {min_pixels})"
    
    fraction = foreground_count / float(total_pixels)
    if fraction > max_fraction and not allow_full_scene:
        return False, f"Suspicious full-frame mask coverage ({fraction*100:.1f}% >= {max_fraction*100:.1f}%)"
    
    return True, None


def validate_geometry(
    geom_dict: dict[str, Any] | None,
    scene_bounds_wgs84: list[float] | None = None,
    min_area_m2: float = 1.0,
) -> tuple[bool, dict[str, Any] | None, str | None]:
    """
    Validates a GeoJSON geometry dictionary.
    Ensures topological validity, coordinate ordering [lon, lat], and scene containment.
    Returns: (is_valid, repaired_geometry_dict, rejection_reason)
    """
    if geom_dict is None:
        return False, None, "Geometry is None"
    
    try:
        s_geom = shape(geom_dict)
    except Exception as exc:
        return False, None, f"Failed to parse GeoJSON geometry: {exc}"
    
    if s_geom.is_empty:
        return False, None, "Geometry is empty"
    
    if not s_geom.is_valid:
        s_geom = make_valid(s_geom)
        if s_geom.is_empty:
            return False, None, "Geometry was invalid and could not be repaired"
    
    # Check WGS84 coordinate bounds
    min_x, min_y, max_x, max_y = s_geom.bounds
    if not (-180.0 <= min_x <= 180.0 and -180.0 <= max_x <= 180.0 and -90.0 <= min_y <= 90.0 and -90.0 <= max_y <= 90.0):
        return False, None, f"Coordinates outside valid WGS84 bounds: {[min_x, min_y, max_x, max_y]}"
    
    # If scene bounds provided [min_lon, min_lat, max_lon, max_lat], ensure containment with tolerance
    if scene_bounds_wgs84 and len(scene_bounds_wgs84) == 4:
        s_min_lon, s_min_lat, s_max_lon, s_max_lat = scene_bounds_wgs84
        pad_lon = max(0.01, (s_max_lon - s_min_lon) * 0.1)
        pad_lat = max(0.01, (s_max_lat - s_min_lat) * 0.1)
        
        if (min_x < s_min_lon - pad_lon or max_x > s_max_lon + pad_lon or
            min_y < s_min_lat - pad_lat or max_y > s_max_lat + pad_lat):
            return False, None, f"Geometry bounds {[min_x, min_y, max_x, max_y]} exceed scene bounds {scene_bounds_wgs84}"
        
        # Check if geometry is trivially equal to the scene bounds box (fake detection rejection)
        scene_box = Polygon([
            (s_min_lon, s_min_lat),
            (s_max_lon, s_min_lat),
            (s_max_lon, s_max_lat),
            (s_min_lon, s_max_lat),
            (s_min_lon, s_min_lat),
        ])
        if s_geom.geom_type == "Polygon" and scene_box.area > 0:
            iou = s_geom.intersection(scene_box).area / (s_geom.union(scene_box).area + 1e-9)
            if iou > 0.98 or s_geom.equals_exact(scene_box, tolerance=1e-5):
                return False, None, "Geometry trivially equals entire scene bounding box (rejected as fake mask)"

    return True, mapping(s_geom), None


def compute_geodetic_metrics(geom_dict: dict[str, Any]) -> tuple[float, list[float], list[float]]:
    """
    Computes accurate geodesic area (m^2), centroid [lon, lat], and bbox [min_lon, min_lat, max_lon, max_lat].
    """
    s_geom = shape(geom_dict)
    min_x, min_y, max_x, max_y = s_geom.bounds
    bbox = [round(min_x, 6), round(min_y, 6), round(max_x, 6), round(max_y, 6)]
    
    centroid_pt = s_geom.centroid
    centroid = [round(centroid_pt.x, 6), round(centroid_pt.y, 6)]
    
    # Geodetic area calculation using pyproj / equal area projection centered at centroid
    if HAS_PYPROJ and pyproj is not None:
        try:
            wgs84 = pyproj.CRS("EPSG:4326")
            aeqd = pyproj.CRS(f"+proj=aeqd +lat_0={centroid_pt.y} +lon_0={centroid_pt.x} +datum=WGS84 +units=m")
            project = pyproj.Transformer.from_crs(wgs84, aeqd, always_xy=True).transform
            projected_geom = shapely_transform(project, s_geom)
            area_m2 = round(float(projected_geom.area), 2)
        except Exception:
            area_m2 = None
    else:
        area_m2 = None

    if area_m2 is None:
        # Fallback approximation for WGS84 degree area
        lat_rad = math.radians(centroid_pt.y)
        m_per_deg_lat = 111132.954 - 559.822 * math.cos(2 * lat_rad) + 1.175 * math.cos(4 * lat_rad)
        m_per_deg_lon = 111412.84 * math.cos(lat_rad) - 93.5 * math.cos(3 * lat_rad)
        area_m2 = round(float(s_geom.area * m_per_deg_lat * m_per_deg_lon), 2)
        
    return area_m2, centroid, bbox


def validate_and_build_analysis_object(
    object_id: str,
    target: str,
    modality: str,
    sensor: str | None,
    scene_id: str | None,
    asset_id: str | None,
    geometry: dict[str, Any] | None,
    label: str,
    confidence: float,
    source_model: str,
    provenance: dict[str, Any] | None = None,
    mask_path: str | None = None,
    scene_bounds_wgs84: list[float] | None = None,
    properties: dict[str, Any] | None = None,
) -> AnalysisObject | None:
    """
    Validates and instantiates an authoritative AnalysisObject.
    Rejects invalid/fake geometries and populates verified metrics.
    """
    props = dict(properties or {})
    prov = dict(provenance or {})
    prov.update({
        "source_model": source_model,
        "modality": modality,
        "validated": True,
    })
    
    if geometry is not None:
        valid_geom, repaired_geom, reason = validate_geometry(geometry, scene_bounds_wgs84=scene_bounds_wgs84)
        if not valid_geom or repaired_geom is None:
            logging.warning(f"[MaskValidator] Rejected geometry for object {object_id} ({target}): {reason}")
            return None
        
        area_m2, centroid, bbox = compute_geodetic_metrics(repaired_geom)
        return AnalysisObject(
            object_id=object_id,
            target=target,
            modality=modality,
            sensor=sensor,
            scene_id=scene_id,
            asset_id=asset_id,
            mask_path=mask_path,
            geometry=repaired_geom,
            bbox=bbox,
            centroid=centroid,
            label=label,
            confidence=max(0.0, min(1.0, float(confidence))),
            source_model=source_model,
            provenance=prov,
            area_m2=area_m2,
            properties=props,
        )
    else:
        # Non-spatial or scene-level tag object
        return AnalysisObject(
            object_id=object_id,
            target=target,
            modality=modality,
            sensor=sensor,
            scene_id=scene_id,
            asset_id=asset_id,
            mask_path=mask_path,
            geometry=None,
            bbox=None,
            centroid=None,
            label=label,
            confidence=max(0.0, min(1.0, float(confidence))),
            source_model=source_model,
            provenance=prov,
            area_m2=None,
            properties=props,
        )
