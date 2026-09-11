"""Assemble the Analyze UI JobView from live session and/or Postgres."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Asset, Job, Output, Trace
from backend.schemas import JobAnswer, JobAssetView, JobLulcTag, JobLulcView, JobOverlay, JobTraceView, JobView
from backend.session import SessionContext, get_session_by_job_id
from src.logger import logging


def _job_dir(job_id: str) -> Path:
    return settings.full_job_storage_dir / str(job_id)


def artifact_url(job_id: str, kind: str) -> str:
    return f"/jobs/{job_id}/artifacts/{kind}"


def export_url(job_id: str, fmt: str) -> str:
    return f"/jobs/{job_id}/export.{fmt}"


def list_tile_paths(job_id: str) -> list[Path]:
    tiles_dir = _job_dir(job_id) / "tiles"
    if not tiles_dir.is_dir():
        return []
    return sorted(p for p in tiles_dir.glob("*.png") if p.is_file())


def resolve_composite_path(job_id: str) -> Path | None:
    processed = _job_dir(job_id) / "processed"
    if not processed.is_dir():
        return None
    comp = processed / "composite.png"
    if comp.is_file():
        return comp
    pngs = sorted(processed.glob("*.png"))
    if pngs:
        return pngs[0]
    tifs = sorted(processed.glob("*.tif")) + sorted(processed.glob("*.tiff"))
    return tifs[0] if tifs else None


def resolve_vv_path(job_id: str) -> Path | None:
    processed = _job_dir(job_id) / "processed"
    if not processed.is_dir():
        return None
    vv = processed / "vv.png"
    return vv if vv.is_file() else None


def resolve_vh_path(job_id: str) -> Path | None:
    processed = _job_dir(job_id) / "processed"
    if not processed.is_dir():
        return None
    vh = processed / "vh.png"
    return vh if vh.is_file() else None


def resolve_overlay_path(job_id: str) -> Path | None:
    processed = _job_dir(job_id) / "processed"
    if not processed.is_dir():
        return None
    overlay = processed / "overlay.png"
    return overlay if overlay.is_file() else None


def resolve_tile_path(job_id: str, index: int) -> Path | None:
    tiles = list_tile_paths(job_id)
    if index < 0 or index >= len(tiles):
        return None
    return tiles[index]


def safe_job_file(job_id: str, path: Path) -> Path | None:
    """Return path if it is inside this job's storage directory."""
    try:
        job_root = _job_dir(job_id).resolve()
        resolved = path.resolve()
        resolved.relative_to(job_root)
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def _bounds_from_asset_row(asset: Asset) -> list[float] | None:
    if asset.bbox is None:
        return None
    try:
        from geoalchemy2.shape import to_shape
        geom = to_shape(asset.bbox)
        return [float(c) for c in geom.bounds]
    except Exception:
        logging.warning("Could not convert asset bbox for %s", asset.id)
        return None


def _session_asset_views(session: SessionContext, job_id: str) -> list[JobAssetView]:
    views: list[JobAssetView] = []
    for raw in session.metadata.get("assets") or []:
        if not isinstance(raw, dict):
            continue
        bounds = raw.get("bounds_wgs84") or raw.get("bounds")
        views.append(
            JobAssetView(
                filename=str(raw.get("filename") or "scene.tif"),
                modality=str(raw.get("modality") or "OPTICAL"),
                sensor=raw.get("sensor"),
                bounds_wgs84=[float(x) for x in bounds] if bounds and len(bounds) == 4 else None,
                preview_url=artifact_url(job_id, "composite"),
            )
        )
    return views


def _db_asset_views(job_id: uuid.UUID) -> list[JobAssetView]:
    db = SessionLocal()
    try:
        rows = db.execute(select(Asset).where(Asset.job_id == job_id)).scalars().all()
        return [
            JobAssetView(
                filename=row.filename,
                modality=row.modality,
                sensor=row.sensor,
                bounds_wgs84=_bounds_from_asset_row(row),
                preview_url=artifact_url(str(job_id), "composite"),
            )
            for row in rows
        ]
    finally:
        db.close()


def _answer_from_session(session: SessionContext) -> JobAnswer | None:
    text = None
    confidence = None
    for artifact in reversed(session.artifacts):
        if not isinstance(artifact, dict):
            continue
        payload = artifact.get("payload") or {}
        if payload.get("final_answer"):
            text = str(payload["final_answer"])
            confidence = payload.get("confidence")
            break
    if text is None and session.tool_results:
        last = session.tool_results[-1]
        if isinstance(last, dict) and last.get("result"):
            text = str(last["result"])
    if text is None and session.status not in ("completed", "failed", "refused"):
        return None

    is_sar = (
        session.input_mode == "SINGLE_SAR"
        or any(t.tool_id == "sar_map" for t in session.traces if hasattr(t, "tool_id"))
        or any(isinstance(t, dict) and t.get("tool_id") == "sar_map" for t in session.traces)
    )
    model_name = "reBEN-ResNet50-S1" if is_sar else settings.TALKING_VLM_MODEL
    backend_name = "reben_s1" if is_sar else settings.TALKING_VLM_BACKEND

    return JobAnswer(
        text=text,
        model=model_name,
        backend=backend_name,
        confidence=str(confidence) if confidence is not None else None,
    )


def _lulc_from_session(session: SessionContext) -> JobLulcView | None:
    for res in session.tool_results:
        if not isinstance(res, dict) or res.get("tool_id") != "lulc_map":
            continue
        payload = res.get("result")
        if not isinstance(payload, dict) or "fractions" not in payload:
            continue
        tags: list[JobLulcTag] = []
        for raw in payload.get("scene_tags") or []:
            if not isinstance(raw, dict) or not raw.get("name"):
                continue
            tags.append(
                JobLulcTag(
                    name=str(raw["name"]),
                    score=float(raw.get("score") or 0),
                    source=str(raw["source"]) if raw.get("source") else None,
                )
            )
        fractions = {
            str(k): float(v)
            for k, v in (payload.get("fractions") or {}).items()
            if isinstance(v, (int, float))
        }
        return JobLulcView(
            backend=str(payload.get("backend") or "spectral_fallback"),
            focus=str(payload.get("focus") or "land_cover"),
            fractions=fractions,
            scene_tags=tags,
        )
    return None


def _warnings_from_session(session: SessionContext) -> list[str]:
    for artifact in session.artifacts:
        if isinstance(artifact, dict):
            payload = artifact.get("payload") or {}
            warnings = payload.get("warnings")
            if isinstance(warnings, list):
                return [str(w) for w in warnings]
    return []


def _tile_count(job_id: str, session: SessionContext | None) -> int:
    n = len(list_tile_paths(job_id))
    if n:
        return n
    if session and isinstance(session.preprocessing_result, dict):
        refs = session.preprocessing_result.get("tile_references") or []
        return len(refs)
    return 0


def _route_dict(route: Any) -> dict[str, Any] | None:
    if route is None or route == {}:
        return None
    if hasattr(route, "model_dump"):
        return route.model_dump()
    if isinstance(route, dict):
        return route
    return None


def build_job_view_from_session(session: SessionContext) -> JobView:
    job_id = session.job_id
    assets = _session_asset_views(session, job_id) or _db_asset_views(uuid.UUID(job_id))
    overlays: list[JobOverlay] = []
    if any(a.bounds_wgs84 for a in assets):
        overlays.append(
            JobOverlay(type="FOOTPRINT", geojson_url=export_url(job_id, "geojson"), confidence=None)
        )
    if resolve_overlay_path(job_id) is not None:
        overlays.append(
            JobOverlay(type="GROUNDING", geojson_url=export_url(job_id, "geojson"), confidence=0.88)
        )
    traces = [
        JobTraceView(
            event_type=str(t.get("event_type") or "LOG"),
            node_name=t.get("node_name"),
            tool_id=t.get("tool_id"),
            message=t.get("message"),
            timestamp=t.get("timestamp"),
        )
        for t in session.traces
        if isinstance(t, dict)
    ]
    return JobView(
        job_id=job_id,
        session_id=session.session_id,
        status=session.status,
        query=session.query,
        input_class=session.input_mode,
        task=session.task or "UNROUTED",
        route=_route_dict(session.route),
        answer=_answer_from_session(session),
        assets=assets,
        overlays=overlays,
        traces=traces,
        warnings=_warnings_from_session(session),
        errors=list(session.errors),
        refusal_reason=session.errors[0] if session.status == "refused" and session.errors else None,
        tile_count=_tile_count(job_id, session),
        lulc=_lulc_from_session(session),
    )


def build_job_view_from_db(job_id: str) -> JobView | None:
    db = SessionLocal()
    try:
        try:
            job_uuid = uuid.UUID(str(job_id))
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
        text_out = next((o for o in outputs if o.output_type == "TEXT" and o.text_result), None)
        answer = None
        if text_out is not None or job.status in ("completed", "failed", "refused"):
            is_sar = (
                job.input_mode == "SINGLE_SAR"
                or any(t.tool_id == "sar_map" for t in traces)
            )
            model_name = "reBEN-ResNet50-S1" if is_sar else settings.TALKING_VLM_MODEL
            backend_name = "reben_s1" if is_sar else settings.TALKING_VLM_BACKEND
            answer = JobAnswer(
                text=text_out.text_result if text_out else None,
                model=model_name,
                backend=backend_name,
                confidence=text_out.confidence_label if text_out else None,
            )
        assets = _db_asset_views(job.id)
        overlays: list[JobOverlay] = []
        if any(a.bounds_wgs84 for a in assets):
            overlays.append(
                JobOverlay(type="FOOTPRINT", geojson_url=export_url(str(job.id), "geojson"), confidence=None)
            )
        return JobView(
            job_id=str(job.id),
            session_id=str(job.session_id),
            status=job.status,
            query=job.query or "",
            input_class=job.input_mode or "",
            task=job.task or "UNROUTED",
            route=job.route_json,
            answer=answer,
            assets=assets,
            overlays=overlays,
            traces=[
                JobTraceView(
                    event_type=t.event_type,
                    node_name=t.node_name,
                    tool_id=t.tool_id,
                    message=t.message,
                    timestamp=t.timestamp.isoformat() if t.timestamp else None,
                )
                for t in traces
            ],
            warnings=[],
            errors=[job.error_message] if job.error_message else [],
            refusal_reason=job.error_message if job.status == "refused" else None,
            tile_count=_tile_count(str(job.id), None),
        )
    finally:
        db.close()


def get_job_view(job_id: str) -> JobView | None:
    session = get_session_by_job_id(job_id)
    if session:
        return build_job_view_from_session(session)
    return build_job_view_from_db(job_id)


def footprint_geojson(job_id: str) -> dict[str, Any] | None:
    view = get_job_view(job_id)
    if view is None:
        return None
    features: list[dict[str, Any]] = []
    for asset in view.assets:
        b = asset.bounds_wgs84
        if not b or len(b) != 4:
            continue
        minx, miny, maxx, maxy = b
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "feature_type": "FOOTPRINT",
                    "filename": asset.filename,
                    "modality": asset.modality,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny],
                    ]],
                },
            }
        )

    # Check for SAR or Grounding detections in the session
    session = get_session_by_job_id(job_id)
    if session:
        for res in session.tool_results:
            if isinstance(res, dict) and isinstance(res.get("result"), dict):
                dets = res["result"].get("detections") or []
                ov = res["result"].get("overlays")
                if isinstance(ov, dict):
                    for feat in ov.get("features") or []:
                        if isinstance(feat, dict) and feat.get("geometry"):
                            features.append(feat)
                for det in dets:
                    geo_box = det.get("bbox_wgs84")
                    if geo_box and len(geo_box) == 4:
                        d_minx, d_miny, d_maxx, d_maxy = geo_box
                        features.append({
                            "type": "Feature",
                            "properties": {
                                "feature_type": "DETECTION",
                                "kind": "grounding",
                                "label": det.get("type", "structure"),
                                "id": det.get("id"),
                                "confidence": det.get("confidence", 0.88),
                                "image_position": det.get("image_position"),
                            },
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[
                                    [d_minx, d_miny], [d_maxx, d_miny], [d_maxx, d_maxy], [d_minx, d_maxy], [d_minx, d_miny],
                                ]],
                            },
                        })

    return {"type": "FeatureCollection", "features": features}


def footprint_kml(job_id: str) -> str | None:
    geo = footprint_geojson(job_id)
    if geo is None:
        return None
    placemarks: list[str] = []
    for feat in geo["features"]:
        coords = feat["geometry"]["coordinates"][0]
        coord_str = " ".join(f"{x},{y},0" for x, y in coords)
        name = feat["properties"].get("filename") or "footprint"
        placemarks.append(
            f"<Placemark><name>{name}</name>"
            f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{coord_str}"
            f"</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>"
        )
    inner = "".join(placemarks)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        f"{inner}</Document></kml>"
    )
