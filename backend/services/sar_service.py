"""
SatQuery AI — Specialized SAR Model Service (SARChat-InternVL2.5-2B)

This service manages the lifecycle and inference for SARChat-InternVL2.5-2B,
a vision-language model specialized in Synthetic Aperture Radar (SAR) imagery.
"""

from __future__ import annotations

import os
import time
import threading
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
import rasterio
from PIL import Image
import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoTokenizer, AutoModel

from backend.config import settings
from src.logger import logging

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_transform(input_size: int = 448) -> T.Compose:
    """Builds standard ImageNet normalized transform for InternVL vision backbone."""
    return T.Compose([
        T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def load_sar_image_to_pil(image_source: str | Path | Image.Image) -> Image.Image:
    """
    Loads SAR image from a file path (GeoTIFF or standard image) or PIL Image.
    Preserves the exact preprocessing format verified during standalone testing.
    """
    if isinstance(image_source, Image.Image):
        return image_source.convert("RGB")

    path = Path(image_source)
    if not path.exists():
        raise FileNotFoundError(f"SAR image file not found at: {path}")

    # Check if GeoTIFF or standard image
    suffix = path.suffix.lower()
    if suffix in (".tif", ".tiff"):
        try:
            with rasterio.open(path) as src:
                arr = src.read()  # (bands, H, W)
                
            if arr.shape[0] >= 2:
                # Sentinel-1 dual-pol (VV, VH)
                vv = arr[0]
                vh = arr[1]
                vv_db = 10 * np.log10(np.clip(vv, 1e-5, None))
                vh_db = 10 * np.log10(np.clip(vh, 1e-5, None))

                vv_min, vv_max = np.percentile(vv_db, 2), np.percentile(vv_db, 98)
                vh_min, vh_max = np.percentile(vh_db, 2), np.percentile(vh_db, 98)

                r = np.clip((vv_db - vv_min) / (vv_max - vv_min + 1e-6), 0, 1)
                g = np.clip((vh_db - vh_min) / (vh_max - vh_min + 1e-6), 0, 1)
                b = np.clip(r / (g + 0.1), 0, 1)
                rgb = np.stack([r, g, b], axis=-1)
            else:
                # Single-band SAR
                v = arr[0]
                v_min, v_max = np.percentile(v, 2), np.percentile(v, 98)
                norm = np.clip((v - v_min) / (v_max - v_min + 1e-6), 0, 1)
                rgb = np.stack([norm, norm, norm], axis=-1)

            rgb = (rgb * 255).astype(np.uint8)
            return Image.fromarray(rgb)
        except Exception as e:
            logging.warning(f"[SAR] rasterio load failed ({e}), falling back to PIL.Image.open")
            return Image.open(path).convert("RGB")
    else:
        return Image.open(path).convert("RGB")


class SARChatService:
    """
    Thread-safe Singleton service for SARChat-InternVL2.5-2B.
    Loads the model once from SARCHAT_MODEL_PATH and reuses it across requests.
    """

    _instance: SARChatService | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.model_path = settings.SARCHAT_MODEL_PATH
        self.device = self._resolve_device()
        self.tokenizer: Any = None
        self.model: Any = None
        self.transform = build_transform(input_size=448)
        self._is_loaded = False
        self._load_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> SARChatService:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _resolve_device(self) -> str:
        if settings.SARCHAT_DEVICE:
            return settings.SARCHAT_DEVICE.lower()
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def is_available(self) -> bool:
        """Check if SARCHAT_MODEL_PATH exists on the filesystem."""
        if not self.model_path:
            return False
        return Path(self.model_path).exists()

    def load_model(self) -> None:
        """Loads tokenizer and model weights into memory if not already loaded."""
        if self._is_loaded:
            return

        with self._load_lock:
            if self._is_loaded:
                return

            if not self.is_available():
                raise FileNotFoundError(
                    f"SARChat model path '{self.model_path}' not found. "
                    "Please set SARCHAT_MODEL_PATH in your environment or .env file."
                )

            logging.info(f"[SAR] Loading SARChat model from {self.model_path} on {self.device}...")
            start_time = time.time()

            try:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_path,
                    trust_remote_code=True,
                )
                
                # Load model weights (float32 for CPU/MPS stability, bfloat16 for CUDA)
                dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
                self.model = AutoModel.from_pretrained(
                    self.model_path,
                    torch_dtype=dtype,
                    trust_remote_code=True,
                ).to(self.device)
                
                self.model.eval()
                self._is_loaded = True
                load_time = time.time() - start_time
                logging.info(f"[SAR] Model loaded successfully in {load_time:.2f}s on {self.device}")
            except Exception as e:
                logging.error(f"[SAR] Failed to load SARChat model: {e}")
                raise RuntimeError(f"Failed to load SARChat model: {e}") from e

    def infer(
        self,
        image_source: str | Path | Image.Image,
        question: str,
        max_new_tokens: int = 300,
    ) -> dict[str, Any]:
        """
        Executes SARChat inference on a given SAR image and natural-language question.
        Returns standardized dictionary with answer, model metadata, and latency.
        """
        if not question or not question.strip():
            raise ValueError("SAR question cannot be empty.")

        self.load_model()

        logging.info(f"[SAR] Received SAR query: '{question}'")
        logging.info(f"[SAR] Running inference on image: {image_source}")
        start_time = time.time()

        try:
            pil_img = load_sar_image_to_pil(image_source)
            pixel_values = self.transform(pil_img).unsqueeze(0).to(self.device)

            formatted_question = f"<image>\n{question.strip()}"
            gen_config = dict(max_new_tokens=max_new_tokens, do_sample=False)

            with torch.no_grad():
                response = self.model.chat(
                    tokenizer=self.tokenizer,
                    pixel_values=pixel_values,
                    question=formatted_question,
                    generation_config=gen_config,
                )

            latency_ms = (time.time() - start_time) * 1000.0
            logging.info(f"[SAR] Inference completed in {latency_ms:.1f}ms")

            return {
                "answer": str(response).strip(),
                "model": "SARChat-InternVL2.5-2B",
                "modality": "SAR",
                "latency_ms": round(latency_ms, 2),
                "status": "success",
            }
        except Exception as e:
            logging.error(f"[SAR] Inference error: {e}")
            return {
                "answer": f"SAR inference error: {str(e)}",
                "model": "SARChat-InternVL2.5-2B",
                "modality": "SAR",
                "latency_ms": (time.time() - start_time) * 1000.0,
                "status": "error",
                "error": str(e),
            }

    def query(self, image_path: str | Path, question: str) -> dict[str, Any]:
        """Programmatic interface for benchmark datasets and automated evaluations."""
        return self.infer(image_path, question)


def get_sar_service() -> SARChatService:
    """Convenience accessor for the SARChatService singleton."""
    return SARChatService.get_instance()
