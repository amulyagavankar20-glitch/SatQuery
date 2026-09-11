"""reBEN ResNet50 trained on Sentinel-1 BigEarthNet v2 (19 CORINE classes)."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from backend.agents.tools.bigearthnet import BEN19
from backend.config import settings
from src.logger import logging

HF_REPO = "BIFOLD-BigEarthNetv2-0/resnet50-s1-v0.2.0"
IMAGE_SIZE = 120


class BenS1Classifier:
    """Multilabel 19-class S1 scene classifier (reBEN ResNet50)."""

    _instance: BenS1Classifier | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.model: Any = None
        self.device = "cpu"
        self._failed = False
        self.weights_dir = self._resolve_dir()

    @classmethod
    def get_instance(cls) -> BenS1Classifier:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _resolve_dir(self) -> Path:
        root = Path(settings.BASE_DIR)
        configured = getattr(settings, "BEN_S1_WEIGHTS_PATH", None)
        if configured:
            path = Path(configured)
            return path if path.is_absolute() else root / path
        return root / "weights" / "specialists" / "ben_s1"

    def is_available(self) -> bool:
        d = self.weights_dir
        return d.is_dir() and ((d / "model.safetensors").is_file() or (d / "pytorch_model.bin").is_file())

    def load(self) -> None:
        if self.model is not None or self._failed:
            return
        if not self.is_available():
            raise FileNotFoundError(f"reBEN S1 weights not found at {self.weights_dir}")
        import timm
        from safetensors.torch import load_file

        model = timm.create_model("resnet50", in_chans=2, num_classes=19, pretrained=False)
        weights_path = self.weights_dir / "model.safetensors"
        if not weights_path.is_file():
            weights_path = self.weights_dir / "pytorch_model.bin"
        if weights_path.suffix == ".safetensors":
            state = load_file(str(weights_path))
        else:
            state = torch.load(weights_path, map_location="cpu", weights_only=True)
        mapped = _remap_state(state, model.state_dict())
        missing, unexpected = model.load_state_dict(mapped, strict=False)
        logging.info(
            f"[SAR] reBEN S1 ResNet50 loaded from {weights_path.name} "
            f"(missing={len(missing)} unexpected={len(unexpected)})"
        )
        model.eval()
        self.model = model

    def predict(self, stack2: np.ndarray, top_k: int = 6) -> list[dict[str, Any]]:
        """``stack2`` is (2, H, W) linear VV/VH. Returns ranked BEN-19 tags."""
        self.load()
        x = _prep_s1(stack2)
        with torch.inference_mode():
            logits = self.model(x)
            probs = torch.sigmoid(logits)[0].cpu().numpy()
        ranked = sorted(enumerate(probs), key=lambda kv: kv[1], reverse=True)
        out: list[dict[str, Any]] = []
        for idx, score in ranked:
            if float(score) < 0.12 and len(out) >= 2:
                continue
            name = BEN19[idx] if idx < len(BEN19) else str(idx)
            out.append({"name": name, "score": round(float(score), 3), "source": "reben_s1_resnet50"})
            if len(out) >= top_k:
                break
        return out


def _prep_s1(stack2: np.ndarray) -> torch.Tensor:
    if stack2.ndim != 3 or stack2.shape[0] < 2:
        raise ValueError("expected (2, H, W) VV/VH stack")
    db = 10.0 * np.log10(np.clip(stack2[:2].astype(np.float32), 1e-6, None))
    db = np.clip(db, -30.0, 5.0)
    norm = (db + 30.0) / 35.0
    t = torch.from_numpy(norm).unsqueeze(0)
    t = F.interpolate(t, size=(IMAGE_SIZE, IMAGE_SIZE), mode="bilinear", align_corners=False)
    return t


def _remap_state(raw: dict[str, torch.Tensor], target: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    """Map ConfigILM ``model.vision_encoder.*`` keys onto timm resnet50."""
    mapped: dict[str, torch.Tensor] = {}
    for key, value in raw.items():
        name = key
        if name.startswith("model.vision_encoder."):
            name = name[len("model.vision_encoder.") :]
        if name in target and tuple(value.shape) == tuple(target[name].shape):
            mapped[name] = value
    return mapped
