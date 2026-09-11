"""Locked SatQuery specialist catalog for tool_registry seeding."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import ToolRegistry
from backend.schemas import InputClass, RouterTask

_ALL_TASKS = [t.value for t in RouterTask]
_ALL_CLASSES = [c.value for c in InputClass]


def _tool(
    tool_id: str,
    name: str,
    tool_type: str,
    *,
    model_name: str | None = None,
    model_version: str | None = None,
    description: str,
    supported_tasks: list[str],
    supported_modalities: list[str],
) -> dict[str, Any]:
    return {
        "tool_id": tool_id,
        "name": name,
        "tool_type": tool_type,
        "model_name": model_name,
        "model_version": model_version,
        "description": description,
        "supported_tasks": supported_tasks,
        "supported_modalities": supported_modalities,
        "enabled": True,
    }


TOOL_CATALOG: list[dict[str, Any]] = [
    _tool(
        "preprocess",
        "Input-type-aware preprocessor",
        "UTILITY",
        description="Composite, calibrate, align, and tile rasters before specialist inference.",
        supported_tasks=_ALL_TASKS,
        supported_modalities=_ALL_CLASSES,
    ),
    _tool(
        "sar_map",
        "Sentinel-1 BigEarthNet mapper",
        "CLASSIFICATION",
        model_name="reBEN-ResNet50-S1",
        model_version="resnet50-s1-v0.2.0",
        description="ResNet50 trained on Sentinel-1 BigEarthNet v2 (19 CORINE classes) plus VV/VH backscatter fractions.",
        supported_tasks=[RouterTask.SINGLE_VQA.value, RouterTask.CAPTIONING.value, RouterTask.GROUNDING.value],
        supported_modalities=[InputClass.SINGLE_SAR.value],
    ),
    _tool(
        "lulc_map",
        "Dynamic World land cover",
        "SEGMENTATION",
        model_name="DynamicWorld",
        model_version="dw-s2-9class",
        description="Nine-class pixel map (Dynamic World on S2, spectral fallback on RGB). Scene tags use BigEarthNet-19 names mapped from those fractions — DW is not trained on BEN.",
        supported_tasks=[RouterTask.SINGLE_VQA.value, RouterTask.CAPTIONING.value, RouterTask.GROUNDING.value],
        supported_modalities=[InputClass.SINGLE_OPTICAL.value, InputClass.BI_TEMPORAL.value],
    ),
    _tool(
        "geochat_vqa",
        "GeoChat VQA",
        "VLM",
        model_name="GeoChat-7B",
        model_version="geochat-7b-qlora-ben-v1",
        description="Talking VLM for single-image VQA and captioning.",
        supported_tasks=[RouterTask.SINGLE_VQA.value, RouterTask.CAPTIONING.value, RouterTask.GROUNDING.value],
        supported_modalities=[InputClass.SINGLE_OPTICAL.value, InputClass.SINGLE_SAR.value],
    ),
    _tool(
        "geochat_describe",
        "GeoChat describe",
        "VLM",
        model_name="GeoChat-7B",
        model_version="geochat-7b-qlora-ben-v1",
        description="Describe a change crop or optical–SAR fusion result.",
        supported_tasks=[RouterTask.CHANGE_VQA.value, RouterTask.OPTICAL_SAR_ANALYSIS.value],
        supported_modalities=[InputClass.BI_TEMPORAL.value, InputClass.OPTICAL_SAR.value],
    ),
    _tool(
        "grounding",
        "Phrase grounding",
        "SEGMENTATION",
        model_name="MobileSAM",
        model_version="mobilesam-v1",
        description="Ground a GeoChat phrase onto the image with MobileSAM.",
        supported_tasks=[RouterTask.GROUNDING.value],
        supported_modalities=[InputClass.SINGLE_OPTICAL.value, InputClass.SINGLE_SAR.value],
    ),
    _tool(
        "mobile_sam",
        "MobileSAM",
        "SEGMENTATION",
        model_name="MobileSAM",
        model_version="mobilesam-v1",
        description="Optional grounding fallback from a GeoChat phrase.",
        supported_tasks=[RouterTask.GROUNDING.value],
        supported_modalities=[InputClass.SINGLE_OPTICAL.value, InputClass.SINGLE_SAR.value],
    ),
    _tool(
        "align",
        "Bitemporal aligner",
        "UTILITY",
        description="Co-register a bitemporal pair onto a shared grid.",
        supported_tasks=[RouterTask.CHANGE_DETECTION.value, RouterTask.CHANGE_VQA.value],
        supported_modalities=[InputClass.BI_TEMPORAL.value],
    ),
    _tool(
        "bit_cd",
        "BIT change detector",
        "CHANGE_DETECTOR",
        model_name="BIT",
        model_version="bit-cd-256",
        description="Silent pixel-level change mask on 256 tiles.",
        supported_tasks=[RouterTask.CHANGE_DETECTION.value, RouterTask.CHANGE_VQA.value],
        supported_modalities=[InputClass.BI_TEMPORAL.value],
    ),
    _tool(
        "vectorize",
        "Change vectorizer",
        "UTILITY",
        description="Polygonize a change mask into CRS-aware GeoJSON.",
        supported_tasks=[RouterTask.CHANGE_DETECTION.value, RouterTask.CHANGE_VQA.value],
        supported_modalities=[InputClass.BI_TEMPORAL.value],
    ),
    _tool(
        "coregister",
        "Optical–SAR coregister",
        "UTILITY",
        description="Resample SAR onto the optical grid over the intersection.",
        supported_tasks=[RouterTask.OPTICAL_SAR_ANALYSIS.value],
        supported_modalities=[InputClass.OPTICAL_SAR.value],
    ),
    _tool(
        "fusion_s1s2",
        "S1/S2 fusion head",
        "FUSION",
        model_name="s1s2-fusion",
        model_version="ben-linear-v1",
        description="Small dual-encoder fusion head for optical + SAR.",
        supported_tasks=[RouterTask.OPTICAL_SAR_ANALYSIS.value],
        supported_modalities=[InputClass.OPTICAL_SAR.value],
    ),
    _tool(
        "agreement",
        "Optical–SAR agreement",
        "FUSION",
        description="Agreement / uncertain overlay between optical and SAR evidence.",
        supported_tasks=[RouterTask.OPTICAL_SAR_ANALYSIS.value],
        supported_modalities=[InputClass.OPTICAL_SAR.value],
    ),
    _tool(
        "geospatial_validator",
        "Geospatial validator",
        "UTILITY",
        description="CRS, overlap, and pair-fitness checks before specialist tools.",
        supported_tasks=_ALL_TASKS,
        supported_modalities=_ALL_CLASSES,
    ),
]


def seed_tool_registry(db: Session) -> list[str]:
    """Insert or update the locked tool catalog. Returns tool_ids that changed."""
    changed: list[str] = []
    existing = {
        row.tool_id: row
        for row in db.execute(select(ToolRegistry)).scalars().all()
    }
    for spec in TOOL_CATALOG:
        row = existing.get(spec["tool_id"])
        if row is None:
            db.add(ToolRegistry(**spec))
            changed.append(spec["tool_id"])
            continue
        dirty = False
        for key, value in spec.items():
            if getattr(row, key) != value:
                setattr(row, key, value)
                dirty = True
        if dirty:
            changed.append(spec["tool_id"])
    db.commit()
    return changed


if __name__ == "__main__":
    from backend.database import SessionLocal

    session = SessionLocal()
    try:
        updated = seed_tool_registry(session)
        print(f"seeded {len(TOOL_CATALOG)} tools; changed={updated or 'none'}")
    finally:
        session.close()
