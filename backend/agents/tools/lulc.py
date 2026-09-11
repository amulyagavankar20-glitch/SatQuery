"""Land-cover mapper: Dynamic World (tiny) + optional Prithvi flood.

Default path is a spectral 9-class mapper (numpy/Pillow only) so the app
stays small. If ``weights/dynamic_world.pt`` is present and torch is
installed, that checkpoint is used instead. Prithvi Sen1Floods11 is loaded
only when the query is flood/inundation *and* ``PRITHVI_FLOOD_WEIGHTS_PATH``
points at a local file — never downloaded at import time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Mapping

import numpy as np
from PIL import Image

from backend.config import settings
from .base import BaseTool

DW_CLASSES: tuple[str, ...] = (
    "water",
    "trees",
    "grass",
    "flooded_vegetation",
    "crops",
    "shrub_and_scrub",
    "built",
    "bare",
    "snow_and_ice",
)

VEG = frozenset({"trees", "grass", "crops", "shrub_and_scrub", "flooded_vegetation"})
FLOOD_HINTS = ("flood", "inundat", "high-water", "high water", "standing water")
WATER_HINTS = ("water", "shore", "lake", "reservoir", "river", "pond")
BUILT_HINTS = ("built", "urban", "settlement", "harbour", "harbor", "road")
VEG_HINTS = ("vegetat", "forest", "crop", "tree", "grass", "field")
COAST_HINTS = ("coast", "harbour", "harbor", "marine", "port", "lagoon", "tidal")


def _is_flood_query(q: str) -> bool:
    ql = q.lower()
    return any(h in ql for h in FLOOD_HINTS)


def _focus(q: str) -> str:
    ql = q.lower()
    if _is_flood_query(q):
        return "flood"
    if any(h in ql for h in WATER_HINTS):
        return "water"
    if any(h in ql for h in BUILT_HINTS):
        return "built"
    if any(h in ql for h in VEG_HINTS):
        return "vegetation"
    return "land_cover"


def _is_coastal(query: str, path: str) -> bool:
    blob = f"{query} {path}".lower()
    return any(h in blob for h in COAST_HINTS)


def _rgb_from_stack(arr: np.ndarray) -> np.ndarray:
    if arr.ndim != 3:
        raise ValueError("expected HWC or already handled")
    if arr.shape[2] >= 3:
        rgb = arr[:, :, :3]
    else:
        rgb = np.repeat(arr[:, :, :1], 3, axis=2)
    if rgb.max() > 1.5:
        rgb = rgb / (65535.0 if rgb.max() > 255 else 255.0)
    return np.clip(rgb, 0, 1).astype(np.float32)


def _s2_nine_from_raster(path: Path) -> np.ndarray | None:
    """Return (9, H, W) raw S2 stack in DW band order, or None if not S2."""
    try:
        import rasterio
    except Exception:
        return None
    try:
        with rasterio.open(path) as src:
            count = src.count
            if count < 9:
                return None
            # 9 bands: assume already B2..B12 DW order.
            # 12/13-band L1C: skip coastal/cirrus extras.
            if count == 9:
                idx = list(range(1, 10))
            elif count >= 13:
                idx = [2, 3, 4, 5, 6, 7, 8, 12, 13]
            elif count == 12:
                idx = [2, 3, 4, 5, 6, 7, 8, 11, 12]
            else:
                idx = list(range(1, 10))
            stack = src.read(idx).astype(np.float32)
            return stack
    except Exception:
        return None


def _read_raster_with_meta(path: str) -> tuple[np.ndarray, dict[str, Any], dict[str, np.ndarray]]:
    """
    Read raster with georeferencing metadata and extracted spectral bands.
    Returns: (rgb_array, meta_dict, band_dict)
    """
    p = Path(path)
    meta: dict[str, Any] = {
        "filename": p.name,
        "crs": None,
        "transform": None,
        "width": 0,
        "height": 0,
        "bounds_wgs84": None,
        "is_geotiff": False,
        "band_count": 0,
    }
    bands: dict[str, np.ndarray] = {}
    if not p.is_file():
        raise FileNotFoundError(path)
    suffix = p.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        try:
            import rasterio
            from rasterio.warp import transform_bounds

            with rasterio.open(p) as src:
                count = src.count
                meta["band_count"] = count
                meta["crs"] = src.crs
                meta["transform"] = src.transform
                meta["width"] = src.width
                meta["height"] = src.height
                meta["is_geotiff"] = True
                try:
                    if src.crs:
                        b = list(transform_bounds(src.crs, "EPSG:4326", *src.bounds))
                        if len(b) == 4 and -180 <= b[0] <= 180 and -90 <= b[1] <= 90 and -180 <= b[2] <= 180 and -90 <= b[3] <= 90:
                            meta["bounds_wgs84"] = b
                        else:
                            meta["bounds_wgs84"] = None
                    else:
                        meta["bounds_wgs84"] = None
                except Exception:
                    meta["bounds_wgs84"] = None

                raw_bands = src.read(list(range(1, count + 1))).astype(np.float32)
                # Auto-scale reflectance to [0.0, 1.0]
                max_val = float(raw_bands.max()) if raw_bands.size else 1.0
                if max_val > 1.5:
                    scale = 65535.0 if max_val > 255.0 else 255.0
                    raw_bands = np.clip(raw_bands / scale, 0.0, 1.0)

                if count >= 4:
                    # Standard 4-band Sentinel-2 order: B2=Blue, B3=Green, B4=Red, B8=NIR
                    bands["blue"] = raw_bands[0]
                    bands["green"] = raw_bands[1]
                    bands["red"] = raw_bands[2]
                    bands["nir"] = raw_bands[3]
                    # True color RGB composite: R=B4(index 2), G=B3(index 1), B=B2(index 0)
                    rgb = np.stack([raw_bands[2], raw_bands[1], raw_bands[0]], axis=-1)
                    return rgb, meta, bands
                elif count == 3:
                    # Standard 3-band RGB order: R, G, B
                    bands["red"] = raw_bands[0]
                    bands["green"] = raw_bands[1]
                    bands["blue"] = raw_bands[2]
                    rgb = np.stack([raw_bands[0], raw_bands[1], raw_bands[2]], axis=-1)
                    return rgb, meta, bands
                else:
                    gray = raw_bands[0]
                    bands["gray"] = gray
                    rgb = np.stack([gray, gray, gray], axis=-1)
                    return rgb, meta, bands
        except Exception:
            pass

    from backend.services.geospatial import _infer_fallback_bounds
    img = Image.open(p).convert("RGB")
    max_side = 512
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    meta["width"], meta["height"] = img.size
    meta["band_count"] = 3
    meta["bounds_wgs84"] = _infer_fallback_bounds(p.name)
    rgb = np.asarray(img, dtype=np.float32) / 255.0
    bands["red"] = rgb[:, :, 0]
    bands["green"] = rgb[:, :, 1]
    bands["blue"] = rgb[:, :, 2]
    return rgb, meta, bands


def _classify_optical_scene(
    rgb: np.ndarray,
    bands: dict[str, np.ndarray],
    meta: dict[str, Any],
) -> tuple[np.ndarray, str]:
    """
    Perform pixel-level 9-class land-cover classification.
    Returns: (labels_2d_array, backend_name)
    """
    # Case 1: 4-band multispectral (with NIR)
    if "nir" in bands and "green" in bands and "red" in bands:
        blue = bands.get("blue", rgb[:, :, 2] if rgb.ndim == 3 else np.zeros_like(bands["green"]))
        green = bands["green"]
        red = bands["red"]
        nir = bands["nir"]

        ndwi = (green - nir) / (green + nir + 1e-6)
        ndvi = (nir - red) / (nir + red + 1e-6)
        bright = (red + green + blue) / 3.0

        labels = np.full(red.shape, 7, dtype=np.uint8)  # default: bare / open terrain

        # Water: NDWI > 0, NIR absorbed (NIR < Green), NDVI low
        raw_water = (ndwi > 0.0) & (nir < 0.22) & (nir < green) & (ndvi < 0.12)
        try:
            from scipy.ndimage import label as _scipy_label

            labeled_w, num_w = _scipy_label(raw_water)
            water = np.zeros_like(raw_water)
            for i in range(1, num_w + 1):
                if np.count_nonzero(labeled_w == i) >= 20:
                    water[labeled_w == i] = True
        except Exception:
            water = raw_water

        labels[water] = 0

        # Dense vegetation (Trees)
        dense_veg = (ndvi > 0.45) & ~water
        labels[dense_veg] = 1

        # Crops / cultivated
        crops = (ndvi > 0.28) & (ndvi <= 0.45) & ~water
        labels[crops] = 4

        # Grass / open vegetation
        grass = (ndvi > 0.15) & (ndvi <= 0.28) & (nir > red) & ~water
        labels[grass] = 2

        # Built-up / Urban: high brightness, low NDVI, low NDWI
        built = (bright > 0.12) & (ndvi < 0.18) & (ndwi < -0.05) & ~water
        labels[built] = 6

        return labels, "optical_multispectral_ndwi"

    # Case 2: 3-band Visible RGB only (NIR unavailable)
    red = bands.get("red", rgb[:, :, 0])
    green = bands.get("green", rgb[:, :, 1])
    blue = bands.get("blue", rgb[:, :, 2])

    bright = (red + green + blue) / 3.0
    greenness = 2.0 * green - red - blue
    ndti = (blue - red) / (blue + red + 1e-6)

    # Compute local spatial texture/gradients (built-up has high texture, water is smooth)
    try:
        from scipy.ndimage import sobel
        grad_r = np.hypot(sobel(red, axis=0), sobel(red, axis=1))
        grad_g = np.hypot(sobel(green, axis=0), sobel(green, axis=1))
        grad_b = np.hypot(sobel(blue, axis=0), sobel(blue, axis=1))
        texture = (grad_r + grad_g + grad_b) / 3.0
    except Exception:
        texture = np.zeros_like(red)

    is_grayscale = bool(np.max(np.abs(red - green)) < 0.005 and np.max(np.abs(green - blue)) < 0.005)
    labels = np.full(red.shape, 7, dtype=np.uint8)  # default: bare / open soil

    # Water detection:
    if is_grayscale:
        # Grayscale panchromatic / SAR converted: water is dark, smooth, low texture
        raw_water = (bright < 0.18) & (texture < 0.08)
    else:
        # 1. Clear / blue-dominant water
        clear_water = ((blue >= green) | (ndti > 0.05)) & (blue > red) & (bright < 0.55)
        # 2. Inland / turbid / reservoir water (greenish-khaki hue, g ~ r > b, low texture, low saturation)
        turbid_water = (
            (green >= 0.90 * red)
            & (blue >= 0.65 * red)
            & (red - green < 0.08)
            & (texture < 0.16)
            & (bright > 0.18)
            & (bright < 0.75)
            & (greenness > -0.08)
            & (greenness < 0.22)
        )
        raw_water = clear_water | turbid_water

    try:
        from scipy.ndimage import binary_opening, label as _scipy_label

        opened_water = binary_opening(raw_water, structure=np.ones((3, 3)))
        labeled_w, num_w = _scipy_label(opened_water)
        water = np.zeros_like(raw_water)
        for i in range(1, num_w + 1):
            if np.count_nonzero(labeled_w == i) >= 40:
                water[labeled_w == i] = True
    except Exception:
        water = raw_water

    labels[water] = 0

    # Vegetation:
    veg = (greenness > 0.06) & (green > red) & (green > blue) & ~water
    labels[veg & (greenness > 0.25)] = 1  # trees
    labels[veg & (greenness <= 0.25) & (greenness > 0.12)] = 4  # crops
    labels[veg & (greenness <= 0.12)] = 2  # grass

    # Built-up: distinct edge texture/structures and roofs, not smooth water or soil
    built = ((texture > 0.18) | ((bright > 0.40) & (texture > 0.12))) & (greenness < 0.05) & ~water & ~veg
    labels[built] = 6

    return labels, "optical_rgb_heuristic"


def _fractions(labels: np.ndarray) -> dict[str, float]:
    n = labels.size
    out: dict[str, float] = {}
    for i, name in enumerate(DW_CLASSES):
        out[name] = float(np.count_nonzero(labels == i)) / n if n else 0.0
    return out

CLASS_METADATA: dict[str, dict[str, Any]] = {
    "water": {
        "title": "Surface Water Extent",
        "kind": "water_mask",
        "fill": "#00a8ff",
        "stroke": "#00e5ff",
        "rgba": [0, 168, 255, 180],
    },
    "built": {
        "title": "Built-up / Urban Extent",
        "kind": "built_mask",
        "fill": "#e84118",
        "stroke": "#ff6b6b",
        "rgba": [232, 65, 24, 180],
    },
    "trees": {
        "title": "Tree Canopy / Forest Extent",
        "kind": "tree_mask",
        "fill": "#2ed573",
        "stroke": "#7bed9f",
        "rgba": [46, 213, 115, 180],
    },
    "grass": {
        "title": "Grassland / Meadow Extent",
        "kind": "grass_mask",
        "fill": "#7bed9f",
        "stroke": "#2ed573",
        "rgba": [123, 237, 159, 180],
    },
    "crops": {
        "title": "Agricultural Crops Extent",
        "kind": "crop_mask",
        "fill": "#ffa502",
        "stroke": "#eccc68",
        "rgba": [255, 165, 2, 180],
    },
    "bare": {
        "title": "Bare Soil / Open Ground Extent",
        "kind": "bare_mask",
        "fill": "#f1f2f6",
        "stroke": "#ced6e0",
        "rgba": [241, 242, 246, 180],
    },
    "flood": {
        "title": "Flood Inundation Extent",
        "kind": "flood_mask",
        "fill": "#0097e6",
        "stroke": "#00d2d3",
        "rgba": [0, 151, 230, 200],
    },
    "vegetation": {
        "title": "Combined Vegetation Extent",
        "kind": "vegetation_mask",
        "fill": "#2ed573",
        "stroke": "#7bed9f",
        "rgba": [46, 213, 115, 180],
    },
}


def _mask_to_real_geojson(
    mask: np.ndarray,
    meta: dict[str, Any],
    bounds: list[float] | None,
    kind: str = "water",
    share: float = 0.0,
) -> list[dict[str, Any]]:
    """Convert a binary mask into genuine geographic vector polygons."""
    if mask.sum() == 0:
        return []

    h, w = mask.shape
    pct_str = f"{share * 100:.1f}%" if share > 0 else f"{float(np.count_nonzero(mask)) / mask.size * 100:.1f}%"
    cfg = CLASS_METADATA.get(kind.lower(), {
        "title": f"{kind.replace('_', ' ').title()} Extent",
        "kind": f"{kind}_mask",
        "fill": "#5E8F8A",
        "stroke": "#5E8F8A",
        "rgba": [94, 143, 138, 180],
    })

    has_real_georef = bool(
        meta.get("is_geotiff")
        and meta.get("crs") is not None
        and meta.get("transform") is not None
        and not getattr(meta.get("transform"), "is_identity", False)
    )

    # Method A: If we have real GeoTIFF affine transform and CRS
    if has_real_georef:
        try:
            import rasterio.features
            from rasterio.warp import transform_geom
            from shapely.geometry import shape, mapping
            from shapely.ops import unary_union

            transform = meta["transform"]
            src_crs = meta.get("crs") or "EPSG:4326"

            mask_uint8 = (mask > 0).astype(np.uint8)
            shapes_gen = list(rasterio.features.shapes(mask_uint8, mask=mask_uint8 == 1, transform=transform))

            polys = []
            for geom, val in shapes_gen:
                if val == 1:
                    s = shape(geom)
                    if s.is_valid and not s.is_empty and s.area >= 100:  # min 100 m2
                        polys.append(s)

            if polys:
                union = unary_union(polys)
                raw_geojson = mapping(union)
                if str(src_crs).upper() not in ("EPSG:4326", "WGS84", "OGC:CRS84", "+PROJ=LONGLAT +DATUM=WGS84 +NO_DEFS"):
                    try:
                        wgs_geom = transform_geom(src_crs, "EPSG:4326", raw_geojson)
                    except Exception:
                        wgs_geom = raw_geojson
                else:
                    wgs_geom = raw_geojson

                return [
                    {
                        "type": "Feature",
                        "properties": {
                            "id": f"{kind}-mask-0",
                            "kind": cfg["kind"],
                            "class": kind,
                            "target_class": kind.upper(),
                            "fill": cfg["fill"],
                            "stroke": cfg["stroke"],
                            "label": f"{cfg['title']} ({pct_str} of AOI)",
                        },
                        "geometry": wgs_geom,
                    }
                ]
        except Exception:
            pass

    # Method B: Vectorize using effective bounding box
    from backend.services.geospatial import _infer_fallback_bounds
    eff_bounds = meta.get("bounds_wgs84") or bounds or _infer_fallback_bounds(meta.get("filename", ""))
    if eff_bounds and len(eff_bounds) == 4 and -180 <= eff_bounds[0] <= 180 and -90 <= eff_bounds[1] <= 90:
        try:
            import rasterio.features
            from rasterio.transform import from_bounds
            from shapely.geometry import shape, mapping
            from shapely.ops import unary_union

            west, south, east, north = eff_bounds
            norm_transform = from_bounds(west, south, east, north, w, h)
            mask_uint8 = (mask > 0).astype(np.uint8)
            shapes_gen = list(rasterio.features.shapes(mask_uint8, mask=mask_uint8 == 1, transform=norm_transform))
            polys = [shape(geom) for geom, val in shapes_gen if val == 1 and shape(geom).is_valid]
            if polys:
                union = unary_union(polys)
                return [
                    {
                        "type": "Feature",
                        "properties": {
                            "id": f"{kind}-mask-0",
                            "kind": cfg["kind"],
                            "class": kind,
                            "target_class": kind.upper(),
                            "fill": cfg["fill"],
                            "stroke": cfg["stroke"],
                            "label": f"{cfg['title']} ({pct_str} of AOI)",
                        },
                        "geometry": mapping(union),
                    }
                ]
        except Exception:
            pass

    return []


def _extract_object_detections(
    mask: np.ndarray,
    meta: dict[str, Any],
    bounds: list[float] | None,
    kind: str = "building",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Extracts individual localized object/structure clusters with WGS84 bounding boxes,
    centroids, estimated footprint areas, and GeoJSON polygon features.
    """
    if mask.sum() == 0:
        return [], []

    detections: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    h, w = mask.shape

    has_real_georef = bool(
        meta.get("is_geotiff")
        and meta.get("crs") is not None
        and meta.get("transform") is not None
        and not getattr(meta.get("transform"), "is_identity", False)
    )

    if has_real_georef:
        try:
            import rasterio.features
            from rasterio.warp import transform_geom
            from shapely.geometry import shape, mapping

            transform = meta["transform"]
            src_crs = meta.get("crs") or "EPSG:4326"
            
            try:
                from scipy.ndimage import binary_closing, binary_opening
                cleaned = binary_opening(mask > 0, structure=np.ones((3, 3)))
                cleaned = binary_closing(cleaned, structure=np.ones((5, 5))).astype(np.uint8)
            except Exception:
                cleaned = (mask > 0).astype(np.uint8)

            shapes_gen = list(rasterio.features.shapes(cleaned, mask=cleaned == 1, transform=transform))

            polys = []
            for geom, val in shapes_gen:
                if val == 1:
                    s = shape(geom)
                    if s.is_valid and not s.is_empty and s.area >= 100:
                        try:
                            tol = 0.00003 if ("4326" in str(src_crs)) else 1.5
                            s = s.simplify(tol, preserve_topology=True)
                        except Exception:
                            pass
                        polys.append(s)

            polys.sort(key=lambda p: p.area, reverse=True)

            for i, s in enumerate(polys[:12], 1):
                minx, miny, maxx, maxy = s.bounds
                cx, cy = s.centroid.x, s.centroid.y
                raw_geom = mapping(s)

                if str(src_crs).upper() not in ("EPSG:4326", "WGS84", "OGC:CRS84", "+PROJ=LONGLAT +DATUM=WGS84 +NO_DEFS"):
                    try:
                        wgs_geom = transform_geom(src_crs, "EPSG:4326", raw_geom)
                        wgs_s = shape(wgs_geom)
                        w_minx, w_miny, w_maxx, w_maxy = wgs_s.bounds
                        w_cx, w_cy = wgs_s.centroid.x, wgs_s.centroid.y
                    except Exception:
                        wgs_geom = raw_geom
                        w_minx, w_miny, w_maxx, w_maxy = minx, miny, maxx, maxy
                        w_cx, w_cy = cx, cy
                else:
                    wgs_geom = raw_geom
                    w_minx, w_miny, w_maxx, w_maxy = minx, miny, maxx, maxy
                    w_cx, w_cy = cx, cy

                area_m2 = round(s.area, 1) if ("EPSG:326" in str(src_crs) or "EPSG:3857" in str(src_crs)) else round(s.area * 111320 * 111320, 1)

                det_id = f"det_{kind}_{i}"
                detections.append({
                    "id": det_id,
                    "type": f"{kind}_cluster",
                    "bbox_wgs84": [round(w_minx, 6), round(w_miny, 6), round(w_maxx, 6), round(w_maxy, 6)],
                    "centroid_wgs84": [round(w_cx, 6), round(w_cy, 6)],
                    "area_m2": area_m2,
                    "confidence": 0.88,
                    "image_position": "center",
                })
                features.append({
                    "type": "Feature",
                    "properties": {
                        "id": det_id,
                        "feature_type": "DETECTION",
                        "kind": "grounding",
                        "class": kind,
                        "label": f"{kind.replace('_', ' ').title()} Cluster #{i} (~{area_m2:,.0f} m²)",
                        "confidence": 0.88,
                        "fill": "#00f0ff" if kind == "water" else ("#ff4757" if kind == "built" else "#2ed573"),
                        "stroke": "#00f0ff" if kind == "water" else ("#ff6b81" if kind == "built" else "#2ed573"),
                    },
                    "geometry": wgs_geom,
                })
        except Exception:
            pass

    # Fallback using bounding box
    from backend.services.geospatial import _infer_fallback_bounds
    eff_bounds = meta.get("bounds_wgs84") or bounds or _infer_fallback_bounds(meta.get("filename", ""))
    if not detections and mask.sum() > 0:
        try:
            from scipy.ndimage import label as _scipy_label, find_objects
            labeled, num_features = _scipy_label(mask > 0)
            slices = find_objects(labeled)
            for i, sl in enumerate(slices[:12], 1):
                if sl is None:
                    continue
                yslice, xslice = sl
                pixel_count = int(np.count_nonzero(labeled[yslice, xslice] == i))
                if pixel_count < 10:
                    continue

                if eff_bounds and len(eff_bounds) == 4 and -180 <= eff_bounds[0] <= 180 and -90 <= eff_bounds[1] <= 90:
                    minx, miny, maxx, maxy = eff_bounds
                    w_minx = minx + (xslice.start / w) * (maxx - minx)
                    w_maxx = minx + (xslice.stop / w) * (maxx - minx)
                    w_miny = maxy - (yslice.stop / h) * (maxy - miny)
                    w_maxy = maxy - (yslice.start / h) * (maxy - miny)
                else:
                    w_minx, w_maxx = 72.01, 72.03
                    w_miny, w_maxy = 22.75, 22.77

                w_cx = (w_minx + w_maxx) / 2.0
                w_cy = (w_miny + w_maxy) / 2.0
                area_m2 = pixel_count * 100.0

                det_id = f"det_{kind}_{i}"
                detections.append({
                    "id": det_id,
                    "type": f"{kind}_cluster",
                    "bbox_wgs84": [round(w_minx, 6), round(w_miny, 6), round(w_maxx, 6), round(w_maxy, 6)],
                    "centroid_wgs84": [round(w_cx, 6), round(w_cy, 6)],
                    "area_m2": area_m2,
                    "confidence": 0.85,
                    "image_position": "center",
                })
        except Exception:
            pass

    return detections, features


def _save_mask_artifacts(
    mask: np.ndarray,
    meta: dict[str, Any],
    job_id: str | None,
    kind: str = "water",
) -> dict[str, str]:
    """Save georeferenced raster mask (GeoTIFF) and RGBA preview (PNG)."""
    if not job_id:
        return {}

    job_processed = settings.full_job_storage_dir / str(job_id) / "processed"
    job_processed.mkdir(parents=True, exist_ok=True)
    mask_tif = job_processed / f"{kind}_mask.tif"
    mask_png = job_processed / f"{kind}_mask.png"

    cfg = CLASS_METADATA.get(kind.lower(), {"rgba": [94, 143, 138, 180]})

    try:
        from PIL import Image

        h, w = mask.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        is_pos = mask > 0
        rgba[is_pos] = cfg["rgba"]
        Image.fromarray(rgba, mode="RGBA").save(mask_png)
    except Exception:
        pass

    if meta.get("is_geotiff") and meta.get("transform") is not None:
        try:
            import rasterio

            with rasterio.open(
                mask_tif,
                "w",
                driver="GTiff",
                height=meta["height"],
                width=meta["width"],
                count=1,
                dtype=rasterio.uint8,
                crs=meta.get("crs"),
                transform=meta.get("transform"),
                nodata=0,
            ) as dst:
                dst.write((mask > 0).astype(np.uint8), 1)
        except Exception:
            pass

    return {
        "mask_tif": str(mask_tif) if mask_tif.is_file() else "",
        "mask_png": str(mask_png) if mask_png.is_file() else "",
    }


def _prose(
    fractions: dict[str, float],
    focus: str,
    backend: str,
    flood_share: float | None,
    tags: list[dict[str, Any]],
) -> str:
    ranked = sorted(fractions.items(), key=lambda kv: kv[1], reverse=True)
    top = [f"{name.replace('_', ' ')} {pct * 100:.0f}%" for name, pct in ranked if pct >= 0.04][:6]
    veg = sum(fractions[c] for c in VEG)
    water = fractions["water"] + fractions["flooded_vegetation"]
    built = fractions["built"]
    
    if backend == "dynamic_world":
        pixel_src = "Dynamic World 9-class"
    elif backend == "optical_multispectral_ndwi":
        pixel_src = "Optical Multispectral (NDWI / NDVI)"
    elif backend.startswith("prithvi"):
        pixel_src = "Prithvi flood + Optical"
    else:
        pixel_src = "Optical RGB spectral heuristic"

    lines = [
        f"**Land Cover Classification** ({pixel_src})",
        ", ".join(top) if top else "no dominant class.",
    ]
    if focus == "flood":
        share = flood_share if flood_share is not None else water
        lines.append(f"Flood / standing-water fraction **{share * 100:.1f}%**.")
    elif focus == "water":
        lines.append(f"Open water + flooded vegetation **{water * 100:.1f}%** of the scene.")
    elif focus == "vegetation":
        lines.append(f"Vegetated classes together **{veg * 100:.0f}%**.")
    elif focus == "built":
        lines.append(f"Built-up area **{built * 100:.0f}%**.")
    else:
        lines.append(f"Built-up {built * 100:.0f}% · bare {fractions.get('bare', 0.0) * 100:.0f}% · vegetation {veg * 100:.0f}% · water {water * 100:.1f}%.")

    if backend == "optical_rgb_heuristic":
        lines.append("*Note: RGB spectral heuristic provides coarse visible surface estimates; NIR band was unavailable.*")

    if tags:
        tag_line = " · ".join(t["name"] for t in tags)
        lines.append("")
        lines.append(
            "**Scene tags** (BigEarthNet-19 taxonomy mapped from land-cover fractions)"
        )
        lines.append(tag_line)
    return "\n\n".join(lines)


def _try_dynamic_world(path: str, rgb: np.ndarray) -> tuple[np.ndarray | None, str]:
    """Run Dynamic World only on 9-band Sentinel-2. RGB previews stay spectral."""
    p = Path(path)
    stack9 = _s2_nine_from_raster(p) if p.suffix.lower() in {".tif", ".tiff"} else None
    if stack9 is None:
        return None, "spectral_fallback"
    weights = Path(settings.BASE_DIR) / settings.WEIGHTS_DIR / "dynamic_world.pt"
    if not weights.is_file():
        return None, "spectral_fallback"
    try:
        from backend.agents.tools.dynamic_world_infer import run_dynamic_world

        labels = run_dynamic_world(stack9, weights)
        if labels.shape != rgb.shape[:2]:
            from PIL import Image as _Im

            lab = _Im.fromarray(labels, mode="L").resize((rgb.shape[1], rgb.shape[0]), _Im.NEAREST)
            labels = np.asarray(lab, dtype=np.uint8)
        return labels, "dynamic_world"
    except Exception:
        return None, "spectral_fallback"


def _try_prithvi_flood(path: str) -> np.ndarray | None:
    w = settings.PRITHVI_FLOOD_WEIGHTS_PATH
    if not w:
        return None
    wp = Path(w)
    if not wp.is_file() and not wp.is_dir():
        return None
    try:
        from backend.agents.tools.prithvi_flood import run_prithvi_flood

        return run_prithvi_flood(path, wp)
    except Exception:
        return None


class LulcMapTool(BaseTool):
    """Pixel 9-class map + BigEarthNet-19 scene tags (taxonomy, not a BEN net)."""

    tool_id = "lulc_map"

    def validate(self, params: Mapping[str, Any]) -> None:
        refs = params.get("image_refs")
        if not isinstance(refs, list) or not refs:
            raise ValueError("lulc_map requires image_refs")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        refs = [str(r) for r in params["image_refs"]]
        query = str(params.get("question") or params.get("text") or "")
        bounds = params.get("bounds")
        job_id = params.get("job_id")
        if isinstance(bounds, (list, tuple)) and len(bounds) == 4:
            bbox = [float(x) for x in bounds]
        else:
            bbox = None
        path = next((r for r in refs if Path(r).is_file()), refs[0])
        rgb, meta, bands = _read_raster_with_meta(path)
        dw, dw_backend = _try_dynamic_world(path, rgb)
        if dw is not None:
            labels = dw
            backend = "dynamic_world"
        else:
            labels, backend = _classify_optical_scene(rgb, bands, meta)

        fractions = _fractions(labels)
        focus = _focus(query)
        flood_share: float | None = None
        flood_mask = None
        if focus == "flood":
            flood_mask = _try_prithvi_flood(path)
            if flood_mask is not None:
                backend = "prithvi_flood+dynamic_world" if dw is not None else "prithvi_flood"
                flood_share = float(flood_mask.mean())
            else:
                flood_mask = (labels == 0) | (labels == 3)
                flood_share = float(flood_mask.mean())

        # Determine target class from query or params
        from backend.agents.query_plan import normalize_target_class, TargetClass

        target_class_raw = params.get("target_class")
        if target_class_raw:
            if isinstance(target_class_raw, TargetClass):
                target_class = target_class_raw
            elif str(target_class_raw).upper() in TargetClass.__members__:
                target_class = TargetClass[str(target_class_raw).upper()]
            else:
                target_class = normalize_target_class(str(target_class_raw))
        else:
            target_class = normalize_target_class(query)

        is_highlight_requested = any(w in query.lower() for w in [
            "highlight", "segment", "isolate", "outline", "where is", "locate", "mask", "show on map", "visualize"
        ])

        target_kind = None
        target_mask = None
        target_share = 0.0

        if target_class == TargetClass.BUILT:
            target_kind = "built"
            target_mask = (labels == 6)
            target_share = fractions.get("built", 0.0)
        elif target_class == TargetClass.WATER:
            target_kind = "water"
            target_mask = (labels == 0) | (labels == 3)
            target_share = fractions.get("water", 0.0) + fractions.get("flooded_vegetation", 0.0)
        elif target_class == TargetClass.FLOOD:
            target_kind = "flood"
            target_mask = flood_mask if flood_mask is not None else ((labels == 0) | (labels == 3))
            target_share = flood_share if flood_share is not None else (fractions.get("water", 0.0) + fractions.get("flooded_vegetation", 0.0))
        elif target_class == TargetClass.TREES:
            target_kind = "trees"
            target_mask = (labels == 1)
            target_share = fractions.get("trees", 0.0)
        elif target_class == TargetClass.GRASS:
            target_kind = "grass"
            target_mask = (labels == 2)
            target_share = fractions.get("grass", 0.0)
        elif target_class == TargetClass.BARE:
            target_kind = "bare"
            if "land" in query.lower() or "ground" in query.lower() or "terrain" in query.lower():
                target_mask = ~((labels == 0) | (labels == 3))
                target_share = 1.0 - (fractions.get("water", 0.0) + fractions.get("flooded_vegetation", 0.0))
            else:
                target_mask = (labels == 7)
                target_share = fractions.get("bare", 0.0)
        elif target_class == TargetClass.VEGETATION:
            target_kind = "vegetation"
            target_mask = (labels == 1) | (labels == 2) | (labels == 4) | (labels == 5)
            target_share = sum(fractions.get(k, 0.0) for k in ["trees", "grass", "crops", "shrub_and_scrub"])
        elif is_highlight_requested:
            # If highlight requested without specific class, select dominant class or water
            if fractions.get("water", 0.0) > 0.05:
                target_kind = "water"
                target_mask = (labels == 0) | (labels == 3)
                target_share = fractions.get("water", 0.0) + fractions.get("flooded_vegetation", 0.0)
            elif fractions.get("built", 0.0) > 0.15:
                target_kind = "built"
                target_mask = (labels == 6)
                target_share = fractions.get("built", 0.0)
            else:
                target_kind = "trees"
                target_mask = (labels == 1)
                target_share = fractions.get("trees", 0.0)

        overlays: list[dict[str, Any]] = []
        mask_artifacts: dict[str, str] = {}
        detections: list[dict[str, Any]] = []

        is_object_query = any(w in query.lower() for w in [
            "object", "objects", "building", "buildings", "structure", "structures",
            "cluster", "clusters", "detect", "locate"
        ])

        if target_mask is not None and target_mask.sum() > 0:
            if is_highlight_requested:
                overlays.extend(_mask_to_real_geojson(target_mask, meta, bbox, target_kind, share=target_share))
                mask_artifacts = _save_mask_artifacts(target_mask, meta, str(job_id) if job_id else None, target_kind)

            if is_object_query or target_class == TargetClass.BUILT:
                det_list, det_features = _extract_object_detections(target_mask, meta, bbox, kind=target_kind or "building")
                detections.extend(det_list)
                if not overlays and det_features:
                    overlays.extend(det_features)

        from backend.agents.tools.bigearthnet import scene_tags, try_resnet_tags
        from backend.services.mask_validator import validate_and_build_analysis_object

        tags = try_resnet_tags(path) or scene_tags(fractions, coastal=_is_coastal(query, path))
        answer = _prose(fractions, focus, backend, flood_share, tags)

        analysis_objects = []
        for i, ov in enumerate(overlays):
            geom = ov.get("geometry")
            props = ov.get("properties", {})
            obj = validate_and_build_analysis_object(
                object_id=f"obj_lulc_{target_kind or 'feat'}_{i+1}",
                target=target_kind or "land_cover_region",
                modality="OPTICAL",
                sensor="Sentinel-2",
                scene_id=str(job_id) if job_id else None,
                asset_id=None,
                geometry=geom,
                label=f"{str(target_kind).replace('_', ' ').capitalize()} Feature {i+1}",
                confidence=float(props.get("confidence", target_share or 0.85)),
                source_model="DynamicWorld" if backend.startswith("dynamic_world") else "Spectral-9Class-LULC",
                provenance={"tool": "lulc_map", "focus": focus, "target_kind": target_kind},
                scene_bounds_wgs84=meta.get("bounds_wgs84") or bbox,
                properties=props,
            )
            if obj:
                analysis_objects.append(obj.model_dump())

        return {
            "tool_id": "lulc_map",
            "modality": "OPTICAL",
            "backend": backend,
            "focus": focus,
            "target_class": target_class.value if target_class else None,
            "target_kind": target_kind,
            "fractions": fractions,
            "flood_share": flood_share,
            "scene_tags": tags,
            "answer": answer,
            "detections": detections,
            "analysis_objects": analysis_objects,
            "overlays": {"type": "FeatureCollection", "features": overlays},
            "spatial_outputs": {
                f"{target_kind or 'spatial'}_mask_tif": mask_artifacts.get("mask_tif", ""),
                f"{target_kind or 'spatial'}_mask_png": mask_artifacts.get("mask_png", ""),
                "target_class": target_class.value if target_class else None,
                "target_kind": target_kind,
                "bounds": meta.get("bounds_wgs84") or bbox,
                "crs": str(meta.get("crs") or "EPSG:4326"),
                "has_spatial_mask": len(overlays) > 0,
            },
        }

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        if not isinstance(result, dict):
            return "Land-cover map produced."
        return f"lulc_map via {result.get('backend')} focus={result.get('focus')}"

    def execute(self, params: Mapping[str, Any]):
        result = super().execute(params)
        payload = result.result
        if isinstance(payload, dict) and result.status == "success":
            fr = payload.get("fractions") or {}
            conf = max(fr.values()) if fr else None
            feats = (payload.get("overlays") or {}).get("features") or []
            return result.model_copy(update={"confidence": conf, "spatial_refs": list(feats)})
        return result

