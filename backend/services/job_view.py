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


def generate_raster_preview_png(tif_path: Path, output_png: Path) -> Path | None:
    """Generate high-quality contrast-stretched preview PNG from raw GeoTIFF."""
    if not tif_path.is_file():
        return None
    try:
        import numpy as np
        import rasterio
        from PIL import Image

        output_png.parent.mkdir(parents=True, exist_ok=True)
        if tif_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
            try:
                img = Image.open(tif_path).convert("RGB")
                img.save(output_png)
                return output_png
            except Exception:
                pass

        with rasterio.open(tif_path) as src:
            count = src.count
            dtypes = src.dtypes
            is_float = any("float" in str(d).lower() for d in dtypes)

            def _stretch_channel(ch: np.ndarray) -> np.ndarray:
                p2, p98 = np.percentile(ch, 2), np.percentile(ch, 98)
                if p98 > p2:
                    return np.clip((ch - p2) / (p98 - p2) * 255.0, 0, 255).astype(np.uint8)
                return np.clip(ch, 0, 255).astype(np.uint8)

            if count >= 9:
                # 9+ band Sentinel-2: True color R=B4(3), G=B3(2), B=B2(1)
                data = src.read([3, 2, 1]).astype(np.float32)
                r = _stretch_channel(data[0])
                g = _stretch_channel(data[1])
                b = _stretch_channel(data[2])
                rgb = np.stack([r, g, b], axis=-1)
            elif count == 4:
                # 4-band Sentinel-2 [B2(Blue), B3(Green), B4(Red), B8(NIR)]
                # True color RGB: Red=Band 3 (B4), Green=Band 2 (B3), Blue=Band 1 (B2)
                data = src.read([3, 2, 1]).astype(np.float32)
                r = _stretch_channel(data[0])
                g = _stretch_channel(data[1])
                b = _stretch_channel(data[2])
                rgb = np.stack([r, g, b], axis=-1)
            elif count >= 3:
                # Standard 3-band RGB [1, 2, 3]
                data = src.read([1, 2, 3]).astype(np.float32)
                r = _stretch_channel(data[0])
                g = _stretch_channel(data[1])
                b = _stretch_channel(data[2])
                rgb = np.stack([r, g, b], axis=-1)
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
                # Single band grayscale / intensity
                b = src.read(1).astype(np.float32)
                if is_float:
                    b_db = 10.0 * np.log10(np.clip(b, 1e-5, None))
                    b_min, b_max = np.percentile(b_db, 2), np.percentile(b_db, 98)
                    norm_b = np.clip((b_db - b_min) / (b_max - b_min + 1e-6) * 255.0, 0, 255).astype(np.uint8)
                else:
                    norm_b = _stretch_channel(b)
                rgb = np.stack([norm_b, norm_b, norm_b], axis=-1)

        Image.fromarray(rgb).save(output_png)
        return output_png
    except Exception as exc:
        logging.warning("Failed to generate raster preview for %s: %s", tif_path, exc)
        return None


def resolve_composite_path(job_id: str | Path, target_filename: str | None = None, prefer_t2: bool = False) -> Path | None:
    jdir = Path(job_id) if isinstance(job_id, (Path, str)) and "/" in str(job_id) else _job_dir(str(job_id))
    processed = jdir / "processed"
    raw_dir = jdir / "raw"

    if target_filename:
        # Match target filename in processed or raw
        target_stem = Path(target_filename).stem
        if processed.is_dir():
            candidates = list(processed.glob(f"*{target_stem}*.png"))
            if candidates:
                return candidates[0]
        if raw_dir.is_dir():
            tifs = list(raw_dir.glob(f"*{target_stem}*.tif*"))
            if tifs:
                processed.mkdir(parents=True, exist_ok=True)
                preview_png = processed / f"composite_preview_{tifs[0].stem}.png"
                if preview_png.is_file():
                    return preview_png
                res = generate_raster_preview_png(tifs[0], preview_png)
                if res:
                    return res

    if processed.is_dir():
        # First priority: explicit composite or preview files
        named = sorted(processed.glob("composite*.png"))
        if named:
            return named[-1] if prefer_t2 and len(named) > 1 else named[0]

        # Check for preview images that are NOT masks or overlays
        candidates = [
            p for p in sorted(processed.glob("*.png"))
            if not p.stem.endswith("_mask")
            and not p.stem.startswith("mask_")
            and p.name not in ("overlay.png", "vv.png", "vh.png")
            and not p.name.startswith("tile_")
        ]
        if candidates:
            return candidates[-1] if prefer_t2 and len(candidates) > 1 else candidates[0]

    # If processed composite is not ready, generate preview from raw GeoTIFF
    if raw_dir.is_dir():
        tifs = sorted(raw_dir.glob("*.tif*"))
        if tifs:
            target_tif = tifs[-1] if prefer_t2 and len(tifs) > 1 else tifs[0]
            processed.mkdir(parents=True, exist_ok=True)
            preview_png = processed / f"composite_preview_{target_tif.stem}.png"
            if preview_png.is_file():
                return preview_png
            res = generate_raster_preview_png(target_tif, preview_png)
            if res:
                return res

    return None


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


def resolve_asset_preview_path(job_id: str, asset_index: int = 0) -> Path | None:
    raw_dir = _job_dir(job_id) / "raw"
    processed = _job_dir(job_id) / "processed"
    processed.mkdir(parents=True, exist_ok=True)

    tifs: list[Path] = []
    if raw_dir.is_dir():
        tifs = sorted(raw_dir.glob("*.tif*"))

    if tifs and 0 <= asset_index < len(tifs):
        target_tif = tifs[asset_index]
        preview_png = processed / f"composite_preview_{target_tif.stem}.png"
        if preview_png.is_file():
            return preview_png
        res = generate_raster_preview_png(target_tif, preview_png)
        if res:
            return res

    return resolve_composite_path(job_id)


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
    assets = [r for r in (session.metadata.get("assets") or []) if isinstance(r, dict)]
    for idx, raw in enumerate(assets):
        bounds = raw.get("bounds_wgs84") or raw.get("bounds")
        views.append(
            JobAssetView(
                filename=str(raw.get("filename") or f"scene_{idx+1}.tif"),
                modality=str(raw.get("modality") or "OPTICAL"),
                sensor=raw.get("sensor"),
                bounds_wgs84=[float(x) for x in bounds] if bounds and len(bounds) == 4 else None,
                preview_url=f"/jobs/{job_id}/artifacts/assets/{idx}",
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
                preview_url=f"/jobs/{job_id}/artifacts/assets/{idx}",
            )
            for idx, row in enumerate(rows)
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
    if text is None:
        if session.status == "refused":
            text = session.errors[0] if session.errors else "Request was refused due to modality mismatch."
            confidence = "LOW"
        elif session.status not in ("completed", "failed"):
            return None

    if session.status == "refused":
        return JobAnswer(
            text=text,
            model="SystemValidator",
            backend="modality_gate",
            confidence=str(confidence) if confidence is not None else "LOW",
        )

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
    # Strictly isolate SAR from optical LULC evidence
    if session.input_mode in ("SINGLE_SAR", "SAR"):
        return None
    assets = [r for r in (session.metadata.get("assets") or []) if isinstance(r, dict)]
    active_slot = session.metadata.get("active_slot", "T1")
    active_asset = assets[1] if active_slot == "T2" and len(assets) > 1 else (assets[0] if assets else None)
    if active_asset and str(active_asset.get("modality", "")).upper() == "SAR":
        return None

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
    analysis_objects: list[Any] = []
    for res in session.tool_results:
        if isinstance(res, dict) and isinstance(res.get("result"), dict):
            objs = res["result"].get("analysis_objects") or []
            for obj in objs:
                if isinstance(obj, dict):
                    analysis_objects.append(obj)
                elif hasattr(obj, "model_dump"):
                    analysis_objects.append(obj.model_dump())

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
        analysis_objects=analysis_objects,
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
            if job.status == "refused":
                answer = JobAnswer(
                    text=text_out.text_result if (text_out and text_out.text_result) else (job.error_message or "Request was refused."),
                    model="SystemValidator",
                    backend="modality_gate",
                    confidence="LOW",
                )
            else:
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

    # Check for SAR, BIT Change, or Grounding detections in the session
    session = get_session_by_job_id(job_id)
    if session:
        for res in session.tool_results:
            if isinstance(res, dict) and isinstance(res.get("result"), dict):
                rdict = res["result"]
                dets = rdict.get("detections") or []
                ov = rdict.get("overlays") or rdict.get("geojson")
                if isinstance(ov, dict):
                    for feat in ov.get("features") or []:
                        if isinstance(feat, dict) and feat.get("geometry"):
                            features.append(feat)
                for det in dets:
                    geo_box = det.get("bbox_wgs84") or det.get("bbox")
                    if geo_box and len(geo_box) == 4 and not isinstance(det.get("centroid"), list):
                        d_minx, d_miny, d_maxx, d_maxy = geo_box
                        features.append({
                            "type": "Feature",
                            "properties": {
                                "feature_type": "DETECTION",
                                "kind": det.get("kind", "grounding"),
                                "label": det.get("type") or det.get("label", "structure"),
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
