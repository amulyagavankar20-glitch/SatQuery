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
                        meta["bounds_wgs84"] = list(transform_bounds(src.crs, "EPSG:4326", *src.bounds))
                    else:
                        meta["bounds_wgs84"] = list(src.bounds)
                except Exception:
                    meta["bounds_wgs84"] = list(src.bounds)

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

    img = Image.open(p).convert("RGB")
    max_side = 512
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    meta["width"], meta["height"] = img.size
    meta["band_count"] = 3
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
        blue = bands.get("blue", rgb[:, :, 2])
        green = bands["green"]
        red = bands["red"]
        nir = bands["nir"]

        ndwi = (green - nir) / (green + nir + 1e-6)
        ndvi = (nir - red) / (nir + red + 1e-6)
        bright = (red + green + blue) / 3.0

        labels = np.full(red.shape, 7, dtype=np.uint8)  # default: bare / open terrain

        # Water: NDWI > 0, NIR strongly absorbed (< 0.12 and < Green), NDVI < 0.05
        raw_water = (ndwi > 0.0) & (nir < 0.12) & (nir < green) & (ndvi < 0.05)
        # Connected component cleanup to remove isolated 1-2 pixel noise
        try:
            from scipy.ndimage import label as _scipy_label

            labeled_w, num_w = _scipy_label(raw_water)
            water = np.zeros_like(raw_water)
            for i in range(1, num_w + 1):
                if np.count_nonzero(labeled_w == i) >= 10:
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
        built = (bright > 0.10) & (ndvi < 0.18) & (ndwi < -0.05) & ~water
        labels[built] = 6

        return labels, "optical_multispectral_ndwi"

    # Case 2: 3-band Visible RGB only (NIR unavailable)
    red = bands.get("red", rgb[:, :, 0])
    green = bands.get("green", rgb[:, :, 1])
    blue = bands.get("blue", rgb[:, :, 2])

    bright = (red + green + blue) / 3.0
    greenness = 2.0 * green - red - blue
    ndti = (blue - red) / (blue + red + 1e-6)

    labels = np.full(red.shape, 7, dtype=np.uint8)  # default: bare / open

    # Visible water index: strong blue dominance, low brightness, low greenness
    raw_water = (ndti > 0.15) & (blue > green) & (green >= red) & (bright < 0.35) & (greenness < 0.04)
    try:
        from scipy.ndimage import label as _scipy_label

        labeled_w, num_w = _scipy_label(raw_water)
        water = np.zeros_like(raw_water)
        for i in range(1, num_w + 1):
            if np.count_nonzero(labeled_w == i) >= 10:
                water[labeled_w == i] = True
    except Exception:
        water = raw_water

    labels[water] = 0

    veg = (greenness > 0.08) & ~water
    labels[veg & (greenness > 0.28)] = 1  # trees
    labels[veg & (greenness <= 0.28) & (greenness > 0.16)] = 4  # crops
    labels[veg & (greenness <= 0.16)] = 2  # grass

    built = (bright > 0.38) & (greenness < 0.05) & (np.abs(red - green) < 0.08) & ~water
    labels[built] = 6

    return labels, "optical_rgb_heuristic"


def _fractions(labels: np.ndarray) -> dict[str, float]:
    n = labels.size
    out: dict[str, float] = {}
    for i, name in enumerate(DW_CLASSES):
        out[name] = float(np.count_nonzero(labels == i)) / n if n else 0.0
    return out


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

    # Method A: If we have real GeoTIFF affine transform and CRS
    if meta.get("is_geotiff") and meta.get("transform") is not None:
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
                            "kind": "water_mask" if kind in ("water", "flood") else "mask",
                            "class": kind,
                            "fill": "#00a8ff" if kind == "water" else "#5E8F8A",
                            "stroke": "#00e5ff" if kind == "water" else "#5E8F8A",
                            "label": f"{kind.replace('_', ' ').title()} Feature ({pct_str} of AOI)",
                        },
                        "geometry": wgs_geom,
                    }
                ]
        except Exception:
            pass

    # Method B: Vectorize using effective bounding box
    eff_bounds = meta.get("bounds_wgs84") or bounds
    if eff_bounds and len(eff_bounds) == 4:
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
                            "kind": "water_mask" if kind in ("water", "flood") else "mask",
                            "class": kind,
                            "fill": "#00a8ff" if kind == "water" else "#5E8F8A",
                            "stroke": "#00e5ff" if kind == "water" else "#5E8F8A",
                            "label": f"{kind.replace('_', ' ').title()} Feature ({pct_str} of AOI)",
                        },
                        "geometry": mapping(union),
                    }
                ]
        except Exception:
            pass

    return []


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

    try:
        from PIL import Image

        h, w = mask.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        is_pos = mask > 0
        rgba[is_pos] = [0, 168, 255, 180] if kind == "water" else [94, 143, 138, 180]
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
        water_mask = (labels == 0) | (labels == 3)
        overlays: list[dict[str, Any]] = []
        mask_artifacts: dict[str, str] = {}

        # Generate spatial mask overlay whenever water/flood is present or requested
        target_mask = flood_mask if flood_mask is not None else water_mask
        target_kind = "flood" if focus == "flood" else "water"
        water_share = flood_share if flood_share is not None else (fractions.get("water", 0.0) + fractions.get("flooded_vegetation", 0.0))

        if target_mask.sum() > 0:
            overlays.extend(_mask_to_real_geojson(target_mask, meta, bbox, target_kind, share=water_share))
            mask_artifacts = _save_mask_artifacts(target_mask, meta, str(job_id) if job_id else None, target_kind)

        from backend.agents.tools.bigearthnet import scene_tags, try_resnet_tags

        tags = try_resnet_tags(path) or scene_tags(fractions, coastal=_is_coastal(query, path))
        answer = _prose(fractions, focus, backend, flood_share, tags)
        return {
            "tool_id": "lulc_map",
            "modality": "OPTICAL",
            "backend": backend,
            "focus": focus,
            "fractions": fractions,
            "flood_share": flood_share,
            "scene_tags": tags,
            "answer": answer,
            "overlays": {"type": "FeatureCollection", "features": overlays},
            "spatial_outputs": {
                "water_mask_tif": mask_artifacts.get("mask_tif", ""),
                "water_mask_png": mask_artifacts.get("mask_png", ""),
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
