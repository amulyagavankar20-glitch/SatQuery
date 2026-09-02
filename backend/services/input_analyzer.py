"""
SatQuery AI — Input Analyzer Service
"""
from pathlib import Path
from typing import Any

from backend.exceptions import InvalidRasterError, UnsupportedFormatError
from backend.schemas import Modality
from backend.services.geospatial import (
    compute_spatial_overlap,
    compute_temporal_relationship,
    extract_raster_metadata,
)
from backend.utils import validate_file_extension


class InputAnalyzer:
    """
    Analyzes input satellite assets and extracts normalized metadata,
    sensor modalities, spatial relationships, and temporal differences.
    """

    KNOWN_SAR_KEYWORDS = {
        "sentinel-1",
        "s1",
        "risat",
        "terrasar",
        "cosmo",
        "radarsat",
        "alos",
        "sar",
        "vv",
        "vh",
        "hh",
        "hv",
    }

    KNOWN_OPTICAL_KEYWORDS = {
        "sentinel-2",
        "s2",
        "cartosat",
        "landsat",
        "planet",
        "worldview",
        "spot",
        "pleiades",
        "optical",
        "rgb",
        "nir",
        "red",
        "green",
        "blue",
    }

    @classmethod
    def infer_modality(
        cls,
        metadata: dict[str, Any],
        explicit_modality: str | None = None,
    ) -> str:
        """
        Deterministically infer whether an asset is OPTICAL or SAR based on metadata,
        sensor name, band descriptions, and file tags.
        """
        if explicit_modality and explicit_modality.upper() in (Modality.OPTICAL.value, Modality.SAR.value):
            return explicit_modality.upper()

        text_corpus = " ".join([
            metadata.get("filename", ""),
            str(metadata.get("sensor", "")),
            str(metadata.get("driver", "")),
            " ".join(str(d) for d in metadata.get("band_descriptions", [])),
            " ".join(f"{k}:{v}" for k, v in metadata.get("tags", {}).items()),
        ]).lower()

        # Check for SAR signatures
        is_sar = any(kw in text_corpus for kw in cls.KNOWN_SAR_KEYWORDS)
        # Check for Optical signatures
        is_optical = any(kw in text_corpus for kw in cls.KNOWN_OPTICAL_KEYWORDS)

        if is_sar and not is_optical:
            return Modality.SAR.value
        if is_optical and not is_sar:
            return Modality.OPTICAL.value

        # Fallback heuristic based on band count
        count = metadata.get("count", 1)
        if count >= 3:
            return Modality.OPTICAL.value  # RGB / Multi-spectral is predominantly optical
        elif count in (1, 2):
            # 1 or 2 bands: check polarization tags or default to OPTICAL (panchromatic) unless tagged
            if any(pol in text_corpus for pol in ("vv", "vh", "hh", "hv")):
                return Modality.SAR.value
            return Modality.OPTICAL.value

        return Modality.OPTICAL.value

    def analyze_asset(
        self,
        asset_input: str | Path | dict[str, Any],
        asset_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyze a single asset file or dictionary input and produce normalized metadata.
        """
        if isinstance(asset_input, (str, Path)):
            path = Path(asset_input)
            if not validate_file_extension(path.name):
                raise UnsupportedFormatError(f"Unsupported raster file extension: {path.name}")
            
            raw_meta = extract_raster_metadata(path)
            asset_meta = raw_meta.copy()
            asset_meta["asset_id"] = asset_id or path.stem
            asset_meta["modality"] = self.infer_modality(raw_meta)
            return asset_meta

        elif isinstance(asset_input, dict):
            # Already parsed or structured asset dictionary
            meta = asset_input.copy()
            file_path = meta.get("file_path")
            if file_path and Path(file_path).exists() and ("bounds" not in meta or "crs" not in meta):
                raw_meta = extract_raster_metadata(Path(file_path))
                for k, v in raw_meta.items():
                    if k not in meta or meta[k] is None:
                        meta[k] = v

            meta["asset_id"] = asset_id or meta.get("id") or meta.get("asset_id", "asset_1")
            if "modality" not in meta or not meta["modality"]:
                meta["modality"] = self.infer_modality(meta, meta.get("modality"))
            else:
                meta["modality"] = meta["modality"].upper()

            return meta

        else:
            raise InvalidRasterError(f"Unsupported asset input type: {type(asset_input)}")

    def analyze_inputs(
        self,
        assets: list[str | Path | dict[str, Any]],
        min_overlap_threshold: float = 0.10,
    ) -> dict[str, Any]:
        """
        Analyze a list of input assets, extracting individual metadata and pairwise relationships.
        """
        analyzed_assets = []
        for i, asset in enumerate(assets):
            analyzed = self.analyze_asset(asset, asset_id=f"asset_{i+1}")
            analyzed_assets.append(analyzed)

        count = len(analyzed_assets)
        spatial_rel = None
        temporal_rel = None

        if count == 2:
            a1 = analyzed_assets[0]
            a2 = analyzed_assets[1]

            b1 = a1.get("bounds") or [0, 0, 1, 1]
            c1 = a1.get("crs") or "EPSG:4326"
            b2 = a2.get("bounds") or [0, 0, 1, 1]
            c2 = a2.get("crs") or "EPSG:4326"

            spatial_rel = compute_spatial_overlap(
                bounds1=b1,
                crs1=c1,
                bounds2=b2,
                crs2=c2,
                min_overlap_threshold=min_overlap_threshold,
            )

            d1 = a1.get("acquired_at")
            d2 = a2.get("acquired_at")
            temporal_rel = compute_temporal_relationship(d1, d2)

        return {
            "asset_count": count,
            "assets": analyzed_assets,
            "spatial_relationship": spatial_rel,
            "temporal_relationship": temporal_rel,
        }
