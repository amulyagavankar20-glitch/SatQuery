"""Ingest GeoTIFF uploads into job storage, classify, and persist assets."""

from __future__ import annotations

import uuid
from datetime import timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from backend.schemas import InputClassification
from backend.services.input_classifier import InputClassifier
from backend.session import SessionContext, create_session
from backend.utils import ALLOWED_RASTER_EXTENSIONS, create_job_directory, validate_file_extension
from backend.exceptions import UnsupportedFormatError


def _safe_filename(name: str) -> str:
    stem = Path(name).name.replace("\\", "_").replace("/", "_")
    return stem or f"scene_{uuid.uuid4().hex[:8]}.tif"


def ingest_rasters(
    files: list[UploadFile],
    *,
    query: str = "",
    sensor: str | None = None,
) -> tuple[SessionContext, InputClassification, list[dict[str, Any]]]:
    if not files:
        raise UnsupportedFormatError("No raster files were uploaded.")

    job_id = uuid.uuid4()
    session_id = uuid.uuid4()
    dirs = create_job_directory(job_id)
    raw_dir = dirs["raw"]

    saved_paths: list[Path] = []
    for upload in files:
        filename = _safe_filename(upload.filename or "scene.tif")
        if not validate_file_extension(filename, ALLOWED_RASTER_EXTENSIONS):
            raise UnsupportedFormatError(
                f"Unsupported raster extension for '{filename}'. Use GeoTIFF (.tif/.tiff)."
            )
        dest = raw_dir / filename
        dest.write_bytes(upload.file.read())
        saved_paths.append(dest)

    processed_dir = dirs["processed"]
    for path in saved_paths:
        try:
            import rasterio
            import numpy as np
            from PIL import Image

            preview_png = processed_dir / f"composite_preview_{path.stem}.png"
            with rasterio.open(path) as src:
                count = src.count
                dtypes = src.dtypes
                is_float = any("float" in str(d).lower() for d in dtypes)
                if count >= 9:
                    data = src.read([3, 2, 1]).astype(np.float32)
                    p2, p98 = np.percentile(data, 2), np.percentile(data, 98)
                    norm = np.clip((data - p2) / (p98 - p2 + 1e-6) * 255.0, 0, 255).astype(np.uint8)
                    rgb = np.transpose(norm, (1, 2, 0))
                elif count >= 3:
                    data = src.read([1, 2, 3]).astype(np.float32)
                    p2, p98 = np.percentile(data, 2), np.percentile(data, 98)
                    norm = np.clip((data - p2) / (p98 - p2 + 1e-6) * 255.0, 0, 255).astype(np.uint8)
                    rgb = np.transpose(norm, (1, 2, 0))
                elif count == 2:
                    # Dual-polarization SAR (VV, VH)
                    vv = src.read(1).astype(np.float32)
                    vh = src.read(2).astype(np.float32)
                    vv_db = 10.0 * np.log10(np.clip(vv, 1e-5, None))
                    vh_db = 10.0 * np.log10(np.clip(vh, 1e-5, None))
                    vv_min, vv_max = np.percentile(vv_db, 2), np.percentile(vv_db, 98)
                    vh_min, vh_max = np.percentile(vh_db, 2), np.percentile(vh_db, 98)
                    r = np.clip((vv_db - vv_min) / (vv_max - vv_min + 1e-6), 0, 1)
                    g = np.clip((vh_db - vh_min) / (vh_max - vh_min + 1e-6), 0, 1)
                    b = np.clip(r / (g + 0.1), 0, 1)
                    rgb = (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)
                else:
                    b = src.read(1).astype(np.float32)
                    if is_float:
                        b_db = 10.0 * np.log10(np.clip(b, 1e-5, None))
                        b_min, b_max = np.percentile(b_db, 2), np.percentile(b_db, 98)
                        norm_b = np.clip((b_db - b_min) / (b_max - b_min + 1e-6) * 255.0, 0, 255).astype(np.uint8)
                    else:
                        p2, p98 = np.percentile(b, 2), np.percentile(b, 98)
                        norm_b = np.clip((b - p2) / (p98 - p2 + 1e-6) * 255.0, 0, 255).astype(np.uint8)
                    rgb = np.stack([norm_b, norm_b, norm_b], axis=-1)

            Image.fromarray(rgb).save(preview_png)
            default_composite = processed_dir / "composite.png"
            if not default_composite.is_file():
                Image.fromarray(rgb).save(default_composite)
        except Exception:
            pass

    classifier = InputClassifier()
    asset_inputs: list[dict[str, Any]] = []
    for path in saved_paths:
        item: dict[str, Any] = {
            "file_path": str(path.resolve()),
            "filename": path.name,
        }
        if sensor and sensor.strip():
            item["sensor"] = sensor.strip()
        asset_inputs.append(item)
    analysis = classifier.analyzer.analyze_inputs(asset_inputs)
    classification = classifier.classify(asset_inputs, analysis_metadata=analysis)
    analyzed = list(analysis.get("assets") or [])

    if sensor and sensor.strip():
        for asset in analyzed:
            asset.setdefault("sensor", sensor.strip())
            tags = dict(asset.get("tags") or {})
            tags.setdefault("SENSOR", sensor.strip())
            asset["tags"] = tags

    for asset in analyzed:
        acquired = asset.get("acquired_at")
        if acquired is not None and getattr(acquired, "tzinfo", None) is None:
            acquired = acquired.replace(tzinfo=timezone.utc)
        if acquired is not None:
            asset["acquired_at"] = acquired.isoformat() if hasattr(acquired, "isoformat") else acquired

    input_class = classification.input_class.value if classification.input_class else ""
    session = create_session(
        session_id=session_id,
        job_id=job_id,
        query=query,
        input_mode=input_class,
        task="UNROUTED",
    )
    session.status = "ingested" if classification.valid else "refused"
    session.classification = classification.model_dump(mode="json")
    session.metadata = {
        "assets": analyzed,
        "input_class": input_class,
        "classification": session.classification,
        "sensor": sensor,
    }
    if classification.spatial_relationship:
        session.pair_fitness = classification.spatial_relationship.model_dump(mode="json")
    if classification.refusal_reason:
        session.errors.append(classification.refusal_reason)

    return session, classification, analyzed
