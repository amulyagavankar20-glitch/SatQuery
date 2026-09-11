"""
SatQuery AI — Deterministic Input Classifier
"""
from typing import Any
from pathlib import Path

from backend.schemas import (
    InputClass,
    InputClassification,
    Modality,
    SpatialRelationship,
    TemporalRelationship,
)
from backend.services.input_analyzer import InputAnalyzer
from src.logger import logging


class InputClassifier:
    """
    Deterministic Input Classifier for SatQuery AI.
    
    Classifies the uploaded input configuration into exactly one of:
      1. SINGLE_OPTICAL
      2. SINGLE_SAR
      3. BI_TEMPORAL
      4. OPTICAL_SAR
      
    Or returns a structured validation/refusal state with detailed diagnostics.
    """

    def __init__(self, min_overlap_threshold: float = 0.10):
        self.min_overlap_threshold = min_overlap_threshold
        self.analyzer = InputAnalyzer()

    def classify(
        self,
        assets: list[str | Path | dict[str, Any]],
        analysis_metadata: dict[str, Any] | None = None,
    ) -> InputClassification:
        """
        Classify input configuration using metadata from InputAnalyzer.
        """
        if not assets:
            return InputClassification(
                input_class=None,
                valid=False,
                refusal_reason="No input assets provided.",
                validation_messages=["Input asset list is empty."],
                details={"asset_count": 0},
            )

        # Analyze inputs if not pre-computed
        if analysis_metadata is None:
            try:
                analysis = self.analyzer.analyze_inputs(
                    assets=assets,
                    min_overlap_threshold=self.min_overlap_threshold,
                )
            except Exception as e:
                logging.error(f"Error during input analysis: {e}")
                return InputClassification(
                    input_class=None,
                    valid=False,
                    refusal_reason=f"Input analysis failed: {str(e)}",
                    validation_messages=[f"Analysis exception: {str(e)}"],
                    details={"error": str(e)},
                )
        else:
            analysis = analysis_metadata

        asset_count = analysis.get("asset_count", len(assets))
        analyzed_assets = analysis.get("assets", [])
        spatial_rel: SpatialRelationship | None = analysis.get("spatial_relationship")
        temporal_rel: TemporalRelationship | None = analysis.get("temporal_relationship")

        asset_ids = [str(a.get("asset_id", f"asset_{i+1}")) for i, a in enumerate(analyzed_assets)]
        modalities = [str(a.get("modality", "UNKNOWN")).upper() for a in analyzed_assets]
        acquisition_dates = [a.get("acquired_at") for a in analyzed_assets]

        # -------------------------------------------------------------------
        # Rule 1 & 2: Single Asset Configurations
        # -------------------------------------------------------------------
        if asset_count == 1:
            mod = modalities[0]
            if mod == Modality.OPTICAL.value:
                return InputClassification(
                    input_class=InputClass.SINGLE_OPTICAL,
                    valid=True,
                    asset_ids=asset_ids,
                    modalities=modalities,
                    acquisition_dates=acquisition_dates,
                    validation_messages=["Classified as SINGLE_OPTICAL: Exactly one optical raster."],
                    details={"asset": analyzed_assets[0]},
                )
            elif mod == Modality.SAR.value:
                return InputClassification(
                    input_class=InputClass.SINGLE_SAR,
                    valid=True,
                    asset_ids=asset_ids,
                    modalities=modalities,
                    acquisition_dates=acquisition_dates,
                    validation_messages=["Classified as SINGLE_SAR: Exactly one SAR raster."],
                    details={"asset": analyzed_assets[0]},
                )
            else:
                return InputClassification(
                    input_class=None,
                    valid=False,
                    asset_ids=asset_ids,
                    modalities=modalities,
                    refusal_reason=f"Unsupported sensor modality: '{mod}'",
                    validation_messages=[f"Single asset had unknown or unsupported modality '{mod}'."],
                    details={"modalities": modalities},
                )

        # -------------------------------------------------------------------
        # Rule 3 & 4: Dual Asset Configurations (Pairs)
        # -------------------------------------------------------------------
        elif asset_count == 2:
            m1, m2 = modalities[0], modalities[1]

            # Case A: Cross-modal OPTICAL + SAR
            if (m1 == Modality.OPTICAL.value and m2 == Modality.SAR.value) or (
                m1 == Modality.SAR.value and m2 == Modality.OPTICAL.value
            ):
                has_overlap = bool(spatial_rel and spatial_rel.has_sufficient_overlap)
                overlap_msg = "with verified geographic overlap." if has_overlap else "Note: footprints do not sufficiently overlap."
                return InputClassification(
                    input_class=InputClass.OPTICAL_SAR,
                    valid=True,
                    asset_ids=asset_ids,
                    modalities=modalities,
                    acquisition_dates=acquisition_dates,
                    spatial_relationship=spatial_rel,
                    temporal_relationship=temporal_rel,
                    validation_messages=[
                        f"Classified as OPTICAL_SAR: Paired Optical and SAR imagery ({overlap_msg})"
                    ],
                    details={"spatial_relationship": spatial_rel.model_dump() if spatial_rel else {}},
                )

            # Case B: Homogeneous Pair (BI_TEMPORAL)
            elif m1 == m2 and m1 in (Modality.OPTICAL.value, Modality.SAR.value):
                has_overlap = bool(spatial_rel and spatial_rel.has_sufficient_overlap)
                overlap_msg = "with verified geographic overlap" if has_overlap else "low/no spatial overlap"
                days_str = f"({temporal_rel.days_difference} days apart)" if (temporal_rel and temporal_rel.days_difference is not None) else ""
                return InputClassification(
                    input_class=InputClass.BI_TEMPORAL,
                    valid=True,
                    asset_ids=asset_ids,
                    modalities=modalities,
                    acquisition_dates=acquisition_dates,
                    spatial_relationship=spatial_rel,
                    temporal_relationship=temporal_rel,
                    validation_messages=[
                        f"Classified as BI_TEMPORAL: Paired {m1} imagery {days_str} ({overlap_msg})."
                    ],
                    details={
                        "spatial_relationship": spatial_rel.model_dump() if spatial_rel else {},
                        "temporal_relationship": temporal_rel.model_dump() if temporal_rel else {},
                    },
                )

            else:
                return InputClassification(
                    input_class=None,
                    valid=False,
                    asset_ids=asset_ids,
                    modalities=modalities,
                    refusal_reason=f"Unsupported modality combination: '{m1}' and '{m2}'.",
                    validation_messages=[f"Combination of modalities {modalities} is not supported."],
                    details={"modalities": modalities},
                )

        # -------------------------------------------------------------------
        # Rule 5: Unsupported Configuration (>2 assets)
        # -------------------------------------------------------------------
        else:
            return InputClassification(
                input_class=None,
                valid=False,
                asset_ids=asset_ids,
                modalities=modalities,
                refusal_reason=f"Unsupported asset count ({asset_count}). SatQuery supports 1 or 2 assets.",
                validation_messages=[
                    f"Received {asset_count} images. MVP pipeline supports single or dual-image configurations."
                ],
                details={"asset_count": asset_count},
            )
