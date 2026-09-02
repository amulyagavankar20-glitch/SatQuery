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

    classifier = InputClassifier()
    asset_inputs: list[dict[str, Any]] = []
    for path in saved_paths:
        asset_inputs.append({
            "file_path": str(path.resolve()),
            "filename": path.name,
            "sensor": sensor,
        })
    analysis = classifier.analyzer.analyze_inputs(asset_inputs)
    classification = classifier.classify(asset_inputs, analysis_metadata=analysis)
    analyzed = list(analysis.get("assets") or [])

    if sensor:
        for asset in analyzed:
            asset.setdefault("sensor", sensor)
            tags = dict(asset.get("tags") or {})
            tags.setdefault("SENSOR", sensor)
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
