"""Build presentation GeoTIFFs + PNG previews for S2, S1, and BIT.

Writes to web/public/presentation/ so the console can serve the PNGs and
the GeoTIFFs can be uploaded by hand.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.io import MemoryFile

OUT = Path(__file__).resolve().parents[2] / "web" / "public" / "presentation"
SIZE = 256

# DW order: B2 B3 B4 B5 B6 B7 B8 B11 B12  (L1C-like DN)
SPEC = {
    "water": np.array([1800, 1600, 700, 500, 400, 350, 300, 180, 140], np.float32),
    "flood": np.array([1400, 1500, 900, 800, 1100, 1300, 1500, 700, 400], np.float32),
    "trees": np.array([250, 450, 300, 700, 1800, 2300, 2800, 1100, 550], np.float32),
    "grass": np.array([400, 650, 450, 800, 1400, 1700, 2000, 900, 500], np.float32),
    "crops": np.array([350, 550, 400, 750, 1600, 2000, 2400, 1000, 520], np.float32),
    "built": np.array([900, 950, 1000, 1050, 1100, 1150, 1200, 1800, 1600], np.float32),
    "bare": np.array([1100, 1050, 1000, 950, 900, 850, 800, 1200, 1100], np.float32),
    "sand": np.array([1600, 1400, 1200, 1000, 800, 700, 650, 900, 800], np.float32),
    "sea": np.array([1600, 1500, 600, 400, 300, 250, 200, 120, 90], np.float32),
}


def _noise(h: int, w: int, seed: int, scale: float = 8.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    small = max(4, int(h / scale)), max(4, int(w / scale))
    base = rng.uniform(-1, 1, small).astype(np.float32)
    return np.array(Image.fromarray(base, mode="F").resize((w, h), Image.BILINEAR))


def _label_to_s2(labels: np.ndarray, jitter: int = 7) -> np.ndarray:
    h, w = labels.shape
    stack = np.zeros((9, h, w), np.float32)
    rng = np.random.default_rng(int(labels.size) % 997)
    for name, vec in SPEC.items():
        mask = labels == name
        if not np.any(mask):
            continue
        n = int(mask.sum())
        noise = rng.normal(0, 40, size=(9, n)).astype(np.float32)
        stack[:, mask] = vec[:, None] + noise
    stack *= 1.0 + 0.04 * _noise(h, w, jitter)
    return np.clip(stack, 50, 6000)


def _s2_rgb(stack: np.ndarray) -> np.ndarray:
    rgb = np.stack([stack[2], stack[1], stack[0]], axis=-1)  # B4 B3 B2
    lo, hi = np.percentile(rgb, (2, 98))
    rgb = np.clip((rgb - lo) / max(hi - lo, 1), 0, 1)
    return (rgb * 255).astype(np.uint8)


def _write_tif(path: Path, data: np.ndarray, bounds: tuple, *, datetime: str | None, sensor: str, extra: dict | None = None) -> None:
    h, w = data.shape[-2], data.shape[-1]
    count = 1 if data.ndim == 2 else data.shape[0]
    profile = {
        "driver": "GTiff",
        "height": h,
        "width": w,
        "count": count,
        "dtype": data.dtype,
        "crs": "EPSG:4326",
        "transform": from_bounds(*bounds, w, h),
        "compress": "lzw",
    }
    west, south, east, north = bounds
    with MemoryFile() as mem:
        with mem.open(**profile) as dst:
            if data.ndim == 2:
                dst.write(data, 1)
            else:
                dst.write(data)
            tags = {"SENSOR": sensor}
            if datetime:
                tags["TIFFTAG_DATETIME"] = datetime
            if extra:
                tags.update(extra)
            dst.update_tags(**tags)
        path.write_bytes(mem.read())


def _write_png(path: Path, rgb: np.ndarray) -> None:
    Image.fromarray(rgb, mode="RGB").save(path, optimize=True)


def _disk(cy: float, cx: float, ry: float, rx: float, yy: np.ndarray, xx: np.ndarray) -> np.ndarray:
    return ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1


def _grid() -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    return yy.astype(np.float32), xx.astype(np.float32)


def scene_s2_water() -> np.ndarray:
    yy, xx = _grid()
    labels = np.full((SIZE, SIZE), "crops", dtype=object)
    labels[_disk(140, 90, 95, 80, yy, xx)] = "water"
    labels[_disk(70, 70, 28, 36, yy, xx)] = "flood"
    labels[(xx > 170) & (yy > 90) & (yy < 170) & (xx < 230)] = "built"
    labels[(xx > 200) & (yy > 180)] = "bare"
    n = _noise(SIZE, SIZE, 11)
    labels[(n > 0.45) & (labels == "crops")] = "grass"
    return labels


def scene_s2_vegetation() -> np.ndarray:
    yy, xx = _grid()
    labels = np.full((SIZE, SIZE), "trees", dtype=object)
    labels[xx > 140] = "crops"
    labels[(xx > 140) & (yy > 160)] = "grass"
    labels[(xx > 200) & (yy < 50)] = "bare"
    labels[_disk(200, 40, 22, 22, yy, xx)] = "water"
    n = _noise(SIZE, SIZE, 21)
    labels[(n > 0.35) & (labels == "trees")] = "grass"
    return labels


def scene_s2_flood() -> np.ndarray:
    yy, xx = _grid()
    labels = np.full((SIZE, SIZE), "crops", dtype=object)
    river = (np.abs(xx - 40 - 0.35 * yy) < 18) | (yy > 200)
    labels[river] = "water"
    floodplain = (xx < 120) & (yy > 80) & ~river
    labels[floodplain] = "flood"
    labels[(xx > 170) & (yy < 90)] = "built"
    labels[(xx > 190) & (yy > 140)] = "grass"
    return labels


def scene_s2_urban() -> np.ndarray:
    yy, xx = _grid()
    labels = np.full((SIZE, SIZE), "bare", dtype=object)
    labels[(xx % 28 < 18) & (yy % 22 < 14) & (xx > 40) & (yy > 30)] = "built"
    labels[yy > 210] = "water"
    labels[(xx < 40) & (yy < 180)] = "grass"
    return labels


def scene_s2_coast() -> np.ndarray:
    yy, xx = _grid()
    labels = np.full((SIZE, SIZE), "sea", dtype=object)
    labels[xx > 110 + 18 * np.sin(yy / 18)] = "sand"
    labels[xx > 150 + 10 * np.sin(yy / 22)] = "bare"
    labels[(xx > 170) & (yy > 60) & (yy < 200)] = "built"
    labels[(xx > 210) & (yy > 160)] = "grass"
    return labels


def _s1_from_labels(labels: np.ndarray, seed: int) -> np.ndarray:
    h, w = labels.shape
    rng = np.random.default_rng(seed)
    vv = np.full((h, w), 0.12, np.float32)
    vh = np.full((h, w), 0.04, np.float32)
    table = {
        "water": (0.012, 0.004),
        "sea": (0.010, 0.003),
        "flood": (0.025, 0.008),
        "built": (0.55, 0.18),
        "trees": (0.16, 0.09),
        "grass": (0.11, 0.05),
        "crops": (0.13, 0.06),
        "bare": (0.08, 0.03),
        "sand": (0.06, 0.02),
    }
    for name, (a, b) in table.items():
        m = labels == name
        n = int(m.sum())
        if not n:
            continue
        vv[m] = a * rng.uniform(0.7, 1.3, n)
        vh[m] = b * rng.uniform(0.7, 1.3, n)
    return np.stack([vv, vh], 0)


def _s1_rgb(stack: np.ndarray) -> np.ndarray:
    vv, vh = stack[0], stack[1]
    ratio = np.clip(vv / np.clip(vh, 1e-4, None), 0, 12) / 12
    rgb = np.stack(
        [
            _stretch(vv),
            _stretch(vh),
            (ratio * 255).astype(np.uint8),
        ],
        axis=-1,
    )
    return rgb


def _stretch(band: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(band, (2, 98))
    return (np.clip((band - lo) / max(hi - lo, 1e-6), 0, 1) * 255).astype(np.uint8)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    catalog: list[str] = [
        "SatQuery presentation scenes",
        "Upload the .tif into the console. PNGs are what you see.",
        "",
        f"{'file':<28} {'ask':<48} expect",
        "-" * 96,
    ]

    def add_s2(stem: str, labels: np.ndarray, bounds: tuple, ask: str, expect: str, sensor="Sentinel-2") -> None:
        stack = _label_to_s2(labels)
        _write_tif(OUT / f"{stem}.tif", stack, bounds, datetime="2023-11-14 00:00:00", sensor=sensor)
        _write_png(OUT / f"{stem}.png", _s2_rgb(stack))
        catalog.append(f"{stem}.tif{' ' * (28-len(stem)-4)} {ask:<48} {expect}")

    def add_s1(stem: str, labels: np.ndarray, bounds: tuple, ask: str, expect: str) -> None:
        stack = _s1_from_labels(labels, seed=sum(ord(c) for c in stem))
        _write_tif(
            OUT / f"{stem}.tif",
            stack.astype(np.float32),
            bounds,
            datetime="2024-07-03 00:00:00",
            sensor="Sentinel-1",
            extra={"POLARIZATION": "VV,VH"},
        )
        _write_png(OUT / f"{stem}.png", _s1_rgb(stack))
        catalog.append(f"{stem}.tif{' ' * (28-len(stem)-4)} {ask:<48} {expect}")

    inland = (72.04, 22.78, 72.16, 22.88)
    coast = (69.68, 22.80, 69.80, 22.90)
    floodb = (70.08, 22.40, 70.22, 22.51)

    add_s2("s2_water", scene_s2_water(), inland, "Highlight the water body", "DW water basin west, inland waters tag")
    add_s2("s2_vegetation", scene_s2_vegetation(), inland, "Describe land-cover and major objects", "trees/crops/grass fractions")
    add_s2("s2_flood", scene_s2_flood(), floodb, "Map the flood inundation", "water + flooded vegetation")
    add_s2("s2_urban", scene_s2_urban(), inland, "Where is the built-up area?", "built grid, urban fabric tag")
    add_s2("s2_coast", scene_s2_coast(), coast, "Describe land-cover and major objects", "marine water + port built")

    add_s1("s1_harbor", scene_s2_coast(), coast, "Describe this SAR scene", "bright built, dark water, reBEN S1 tags")
    add_s1("s1_flood", scene_s2_flood(), floodb, "What objects are visible in this SAR image?", "dark inundation, bright settlement")

    # BIT urban growth
    t1 = scene_s2_urban()
    t2 = t1.copy()
    yy, xx = _grid()
    t2[(xx > 80) & (xx < 160) & (yy > 40) & (yy < 120)] = "built"
    rgb1, rgb2 = _s2_rgb(_label_to_s2(t1, 3)), _s2_rgb(_label_to_s2(t2, 4))
    bgr1 = np.transpose(rgb1, (2, 0, 1))
    bgr2 = np.transpose(rgb2, (2, 0, 1))
    _write_tif(OUT / "bit_urban_t1.tif", bgr1, inland, datetime="2022-03-08 00:00:00", sensor="Cartosat-2S")
    _write_tif(OUT / "bit_urban_t2.tif", bgr2, inland, datetime="2024-02-21 00:00:00", sensor="Cartosat-2S")
    _write_png(OUT / "bit_urban_t1.png", rgb1)
    _write_png(OUT / "bit_urban_t2.png", rgb2)
    catalog.append(f"{'bit_urban_t1+t2.tif':<28} {'What changed between these two dates, and where?':<48} new built block, BIT polygons")

    # BIT water expansion (flood)
    w1 = scene_s2_water()
    w2 = w1.copy()
    w2[_disk(140, 90, 120, 110, * _grid())] = "water"
    w2[_disk(70, 70, 40, 50, * _grid())] = "flood"
    r1, r2 = _s2_rgb(_label_to_s2(w1, 5)), _s2_rgb(_label_to_s2(w2, 6))
    _write_tif(OUT / "bit_flood_t1.tif", np.transpose(r1, (2, 0, 1)), floodb, datetime="2023-07-01 00:00:00", sensor="Cartosat-2S")
    _write_tif(OUT / "bit_flood_t2.tif", np.transpose(r2, (2, 0, 1)), floodb, datetime="2023-07-18 00:00:00", sensor="Cartosat-2S")
    _write_png(OUT / "bit_flood_t1.png", r1)
    _write_png(OUT / "bit_flood_t2.png", r2)
    catalog.append(f"{'bit_flood_t1+t2.tif':<28} {'What changed between these two dates, and where?':<48} larger water, BIT change")

    (OUT / "INDEX.txt").write_text("\n".join(catalog) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("\n".join(catalog))


if __name__ == "__main__":
    main()
