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


def _open_rgb(path: str) -> np.ndarray:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    suffix = p.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        try:
            import rasterio

            with rasterio.open(p) as src:
                count = min(src.count, 4)
                arr = src.read(list(range(1, count + 1)))
            arr = np.transpose(arr, (1, 2, 0)).astype(np.float32)
            return _rgb_from_stack(arr)
        except Exception:
            pass
    img = Image.open(p).convert("RGB")
    max_side = 512
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    return np.asarray(img, dtype=np.float32) / 255.0


def _spectral_labels(rgb: np.ndarray) -> np.ndarray:
    """9-class map from RGB (and optional 4th band already folded into RGB)."""
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    bright = (r + g + b) / 3.0
    greenness = 2.0 * g - r - b
    ndwi = (g - r) / (g + r + 1e-6)
    labels = np.full(r.shape, 8, dtype=np.uint8)  # snow default only if very bright+blue
    labels[:, :] = 7  # bare
    veg = greenness > 0.08
    labels[veg & (greenness > 0.28)] = 1  # trees
    labels[veg & (greenness <= 0.28) & (greenness > 0.16)] = 4  # crops
    labels[veg & (greenness <= 0.16)] = 2  # grass
    shrub = veg & (bright < 0.28) & (greenness < 0.14)
    labels[shrub] = 5
    # (G-R) NDWI is high on vegetation too — require low greenness for water.
    water = ((ndwi > 0.12) & (greenness < 0.06)) | ((b > r + 0.08) & (b >= g) & (bright < 0.5) & (greenness < 0.06))
    # Turbid / green-grey water (Cartosat reservoirs): R≈G > B, mid brightness.
    turbid = (np.abs(r - g) < 0.04) & ((r - b) > 0.04) & (bright > 0.42) & (bright < 0.66) & (greenness < 0.14)
    water = water | turbid
    labels[water] = 0
    flooded = water & veg
    labels[flooded] = 3
    built = (bright > 0.42) & (greenness < 0.04) & (np.abs(r - g) < 0.08) & ~water
    labels[built] = 6
    snow = (bright > 0.78) & (b > 0.7) & ~veg
    labels[snow] = 8
    return labels


def _fractions(labels: np.ndarray) -> dict[str, float]:
    n = labels.size
    out: dict[str, float] = {}
    for i, name in enumerate(DW_CLASSES):
        out[name] = float(np.count_nonzero(labels == i)) / n if n else 0.0
    return out


def _mask_to_boxes(mask: np.ndarray, max_boxes: int = 1) -> list[list[float]]:
    """One axis-aligned box around the mask, in normalized image coords [x0,y0,x1,y1]."""
    h, w = mask.shape
    ys, xs = np.where(mask)
    if ys.size == 0:
        return []
    y0, y1 = float(ys.min()) / h, float(ys.max() + 1) / h
    x0, x1 = float(xs.min()) / w, float(xs.max() + 1) / w
    return [[round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]]


def _boxes_to_geojson(boxes: list[list[float]], bounds: list[float] | None, kind: str) -> list[dict[str, Any]]:
    feats: list[dict[str, Any]] = []
    if bounds and len(bounds) == 4:
        west, south, east, north = bounds
        dx, dy = east - west, north - south
    else:
        west, south, north = 0.0, 0.0, 1.0
        dx = dy = 1.0
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        # image y grows down; geographic y grows north
        minx, maxx = west + dx * x0, west + dx * x1
        maxy, miny = north - dy * y0, north - dy * y1
        ring = [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]
        feats.append(
            {
                "type": "Feature",
                "properties": {
                    "id": f"{kind}-{i}",
                    "kind": "change" if kind in ("water", "flood") else "uncertain",
                    "class": kind,
                    "label": kind.replace("_", " "),
                },
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    return feats


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
    pixel_src = "Dynamic World 9-class" if backend.startswith("dynamic_world") else "RGB spectral fallback (not Dynamic World)"
    if backend.startswith("prithvi"):
        pixel_src = "Prithvi flood + " + pixel_src
    lines = [
        f"**Pixel map** ({pixel_src})",
        ", ".join(top) if top else "no dominant class.",
    ]
    if focus == "flood":
        share = flood_share if flood_share is not None else water
        lines.append(f"Flood / standing-water share **{share * 100:.0f}%**.")
    elif focus == "water":
        lines.append(f"Open water + flooded vegetation **{water * 100:.0f}%** of the frame.")
    elif focus == "vegetation":
        lines.append(f"Vegetated classes together **{veg * 100:.0f}%**.")
    elif focus == "built":
        lines.append(f"Built-up **{built * 100:.0f}%**.")
    else:
        lines.append(f"Water {water * 100:.0f}% · vegetation {veg * 100:.0f}% · built {built * 100:.0f}%.")
    if tags:
        tag_line = " · ".join(t["name"] for t in tags)
        lines.append("")
        lines.append(
            "**Scene tags** (BigEarthNet-19 names mapped from the 9-class fractions — "
            "Dynamic World is not trained on BigEarthNet)"
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
        if isinstance(bounds, (list, tuple)) and len(bounds) == 4:
            bbox = [float(x) for x in bounds]
        else:
            bbox = None
        path = next((r for r in refs if Path(r).is_file()), refs[0])
        rgb = _open_rgb(path)
        dw, backend = _try_dynamic_world(path, rgb)
        labels = dw if dw is not None else _spectral_labels(rgb)
        if dw is None:
            backend = "spectral_fallback"
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
        water_mask = labels == 0
        veg_mask = np.isin(labels, [1, 2, 3, 4, 5])
        built_mask = labels == 6
        overlays: list[dict[str, Any]] = []
        if focus in ("water", "flood", "land_cover"):
            overlays.extend(_boxes_to_geojson(_mask_to_boxes(flood_mask if flood_mask is not None else water_mask), bbox, "flood" if focus == "flood" else "water"))
        if focus in ("vegetation", "land_cover"):
            overlays.extend(_boxes_to_geojson(_mask_to_boxes(veg_mask), bbox, "vegetation"))
        if focus in ("built", "land_cover"):
            overlays.extend(_boxes_to_geojson(_mask_to_boxes(built_mask), bbox, "built"))
        from backend.agents.tools.bigearthnet import scene_tags, try_resnet_tags

        tags = try_resnet_tags(path) or scene_tags(fractions, coastal=_is_coastal(query, path))
        answer = _prose(fractions, focus, backend, flood_share, tags)
        return {
            "backend": backend,
            "focus": focus,
            "fractions": fractions,
            "flood_share": flood_share,
            "scene_tags": tags,
            "answer": answer,
            "overlays": {"type": "FeatureCollection", "features": overlays},
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
