"""Persist finished LangGraph runs into PostgreSQL / PostGIS."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.agents.state import GraphState
from backend.database import SessionLocal
from backend.models import Asset, Job, Output, SpatialFeature, ToolRegistry, ToolRun, Trace
from backend.utils import bbox_to_geometry, geojson_to_geometry
from backend.session import SessionContext
from src.logger import logging

_INPUT_MODE_TO_CLASS = {
    "SINGLE_OPTICAL": "SINGLE_OPTICAL",
    "SINGLE_SAR": "SINGLE_SAR",
    "BI_TEMPORAL": "BI_TEMPORAL",
    "BI_TEMPORAL_OPTICAL": "BI_TEMPORAL",
    "BI_TEMPORAL_SAR": "BI_TEMPORAL",
    "OPTICAL_SAR": "OPTICAL_SAR",
}


def normalize_input_class(value: str) -> str:
    """Map router input_mode strings onto InputClass enum values."""
    return _INPUT_MODE_TO_CLASS.get(value, value)


def _as_uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_job_record(
    *,
    job_id: str | uuid.UUID,
    session_id: str | uuid.UUID,
    query: str,
    input_mode: str,
    task: str,
    project_id: uuid.UUID | None = None,
    status: str = "running",
) -> Job:
    db = SessionLocal()
    try:
        existing = db.get(Job, _as_uuid(job_id))
        if existing is not None:
            existing.query = query or existing.query
            existing.input_mode = input_mode or existing.input_mode
            existing.task = task or existing.task
            existing.status = status
            if status == "running" and existing.started_at is None:
                existing.started_at = _utcnow()
            db.commit()
            db.refresh(existing)
            return existing
        job = Job(
            id=_as_uuid(job_id),
            project_id=project_id,
            session_id=_as_uuid(session_id),
            query=query,
            input_mode=input_mode,
            task=task or "UNROUTED",
            status=status,
            started_at=_utcnow() if status == "running" else None,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logging.warning("Database unavailable, skipping create_job_record: %s", exc)
        return None
    finally:
        try:
            db.close()
        except Exception:
            pass


def persist_assets(job_id: str | uuid.UUID, assets: list[dict[str, Any]]) -> None:
    """Store ingested raster metadata and WGS84 footprints in PostGIS."""
    from backend.utils import bbox_to_geometry

    db = SessionLocal()
    try:
        job_uuid = _as_uuid(job_id)
        for asset in assets:
            bounds = asset.get("bounds_wgs84") or asset.get("bounds")
            bbox = None
            if bounds and len(bounds) == 4:
                bbox = bbox_to_geometry(float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3]))
            acquired = asset.get("acquired_at")
            if isinstance(acquired, str):
                acquired = datetime.fromisoformat(acquired)
            if acquired is not None and getattr(acquired, "tzinfo", None) is None:
                acquired = acquired.replace(tzinfo=timezone.utc)
            db.add(
                Asset(
                    job_id=job_uuid,
                    file_path=str(asset.get("file_path") or ""),
                    filename=str(asset.get("filename") or "scene.tif")[:255],
                    format="GeoTIFF",
                    modality=str(asset.get("modality") or "OPTICAL"),
                    sensor=asset.get("sensor") or (asset.get("tags") or {}).get("SENSOR"),
                    acquired_at=acquired,
                    crs=asset.get("crs"),
                    width=asset.get("width"),
                    height=asset.get("height"),
                    bands=asset.get("band_descriptions"),
                    nodata=asset.get("nodata"),
                    cloud_fraction=asset.get("cloud_fraction"),
                    bbox=bbox,
                )
            )
        db.commit()
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logging.warning("Database unavailable, skipping persist_assets for job %s: %s", job_id, exc)
    finally:
        try:
            db.close()
        except Exception:
            pass


def persist_run(session: SessionContext, result: GraphState) -> None:
    """Write traces, tool runs, outputs, and final job status after a graph run."""
    db = SessionLocal()
    try:
        job_uuid = _as_uuid(session.job_id)
        job = db.get(Job, job_uuid)
        if job is None:
            job = Job(
                id=job_uuid,
                session_id=_as_uuid(session.session_id),
                query=session.query,
                input_mode=session.input_mode,
                task=session.task or "UNROUTED",
                status=session.status or "running",
                started_at=_utcnow(),
            )
            db.add(job)
            db.flush()

        job.status = session.status or result.get("status") or "completed"
        job.task = session.task or job.task
        job.route_json = session.route or None
        job.completed_at = _utcnow()
        if session.errors:
            job.error_message = "; ".join(session.errors)

        _persist_traces(db, job_uuid, session.traces)
        _persist_tool_runs(db, job_uuid, session.tool_results)
        _persist_outputs(db, job_uuid, result)
        _persist_spatial_features(db, job_uuid, result)

        db.commit()
    except Exception:
        db.rollback()
        logging.exception("Failed to persist finished job %s", session.job_id)
    finally:
        db.close()


def load_job(job_id: str) -> dict[str, Any] | None:
    """Return a serialized job with traces/outputs if it exists in Postgres."""
    db = SessionLocal()
    try:
        try:
            job_uuid = _as_uuid(job_id)
        except ValueError:
            return None
        job = db.get(Job, job_uuid)
        if job is None:
            return None
        traces = (
            db.execute(select(Trace).where(Trace.job_id == job.id).order_by(Trace.timestamp))
            .scalars()
            .all()
        )
        outputs = db.execute(select(Output).where(Output.job_id == job.id)).scalars().all()
        return {
            "session_id": str(job.session_id),
            "job_id": str(job.id),
            "status": job.status,
            "query": job.query,
            "input_mode": job.input_mode,
            "task": job.task,
            "route_json": job.route_json,
            "error_message": job.error_message,
            "traces": [
                {
                    "event_type": t.event_type,
                    "node_name": t.node_name,
                    "tool_id": t.tool_id,
                    "message": t.message,
                    "parameters": t.parameters,
                    "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                }
                for t in traces
            ],
            "outputs": [
                {
                    "output_type": o.output_type,
                    "text_result": o.text_result,
                    "file_path": o.file_path,
                    "confidence_label": o.confidence_label,
                }
                for o in outputs
            ],
        }
    finally:
        db.close()


def _persist_traces(db: Session, job_id: uuid.UUID, traces: list[dict[str, Any]]) -> None:
    for event in traces:
        db.add(
            Trace(
                job_id=job_id,
                event_type=event.get("event_type") or "LOG",
                node_name=event.get("node_name"),
                tool_id=event.get("tool_id"),
                parameters=event.get("parameters"),
                message=event.get("message"),
                trace_metadata=event.get("trace_metadata"),
            )
        )


def _persist_tool_runs(db: Session, job_id: uuid.UUID, tool_results: list[dict[str, Any]]) -> None:
    registry = {
        row.tool_id: row.id
        for row in db.execute(select(ToolRegistry)).scalars().all()
    }
    for index, result in enumerate(tool_results, start=1):
        tool_key = result.get("tool_id")
        registry_id = registry.get(tool_key)
        if registry_id is None:
            continue
        db.add(
            ToolRun(
                job_id=job_id,
                tool_id=registry_id,
                sequence_no=index,
                status=result.get("status") or "success",
                parameters=None,
                input_refs=result.get("input_refs"),
                output_refs=result.get("output_refs"),
                confidence=result.get("confidence"),
                latency_ms=result.get("latency_ms"),
                error_message="; ".join(result.get("warnings") or []) or None,
            )
        )


def _persist_outputs(db: Session, job_id: uuid.UUID, result: GraphState) -> None:
    report = result.get("report") or {}
    final_answer = result.get("final_answer") or report.get("final_answer")
    confidence = result.get("confidence")
    label = None
    if confidence is not None:
        label = confidence.level if hasattr(confidence, "level") else str(confidence)
    if final_answer:
        db.add(
            Output(
                job_id=job_id,
                output_type="TEXT",
                text_result=str(final_answer),
                mime_type="text/plain",
                confidence_label=label or report.get("confidence"),
            )
        )
    pre = result.get("preprocessing_result")
    output_paths: dict[str, Any] = {}
    if pre is not None:
        if hasattr(pre, "output_paths"):
            output_paths = pre.output_paths or {}
        elif isinstance(pre, dict):
            output_paths = pre.get("output_paths") or {}
    composite = output_paths.get("composite_png") or output_paths.get("composite_tif")
    if composite:
        db.add(
            Output(
                job_id=job_id,
                output_type="OVERLAY",
                file_path=str(composite),
                mime_type="image/png" if str(composite).endswith(".png") else "image/tiff",
                confidence_label=label or report.get("confidence"),
            )
        )


def _persist_spatial_features(db: Session, job_id: uuid.UUID, result: GraphState) -> None:
    """Store granular vector features (SAR detections, BIT change polygons, grounding) in PostGIS."""
    # 1. Process specialist tool results (SAR detections, BIT change polygons)
    specialist_results = result.get("specialist_results") or []
    for item in specialist_results:
        tool_id = getattr(item, "tool_id", None) or (item.get("tool_id") if isinstance(item, dict) else None)
        payload = getattr(item, "result", None) if hasattr(item, "result") else (item.get("result") if isinstance(item, dict) else None)
        if not isinstance(payload, dict):
            continue

        # SAR detections -> SpatialFeature (DETECTION bounding box)
        if tool_id == "sarchat_vqa":
            dets = payload.get("detections") or []
            for det in dets:
                if not isinstance(det, dict):
                    continue
                bbox = det.get("bbox_wgs84")
                if bbox and len(bbox) == 4:
                    try:
                        geom = bbox_to_geometry(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]), srid=4326)
                        db.add(
                            SpatialFeature(
                                job_id=job_id,
                                feature_type="DETECTION",
                                geometry=geom,
                                class_label=str(det.get("type") or "structure"),
                                confidence=float(det.get("confidence") or 0.88),
                                properties=det,
                            )
                        )
                    except Exception as exc:
                        logging.warning("Failed to construct SpatialFeature for SAR detection %s: %s", det.get("id"), exc)

        # BIT change detection -> SpatialFeature (CHANGE_POLYGON)
        elif tool_id == "bit_cd":
            geojson = payload.get("geojson") or {}
            features = geojson.get("features") or []
            for feat in features:
                if not isinstance(feat, dict):
                    continue
                geom_dict = feat.get("geometry")
                if geom_dict and isinstance(geom_dict, dict):
                    try:
                        geom = geojson_to_geometry(geom_dict, srid=4326)
                        props = feat.get("properties") or {}
                        area_m2 = props.get("area_m2")
                        db.add(
                            SpatialFeature(
                                job_id=job_id,
                                feature_type="CHANGE_POLYGON",
                                geometry=geom,
                                class_label=str(props.get("class") or "change"),
                                confidence=1.0,
                                area_m2=float(area_m2) if area_m2 is not None else None,
                                properties=props,
                            )
                        )
                    except Exception as exc:
                        logging.warning("Failed to construct SpatialFeature for BIT change feature: %s", exc)

    # 2. Process any direct spatial evidence items in GraphState
    spatial_evidence = result.get("spatial_evidence") or []
    for ev in spatial_evidence:
        if isinstance(ev, dict) and "type" in ev and "coordinates" in ev:
            try:
                geom = geojson_to_geometry(ev, srid=4326)
                db.add(
                    SpatialFeature(
                        job_id=job_id,
                        feature_type="SPATIAL_EVIDENCE",
                        geometry=geom,
                        class_label=ev.get("label", "evidence"),
                        confidence=float(ev.get("confidence", 0.9)),
                        properties=ev,
                    )
                )
            except Exception as exc:
                logging.warning("Failed to construct SpatialFeature for generic spatial evidence: %s", exc)

