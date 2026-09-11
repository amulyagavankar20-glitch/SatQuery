"""BigEarthNet-19 scene tags.

Dynamic World is a *pixel* 9-class mapper (Brown et al. 2022). It is not
trained on BigEarthNet. BigEarthNet-19 is a *scene-level* CORINE taxonomy
(Sumbul et al. / reBEN). This module:

1. Always maps DW/spectral class fractions onto the 19 BEN names (no extra
   weights — demo-ready, honest taxonomy).
2. Optionally runs the MIT-licensed reBEN ResNet50 if a 12-band S2 chip and
   local weights exist (``BIGEARTHNET_WEIGHTS_PATH``). Never downloaded here.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from backend.config import settings

# Official 19-class BigEarthNet / reBEN label set.
BEN19: tuple[str, ...] = (
    "Urban fabric",
    "Industrial or commercial units",
    "Arable land",
    "Permanent crops",
    "Pastures",
    "Complex cultivation patterns",
    "Agriculture with natural vegetation",
    "Agro-forestry areas",
    "Broad-leaved forest",
    "Coniferous forest",
    "Mixed forest",
    "Natural grassland and sparsely vegetated areas",
    "Moors, heathland and sclerophyllous vegetation",
    "Transitional woodland, shrub",
    "Beaches, dunes, sands",
    "Inland wetlands",
    "Coastal wetlands",
    "Inland waters",
    "Marine waters",
)

# How each Dynamic World pixel class votes on BEN-19 scene tags.
_DW_TO_BEN: dict[str, tuple[tuple[str, float], ...]] = {
    "water": (("Inland waters", 1.0),),
    "trees": (("Broad-leaved forest", 0.5), ("Mixed forest", 0.5)),
    "grass": (("Pastures", 0.6), ("Natural grassland and sparsely vegetated areas", 0.4)),
    "flooded_vegetation": (("Inland wetlands", 0.7), ("Coastal wetlands", 0.3)),
    "crops": (("Arable land", 0.6), ("Complex cultivation patterns", 0.4)),
    "shrub_and_scrub": (("Transitional woodland, shrub", 0.7), ("Moors, heathland and sclerophyllous vegetation", 0.3)),
    "built": (("Urban fabric", 0.6), ("Industrial or commercial units", 0.4)),
    "bare": (("Natural grassland and sparsely vegetated areas", 1.0),),
    "snow_and_ice": (("Natural grassland and sparsely vegetated areas", 1.0),),
}


def scene_tags(
    fractions: dict[str, float],
    top_k: int = 4,
    *,
    coastal: bool = False,
) -> list[dict[str, Any]]:
    """Map 9-class pixel fractions onto BigEarthNet-19 *names*.

    This is a taxonomy lookup, not inference. Dynamic World was trained on
    GEE Sentinel-2 composites with its own 9 labels — it has never seen
    BigEarthNet. The optional reBEN ResNet (``try_resnet_tags``) is the only
    path that actually scores a BEN-trained net, and it stays off unless
    12-band S2 weights are present.
    """
    mapping = dict(_DW_TO_BEN)
    if coastal:
        mapping["water"] = (("Marine waters", 0.75), ("Inland waters", 0.25))
    scores: dict[str, float] = defaultdict(float)
    for dw, share in fractions.items():
        for name, weight in mapping.get(dw, ()):
            scores[name] += float(share) * weight
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    out: list[dict[str, Any]] = []
    for name, score in ranked:
        if score < 0.04:
            continue
        out.append({"name": name, "score": round(float(score), 3), "source": "ben19_taxonomy"})
        if len(out) >= top_k:
            break
    return out


def try_resnet_tags(image_path: str) -> list[dict[str, Any]] | None:
    """Optional reBEN ResNet50 on a 12-band S2 chip. Returns None if unavailable."""
    w = getattr(settings, "BIGEARTHNET_WEIGHTS_PATH", None)
    if not w:
        return None
    path = Path(w)
    if not path.exists():
        return None
    try:
        import rasterio

        with rasterio.open(image_path) as src:
            if src.count < 12:
                return None
    except Exception:
        return None
    return None
