"""Dynamic World (Brown et al. 2022) — Apache-2.0 PyTorch port.

Architecture follows calebrob6/dynamic_world_pytorch (Apache-2.0), converted
from Google's official SavedModel. Input is 9 Sentinel-2 L1C bands in order
B2, B3, B4, B5, B6, B7, B8, B11, B12, already log-percentile normalized.

Do not feed RGB Cartosat previews into this model.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

SENTINEL2_BANDS = ("B2", "B3", "B4", "B5", "B6", "B7", "B8", "B11", "B12")

# Per-band log-percentile stats from the official Dynamic World runner.
_NORM_PERCENTILES = np.array(
    [
        [1.7417268007636313, 2.023298706048351],
        [1.7261204997060209, 2.038905204308012],
        [1.6798346251414997, 2.179592821212937],
        [1.7734969472909623, 2.2890068333026603],
        [2.289154079164943, 2.6171674549378166],
        [2.382939712192371, 2.773418590375327],
        [2.3828939530384052, 2.7578332604178284],
        [2.1952484264967844, 2.789092484314204],
        [1.554812948247501, 2.4140534947492487],
    ],
    dtype=np.float32,
)

_MODEL: "DynamicWorld | None" = None
_WEIGHTS: Path | None = None


class _ConvBNMish(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, kernel_size: int = 1, padding: int = 0, groups: int = 1):
        super().__init__()
        self.conv = nn.Conv2d(in_ch, out_ch, kernel_size, padding=padding, groups=groups, bias=True)
        self.bn = nn.BatchNorm2d(out_ch, eps=1e-3, momentum=0.01)
        self.act = nn.Mish()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.bn(self.conv(x)))


class _DWMish(nn.Module):
    def __init__(self, ch: int):
        super().__init__()
        self.dw = nn.Conv2d(ch, ch, 3, padding=1, groups=ch, bias=True)
        self.bn = nn.BatchNorm2d(ch, eps=1e-3, momentum=0.01)
        self.act = nn.Mish()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.bn(self.dw(x)))


class _ResidualBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.pw1 = _ConvBNMish(in_ch, out_ch)
        self.dw1 = _DWMish(out_ch)
        self.pw2 = _ConvBNMish(out_ch, out_ch)
        self.dw2 = _DWMish(out_ch)
        self.pw3 = _ConvBNMish(out_ch, out_ch)
        self.dw3 = _DWMish(out_ch)
        self.shortcut = _ConvBNMish(in_ch, out_ch)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        main = self.dw3(self.pw3(self.dw2(self.pw2(self.dw1(self.pw1(x))))))
        return main + self.shortcut(x)


class _SkipBranch(nn.Module):
    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.pw = _ConvBNMish(in_ch, out_ch)
        self.dw = _DWMish(out_ch)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dw(self.pw(x))


class DynamicWorld(nn.Module):
    """Google Dynamic World forward model (m=1.5, b=2, base=32)."""

    def __init__(self, in_ch: int = 9, num_classes: int = 9):
        super().__init__()
        stem_c, skip_c, mid_c, high_c = 64, 48, 96, 144
        self.stem = _ConvBNMish(in_ch, stem_c, kernel_size=3, padding=1)
        self.skip = _SkipBranch(stem_c, skip_c)
        self.block1 = _ResidualBlock(stem_c, mid_c)
        self.block2 = _ResidualBlock(mid_c, high_c)
        self.block3 = _ResidualBlock(high_c + skip_c, high_c)
        self.classifier = nn.Conv2d(high_c, num_classes, kernel_size=1, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h, w = x.shape[-2:]
        x = self.stem(x)
        down = (h // 2, w // 2)
        x_down = F.interpolate(x, size=down, mode="bilinear", align_corners=False, antialias=True)
        skip_out = self.skip(x_down)
        b2 = self.block2(self.block1(x_down))
        b3 = self.block3(torch.cat([b2, skip_out], dim=1))
        up = F.interpolate(b3, size=(h, w), mode="bilinear", align_corners=False)
        return self.classifier(F.normalize(up, p=2, dim=1, eps=1e-12))


def normalize_sentinel2(stack: np.ndarray) -> np.ndarray:
    """``stack`` is (9, H, W) raw L1C-like reflectance / DN."""
    x = np.log(stack * 0.005 + 1.0)
    x = (x - _NORM_PERCENTILES[:, 0, None, None]) / _NORM_PERCENTILES[:, 1, None, None]
    x = np.exp(x * 5.0 - 1.0)
    return (x / (x + 1.0)).astype(np.float32)


def _load(weights: Path) -> DynamicWorld:
    global _MODEL, _WEIGHTS
    if _MODEL is not None and _WEIGHTS == weights:
        return _MODEL
    model = DynamicWorld()
    state = torch.load(weights, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    _MODEL = model
    _WEIGHTS = weights
    return model


def run_dynamic_world(stack9: np.ndarray, weights: Path) -> np.ndarray:
    """``stack9`` is (9, H, W) un-normalized S2. Returns (H, W) uint8 labels."""
    if stack9.shape[0] != 9:
        raise ValueError(f"Dynamic World expects 9 bands, got {stack9.shape}")
    h, w = stack9.shape[1], stack9.shape[2]
    # Keep the net small: cap the long side.
    max_side = 512
    work = stack9
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        nh, nw = max(4, int(h * scale)), max(4, int(w * scale))
        t = torch.from_numpy(stack9).unsqueeze(0)
        work = F.interpolate(t, size=(nh, nw), mode="bilinear", align_corners=False)[0].numpy()
    normed = normalize_sentinel2(work)
    model = _load(weights)
    x = torch.from_numpy(normed).unsqueeze(0)
    with torch.inference_mode():
        labels = model(x).argmax(dim=1)[0].cpu().numpy().astype(np.uint8)
    if labels.shape != (h, w):
        labels = F.interpolate(
            torch.from_numpy(labels[None, None].astype(np.float32)),
            size=(h, w),
            mode="nearest",
        )[0, 0].numpy().astype(np.uint8)
    return labels
