"""
SatQuery AI — Specialized BIT LEVIR Change Detection Service

This service manages the lifecycle, preprocessing, ONNX Runtime inference,
and geospatial postprocessing for the Bitemporal Image Transformer (BIT)
model trained on the LEVIR-CD benchmark.
"""

from __future__ import annotations

import os
import time
import threading
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from PIL import Image
import rasterio
from rasterio.transform import Affine
from rasterio.warp import reproject, Resampling, transform_geom
import rasterio.features
from shapely.geometry import shape, mapping

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from backend.config import settings
from src.logger import logging


class BITService:
    """Thread-safe singleton service for BIT LEVIR ONNX Change Detection."""

    _instance: BITService | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.session: Any | None = None
        self.model_path: Path | None = None
        self.input_name_1: str = "img1"
        self.input_name_2: str = "img2"
        self.output_name: str = "pred"
        self.providers: list[str] = []
        self._init_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> BITService:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _get_configured_model_path(self) -> Path:
        """Resolves the BIT model path from settings or repository defaults."""
        raw_path = getattr(settings, "BIT_WEIGHTS_PATH", None) or "models/BIT_LEVIR_model.onnx"
        path = Path(raw_path)
        if not path.is_absolute():
            # Resolve relative to repo root
            repo_root = Path(__file__).resolve().parent.parent.parent
            path = repo_root / path
        return path

    def _load_session(self) -> Any:
        """Loads and caches the ONNX Runtime InferenceSession."""
        if self.session is not None:
            return self.session

        with self._init_lock:
            if self.session is not None:
                return self.session

            if ort is None:
                raise RuntimeError("onnxruntime is not installed in the environment.")

            model_path = self._get_configured_model_path()
            if not model_path.exists():
                raise FileNotFoundError(
                    f"BIT ONNX model file not found at: {model_path.name}"
                )

            # Validate that external weights file exists in the same folder
            external_data_path = model_path.parent / "BIT_LEVIR_model.onnx.data"
            if not external_data_path.exists():
                logging.warning(
                    "External tensor data file 'BIT_LEVIR_model.onnx.data' not found in model directory."
                )

            # Determine available execution providers safely
            available_providers = ort.get_available_providers()
            desired_providers = []
            if "CUDAExecutionProvider" in available_providers:
                desired_providers.append("CUDAExecutionProvider")
            if "CoreMLExecutionProvider" in available_providers:
                desired_providers.append("CoreMLExecutionProvider")
            desired_providers.append("CPUExecutionProvider")

            session_options = ort.SessionOptions()
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            logging.info(f"Loading BIT ONNX model from: {model_path.name}")
            session = ort.InferenceSession(
                str(model_path),
                sess_options=session_options,
                providers=desired_providers,
            )

            # Inspect input/output names dynamically
            inputs = session.get_inputs()
            outputs = session.get_outputs()

            if len(inputs) >= 2:
                self.input_name_1 = inputs[0].name
                self.input_name_2 = inputs[1].name
            elif len(inputs) == 1:
                self.input_name_1 = inputs[0].name

            if outputs:
                self.output_name = outputs[0].name

            self.session = session
            self.model_path = model_path
            self.providers = session.get_providers()
            logging.info(
                f"BIT ONNX model loaded successfully with providers: {self.providers}, "
                f"inputs: [{self.input_name_1}, {self.input_name_2}], output: '{self.output_name}'"
            )
            return self.session

    def align_and_load_pair(
        self,
        pre_source: str | Path | np.ndarray | Image.Image,
        post_source: str | Path | np.ndarray | Image.Image,
    ) -> tuple[np.ndarray, np.ndarray, Affine | None, str | None]:
        """
        Loads and spatially co-registers a bi-temporal optical image pair.
        Returns:
            (pre_rgb_uint8, post_rgb_uint8, affine_transform, crs_wkt_or_string)
        """
        pre_arr = None
        post_arr = None
        transform: Affine | None = None
        crs_str: str | None = None

        # Check if pre_source is a GeoTIFF path
        if isinstance(pre_source, (str, Path)) and str(pre_source).lower().endswith((".tif", ".tiff")) and Path(pre_source).exists():
            with rasterio.open(pre_source) as src_pre:
                transform = src_pre.transform
                crs_str = src_pre.crs.to_string() if src_pre.crs else None
                pre_bands = src_pre.read()  # (C, H, W)
                if pre_bands.shape[0] >= 3:
                    pre_arr = pre_bands[:3].transpose(1, 2, 0)
                else:
                    pre_arr = np.repeat(pre_bands[0][:, :, np.newaxis], 3, axis=2)

            # Check if post_source is also a GeoTIFF to reproject to pre grid if needed
            if isinstance(post_source, (str, Path)) and str(post_source).lower().endswith((".tif", ".tiff")) and Path(post_source).exists():
                with rasterio.open(post_source) as src_post:
                    # If CRS or transform differs, reproject to pre grid
                    if src_post.crs != src_pre.crs or src_post.transform != src_pre.transform or src_post.shape != src_pre.shape:
                        post_reprojected = np.zeros_like(pre_bands)
                        for b in range(min(pre_bands.shape[0], src_post.count)):
                            reproject(
                                source=rasterio.band(src_post, b + 1),
                                destination=post_reprojected[b],
                                src_transform=src_post.transform,
                                src_crs=src_post.crs,
                                dst_transform=transform,
                                dst_crs=src_pre.crs,
                                resampling=Resampling.bilinear,
                            )
                        if post_reprojected.shape[0] >= 3:
                            post_arr = post_reprojected[:3].transpose(1, 2, 0)
                        else:
                            post_arr = np.repeat(post_reprojected[0][:, :, np.newaxis], 3, axis=2)
                    else:
                        post_bands = src_post.read()
                        if post_bands.shape[0] >= 3:
                            post_arr = post_bands[:3].transpose(1, 2, 0)
                        else:
                            post_arr = np.repeat(post_bands[0][:, :, np.newaxis], 3, axis=2)

        # Fallback to standard loading if arrays not yet populated
        if pre_arr is None:
            pre_arr = self._load_to_numpy_rgb(pre_source)
        if post_arr is None:
            post_arr = self._load_to_numpy_rgb(post_source)

        # Ensure uint8 [0, 255]
        pre_arr = self._normalize_to_uint8(pre_arr)
        post_arr = self._normalize_to_uint8(post_arr)

        # Ensure spatial shapes match
        if pre_arr.shape[:2] != post_arr.shape[:2]:
            h, w = pre_arr.shape[:2]
            post_img = Image.fromarray(post_arr).resize((w, h), Image.Resampling.BILINEAR)
            post_arr = np.array(post_img)

        return pre_arr, post_arr, transform, crs_str

    def _load_to_numpy_rgb(self, source: str | Path | np.ndarray | Image.Image) -> np.ndarray:
        if isinstance(source, Image.Image):
            return np.array(source.convert("RGB"))
        elif isinstance(source, np.ndarray):
            if source.ndim == 2:
                return np.repeat(source[:, :, np.newaxis], 3, axis=2)
            elif source.ndim == 3:
                if source.shape[0] == 3 and source.shape[2] != 3:
                    return source.transpose(1, 2, 0)
                return source[:, :, :3]
            raise ValueError(f"Unsupported array shape: {source.shape}")
        else:
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(f"Image not found at: {path}")
            img = Image.open(path).convert("RGB")
            return np.array(img)

    def _normalize_to_uint8(self, arr: np.ndarray) -> np.ndarray:
        if arr.dtype == np.uint8:
            return arr
        if np.issubdtype(arr.dtype, np.floating):
            if arr.max() <= 1.0:
                arr = arr * 255.0
            return np.clip(arr, 0, 255).astype(np.uint8)
        # Handle uint16 or other integer ranges via min-max stretch
        vmin, vmax = np.percentile(arr, (1, 99))
        if vmax > vmin:
            scaled = np.clip((arr - vmin) / (vmax - vmin) * 255.0, 0, 255)
            return scaled.astype(np.uint8)
        return np.clip(arr, 0, 255).astype(np.uint8)

    def preprocess_tensor(self, rgb_uint8: np.ndarray) -> np.ndarray:
        """
        Converts RGB uint8 image array to normalized float32 tensor in range [-1.0, 1.0].
        Shape: [1, 3, H, W]
        """
        # (H, W, 3) -> float32 in [-1.0, 1.0]
        # Formula: pixel / 127.5 - 1.0
        normalized = (rgb_uint8.astype(np.float32) / 127.5) - 1.0
        # (H, W, 3) -> (3, H, W) -> (1, 3, H, W)
        tensor = normalized.transpose(2, 0, 1)
        tensor = np.expand_dims(tensor, axis=0)
        return tensor

    def infer_tensors(self, t1: np.ndarray, t2: np.ndarray) -> np.ndarray:
        """
        Runs ONNX Runtime inference on a pair of pre/post tensors.
        Returns:
            binary change mask array (H, W) where 1=change, 0=no change.
        """
        session = self._load_session()

        _, _, orig_h, orig_w = t1.shape

        # Pad to multiple of 8 if necessary for model stride compatibility
        pad_h = (8 - (orig_h % 8)) % 8
        pad_w = (8 - (orig_w % 8)) % 8

        if pad_h > 0 or pad_w > 0:
            t1_in = np.pad(t1, ((0, 0), (0, 0), (0, pad_h), (0, pad_w)), mode="reflect")
            t2_in = np.pad(t2, ((0, 0), (0, 0), (0, pad_h), (0, pad_w)), mode="reflect")
        else:
            t1_in = t1
            t2_in = t2

        inputs = {
            self.input_name_1: t1_in.astype(np.float32),
            self.input_name_2: t2_in.astype(np.float32),
        }

        outputs = session.run([self.output_name], inputs)
        raw_pred = outputs[0]  # Shape: (1, 2, H_padded, W_padded)

        # Slice back to original dimensions
        pred = raw_pred[0, :, :orig_h, :orig_w]  # (2, orig_h, orig_w)

        # Argmax decision: Channel 1 corresponds to Changed state
        change_mask = (np.argmax(pred, axis=0) == 1).astype(np.uint8)
        return change_mask

    def infer_large_scene(
        self,
        pre_arr: np.ndarray,
        post_arr: np.ndarray,
        tile_size: int = 512,
        overlap: int = 64,
    ) -> np.ndarray:
        """
        Tiled inference with overlap blending for large satellite scenes.
        """
        h, w = pre_arr.shape[:2]
        if h <= tile_size and w <= tile_size:
            t1 = self.preprocess_tensor(pre_arr)
            t2 = self.preprocess_tensor(post_arr)
            return self.infer_tensors(t1, t2)

        stride = tile_size - overlap
        full_mask = np.zeros((h, w), dtype=np.uint8)

        for y in range(0, h, stride):
            for x in range(0, w, stride):
                y_end = min(y + tile_size, h)
                x_end = min(x + tile_size, w)
                y_start = max(0, y_end - tile_size)
                x_start = max(0, x_end - tile_size)

                chip_pre = pre_arr[y_start:y_end, x_start:x_end]
                chip_post = post_arr[y_start:y_end, x_start:x_end]

                t1 = self.preprocess_tensor(chip_pre)
                t2 = self.preprocess_tensor(chip_post)
                chip_mask = self.infer_tensors(t1, t2)

                full_mask[y_start:y_end, x_start:x_end] = np.maximum(
                    full_mask[y_start:y_end, x_start:x_end],
                    chip_mask,
                )

        return full_mask

    def postprocess_mask(
        self,
        mask: np.ndarray,
        transform: Affine | None = None,
        crs_str: str | None = None,
        min_region_pixels: int = 10,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        Calculates change metrics and converts mask polygons to WGS84 GeoJSON features.
        """
        total_pixels = int(mask.size)
        changed_pixels = int(np.count_nonzero(mask))
        unchanged_pixels = total_pixels - changed_pixels
        change_percentage = (changed_pixels / total_pixels * 100.0) if total_pixels > 0 else 0.0

        pixel_res_x = abs(transform.a) if transform else 10.0
        pixel_res_y = abs(transform.e) if transform else 10.0
        pixel_area_m2 = pixel_res_x * pixel_res_y
        changed_area_m2 = float(changed_pixels * pixel_area_m2)
        changed_area_km2 = float(changed_area_m2 / 1e6)

        stats = {
            "total_pixels": total_pixels,
            "changed_pixels": changed_pixels,
            "unchanged_pixels": unchanged_pixels,
            "change_percentage": round(change_percentage, 2),
            "changed_area_m2": round(changed_area_m2, 2),
            "changed_area_km2": round(changed_area_km2, 4),
            "pixel_resolution_m": round(pixel_res_x, 2),
            "crs": crs_str or "EPSG:4326",
        }

        # Vectorize change mask to GeoJSON polygons
        geojson_features: list[dict[str, Any]] = []
        if changed_pixels > 0:
            eff_transform = transform if transform is not None else Affine.identity()
            shapes_gen = rasterio.features.shapes(
                mask.astype(np.int16),
                mask=(mask > 0),
                transform=eff_transform,
            )

            for geom_dict, val in shapes_gen:
                if int(val) == 1:
                    poly_geom = shape(geom_dict)
                    if poly_geom.area < (min_region_pixels * pixel_area_m2 if transform else min_region_pixels):
                        continue

                    # Reproject to WGS84 if in a projected CRS
                    if crs_str and crs_str.upper() not in ("EPSG:4326", "WGS84", "OGC:CRS84"):
                        try:
                            geom_wgs84 = transform_geom(crs_str, "EPSG:4326", mapping(poly_geom))
                            final_geom = geom_wgs84
                            poly_shape = shape(geom_wgs84)
                            centroid = [poly_shape.centroid.x, poly_shape.centroid.y]
                            bounds = list(poly_shape.bounds)
                        except Exception:
                            final_geom = mapping(poly_geom)
                            centroid = [poly_geom.centroid.x, poly_geom.centroid.y]
                            bounds = list(poly_geom.bounds)
                    else:
                        final_geom = mapping(poly_geom)
                        centroid = [poly_geom.centroid.x, poly_geom.centroid.y]
                        bounds = list(poly_geom.bounds)

                    feature = {
                        "type": "Feature",
                        "geometry": final_geom,
                        "properties": {
                            "feature_type": "optical_change_detection",
                            "model": "BIT-LEVIR",
                            "area_m2": round(poly_geom.area if transform else poly_geom.area * 100.0, 2),
                            "centroid": centroid,
                            "bbox": bounds,
                        },
                    }
                    geojson_features.append(feature)

        stats["region_count"] = len(geojson_features)
        return stats, geojson_features

    def render_overlay(
        self,
        post_rgb_uint8: np.ndarray,
        mask: np.ndarray,
        output_path: str | Path,
    ) -> str:
        """
        Blends the binary change mask (translucent red) onto the post-event image.
        """
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        base = post_rgb_uint8.copy()
        overlay = base.copy()
        # Red highlight for changed pixels
        overlay[mask > 0] = [255, 30, 30]

        # 60% base + 40% overlay
        blended = (0.6 * base.astype(np.float32) + 0.4 * overlay.astype(np.float32)).astype(np.uint8)
        img = Image.fromarray(blended)
        img.save(out_p, format="PNG")
        return str(out_p)

    def run_change_detection(
        self,
        pre_source: str | Path | np.ndarray | Image.Image,
        post_source: str | Path | np.ndarray | Image.Image,
        output_dir: str | Path | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Executes end-to-end BIT optical change detection.
        """
        t0 = time.perf_counter()
        pre_arr, post_arr, transform, crs_str = self.align_and_load_pair(pre_source, post_source)

        # Inference
        mask = self.infer_large_scene(pre_arr, post_arr)

        # Postprocessing
        stats, features = self.postprocess_mask(mask, transform, crs_str)

        # Render visualization overlay if output directory is specified
        overlay_path = None
        if output_dir or job_id:
            dest_dir = Path(output_dir or f"data/jobs/{job_id or 'default'}")
            dest_dir.mkdir(parents=True, exist_ok=True)
            overlay_file = dest_dir / "bit_change_overlay.png"
            overlay_path = self.render_overlay(post_arr, mask, overlay_file)

        elapsed_sec = round(time.perf_counter() - t0, 3)
        stats["inference_time_seconds"] = elapsed_sec

        # Construct narrative summary
        pct = stats["change_percentage"]
        regions = stats["region_count"]
        summary = (
            f"BIT change detection identified {pct:.2f}% surface alteration "
            f"({stats['changed_area_m2']} m²) concentrated across {regions} localized region(s)."
        )

        return {
            "success": True,
            "mask": mask,
            "statistics": stats,
            "geojson": {
                "type": "FeatureCollection",
                "features": features,
            },
            "overlay_path": overlay_path,
            "summary": summary,
            "elapsed_seconds": elapsed_sec,
        }
