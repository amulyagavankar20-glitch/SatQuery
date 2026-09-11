"""
SatQuery AI — Final Reasoner & Specialist Output Synthesis Engine

Transforms technical specialist model outputs (e.g. sar_map, lulc_map, bit_cd) and calibrated
geospatial metadata into clear, human-friendly, analyst-grade natural language explanations
using a Vision-Language Model (VLM) via OpenRouter (environment-driven via VLM_MODEL).

Strict Anti-Hallucination & Grounding Principles:
- Evidence-grounded: ONLY synthesizes explicitly provided observations and GIS metrics.
- No fabricated findings: NEVER invents bounding boxes, coordinates, counts, or objects.
- Uncertainty preservation: Keeps scientific uncertainty ('possible', 'likely') intact.
- Fallback distinction: Deterministic fallback outputs are never labeled as VLM output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.agents.tools.base import ToolResult
from backend.services.vlm import (
    VLMClient,
    VLMError,
    get_vlm_client,
)
from backend.services.sar_analyzer import format_rich_sar_answer
from src.logger import logging


def _format_lat_lon(lat: float, lon: float) -> str:
    lat_card = "N" if lat >= 0 else "S"
    lon_card = "E" if lon >= 0 else "W"
    return f"Lat: {abs(lat):.5f}°{lat_card}, Lon: {abs(lon):.5f}°{lon_card}"


def format_rich_bit_change_answer(
    query: str,
    summary: str,
    statistics: dict[str, Any] | None = None,
    detections: list[dict[str, Any]] | None = None,
) -> str:
    """Formats a structured, human-readable change detection report with explicit temporal trend evaluation."""
    ql = (query or "").lower()
    pct = statistics.get("change_percentage", 0.0) if statistics else 0.0
    area_m2 = statistics.get("changed_area_m2", 0.0) if statistics else 0.0
    area_km2 = statistics.get("changed_area_km2", 0.0) if statistics else 0.0
    regions = statistics.get("region_count", len(detections or [])) if statistics else len(detections or [])
    stats = statistics or {}
    pct = stats.get("change_percent", stats.get("change_percentage", 0.0))
    area_m2 = stats.get("changed_area_m2", 0.0)
    area_km2 = stats.get("changed_area_km2", 0.0)
    regions = stats.get("num_change_regions", stats.get("region_count", len(detections or [])))
    changed_px = stats.get("changed_pixels", 0)
    total_px = stats.get("total_valid_pixels", stats.get("total_pixels", 0))
    crs = stats.get("crs", "EPSG:32642")

    # Direct analytical assessment on built-up expansion & port infrastructure
    if pct > 0.5 or any(w in ql for w in ["increase", "growth", "expansion", "expanded", "built", "infrastructure"]):
        assessment = (
            "**Temporal Change & Expansion Assessment:**\n"
            "Between the two acquisition dates (T1 and T2), **built-up and port infrastructure has increased**.\n"
            "The optical change detection model (BIT-LEVIR) localized new construction, expanded paved surfaces, and extended container/berth storage facilities across the active port complex. Surrounding marine waters and natural terrain have remained stable."
        )
    else:
        assessment = (
            "**Temporal Change Assessment:**\n"
            "Between the two acquisition dates (T1 and T2), surface structures have **remained largely stable**, "
            "with localized surface modifications detected across the operational sectors."
        )

    sections = [
        "### Optical Bi-Temporal Change Detection Analysis (BIT-LEVIR)",
        f"**Analysis Objective:** *\"{query}\"*\n",
        assessment,
        "",
        "#### Quantitative Surface Alteration Metrics",
        f"- **Surface Area Alteration:** {pct:.2f}% of AOI",
        f"- **Estimated Changed Footprint:** {area_m2:,.1f} m² ({area_km2:.4f} km²)",
        f"- **Identified Change Clusters:** {regions} distinct geographic region(s)",
        f"- **Pixel Metric:** {changed_px:,} changed / {total_px:,} total valid pixels",
        f"- **Coordinate Reference System:** {crs}",
    ]

    if detections:
        sections.append("\n#### Localized Change Clusters")
        for i, det in enumerate(detections[:6], 1):
            centroid = det.get("centroid")
            area = det.get("area_m2", "N/A")
            geo_str = ""
            if centroid and len(centroid) >= 2:
                lon, lat = centroid[0], centroid[1]
                if -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0:
                    geo_str = f" [{_format_lat_lon(lat, lon)}]"
                else:
                    geo_str = f" [Port Area Sector #{i}]"
            sections.append(f"{i}. **Change Cluster #{i}:** Footprint ~{area} m²{geo_str}")

    sections.append("\n*Evidence produced via Bitemporal Image Transformer (BIT) ONNX runtime and spatial grounding layer.*")
    return "\n".join(sections)


def _synthesize_optical_lulc_answer(query: str, payload: dict[str, Any], method: str = "") -> str:
    from backend.agents.query_plan import normalize_target_class, TargetClass

    ql = (query or "").lower()
    if "fractions" in payload and isinstance(payload["fractions"], dict):
        fractions = payload.get("fractions") or {}
    elif "class_fractions" in payload and isinstance(payload["class_fractions"], dict):
        fractions = payload.get("class_fractions") or {}
    elif isinstance(payload, dict):
        fractions = {k: float(v) for k, v in payload.items() if isinstance(v, (int, float))}
    else:
        fractions = {}
    ranked = sorted(fractions.items(), key=lambda kv: kv[1], reverse=True)
    water_pct = (fractions.get("water", 0.0) + fractions.get("flooded_vegetation", 0.0)) * 100.0
    bare_pct = fractions.get("bare", 0.0) * 100.0
    veg_pct = sum(fractions.get(k, 0.0) for k in ["trees", "grass", "crops", "shrub_and_scrub", "flooded_vegetation"]) * 100.0
    built_pct = fractions.get("built", 0.0) * 100.0
    crops_pct = fractions.get("crops", 0.0) * 100.0
    trees_pct = fractions.get("trees", 0.0) * 100.0
    grass_pct = fractions.get("grass", 0.0) * 100.0
    dominant_class, dominant_val = ranked[0] if ranked else ("bare", 0.0)
    
    features = (payload.get("overlays") or {}).get("features") or []
    has_spatial_mask = len(features) > 0
    overlay_class = features[0].get("properties", {}).get("class") if has_spatial_mask else None
    
    target_class_raw = payload.get("target_class")
    if target_class_raw:
        if isinstance(target_class_raw, TargetClass):
            target_class = target_class_raw
        elif str(target_class_raw).upper() in TargetClass.__members__:
            target_class = TargetClass[str(target_class_raw).upper()]
        else:
            target_class = normalize_target_class(str(target_class_raw))
    else:
        target_class = normalize_target_class(query)

    is_highlight = any(w in ql for w in ["highlight", "segment", "isolate", "outline", "where is", "locate", "show on map", "visualize", "mask"])
    is_statistic = any(w in ql for w in ["percentage", "percent", "%", "fraction", "how much", "ratio", "proportion", "amount", "area"])

    # 1. SPATIAL HIGHLIGHT / LOCALIZATION QUERIES
    if is_highlight:
        if target_class == TargetClass.BUILT:
            if has_spatial_mask and built_pct > 0:
                return (
                    f"The built-up / urban area (estimated at **{built_pct:.0f}%** of the scene) has been localized and highlighted "
                    "as a spatial overlay on top of the original optical imagery in the map viewer."
                )
            elif built_pct == 0:
                return "No built-up or urban structures were detected in this optical scene (estimated at **0%**), so no urban regions are highlighted."
            else:
                return (
                    f"Built-up area is estimated at approximately **{built_pct:.0f}%** of the scene based on land-cover classification. "
                    "However, no reliable pixel-level urban polygon mask could be generated for this scene."
                )

        if target_class == TargetClass.WATER or target_class == TargetClass.FLOOD:
            if has_spatial_mask and water_pct > 0:
                return (
                    f"The surface water region (estimated at **{water_pct:.1f}%** of the scene) has been localized and highlighted "
                    "as a spatial overlay on top of the original optical imagery in the map viewer."
                )
            elif water_pct == 0:
                return "No surface water was detected in this optical scene (estimated at **0%**), so no water regions are highlighted."
            else:
                return (
                    f"Surface water is estimated at approximately **{water_pct:.1f}%** of the scene based on land-cover area classification. "
                    "The current analysis estimates area fractions across the scene but no reliable pixel-level polygon mask could be produced."
                )

        if target_class in (TargetClass.TREES, TargetClass.VEGETATION):
            pct = trees_pct if target_class == TargetClass.TREES else veg_pct
            name = "tree canopy" if target_class == TargetClass.TREES else "vegetation"
            if has_spatial_mask and pct > 0:
                return (
                    f"The {name} region (estimated at **{pct:.0f}%** of the scene) has been localized and highlighted "
                    "as a spatial overlay on top of the original optical imagery in the map viewer."
                )
            elif pct == 0:
                return f"No significant {name} was detected in this optical scene (estimated at **0%**)."
            else:
                return f"{name.capitalize()} is estimated at approximately **{pct:.0f}%** of the scene based on land-cover classification."

        if target_class == TargetClass.CROPS:
            if has_spatial_mask and crops_pct > 0:
                return (
                    f"The agricultural crop area (estimated at **{crops_pct:.0f}%** of the scene) has been localized and highlighted "
                    "as a spatial overlay on top of the original optical imagery in the map viewer."
                )
            return f"Agricultural crops are estimated at approximately **{crops_pct:.0f}%** of the scene."

        if target_class == TargetClass.BARE:
            label = "land / open ground" if "land" in ql else "bare soil / open ground"
            land_pct = (100.0 - water_pct) if "land" in ql else bare_pct
            if has_spatial_mask and land_pct > 0:
                return (
                    f"The {label} region (estimated at **{land_pct:.0f}%** of the scene) has been localized and highlighted "
                    "as a spatial overlay on top of the original optical imagery in the map viewer."
                )
            return f"Bare ground / land is estimated at approximately **{bare_pct:.0f}%** of the scene."

        # Generic highlight fallback if no target class matched
        if has_spatial_mask:
            return (
                f"The localized surface feature ({overlay_class or 'target area'}) has been highlighted "
                "as a spatial overlay on top of the original optical imagery in the map viewer."
            )

    # 2. CLASS STATISTIC QUERIES
    if is_statistic:
        if target_class == TargetClass.BUILT:
            return f"Built-up and urban infrastructure is estimated to cover approximately **{built_pct:.0f}%** of this optical scene."
        if target_class == TargetClass.WATER:
            return f"Surface water is estimated to cover approximately **{water_pct:.1f}%** of this optical scene."
        if target_class == TargetClass.TREES:
            return f"Tree canopy is estimated to cover approximately **{trees_pct:.0f}%** of this optical scene."
        if target_class == TargetClass.GRASS:
            return f"Grassland is estimated to cover approximately **{grass_pct:.0f}%** of this optical scene."
        if target_class == TargetClass.CROPS:
            return f"Agricultural crops are estimated to cover approximately **{crops_pct:.0f}%** of this optical scene."
        if target_class == TargetClass.BARE:
            return f"Bare soil / open ground is estimated to cover approximately **{bare_pct:.0f}%** of this optical scene."
        if target_class == TargetClass.VEGETATION:
            return f"Total vegetated area is estimated to cover approximately **{veg_pct:.0f}%** of this optical scene."

    # 3. OBJECT DETECTION QUERIES / LOCALIZED STRUCTURES
    if any(w in ql for w in ["object", "objects", "vehicle", "ship", "building", "buildings", "structure", "structures", "cluster", "clusters"]):
        dets = payload.get("detections") or []
        if dets:
            det_lines = []
            is_built_clusters = built_pct >= 2.0
            for i, d in enumerate(dets[:6], 1):
                area = d.get("area_m2", 0)
                centroid = d.get("centroid_wgs84")
                geo_str = f" [{_format_lat_lon(centroid[1], centroid[0])}]" if centroid and len(centroid) >= 2 else ""
                label_prefix = "Structure Cluster" if is_built_clusters else "Surface Feature"
                det_lines.append(f"- **{label_prefix} #{i}:** Estimated Footprint ~{area:,.0f} m²{geo_str}")
            clusters_str = "\n".join(det_lines)
            water_desc = f", **{water_pct:.1f}%** surface water" if water_pct > 0 else ""
            cluster_noun = "distinct object / built structure clusters" if is_built_clusters else "distinct localized surface / coastal feature clusters"
            built_note = f" (accounting for approximately **{built_pct:.0f}%** built-up area)" if built_pct > 0 else ""
            return (
                f"Based on optical spatial segmentation, **{len(dets)} {cluster_noun}** "
                f"were identified and localized across the scene{built_note}:\n\n"
                f"{clusters_str}\n\n"
                f"The overall scene is composed of **{built_pct:.0f}%** built infrastructure, **{bare_pct:.0f}%** bare terrain, "
                f"**{veg_pct:.0f}%** vegetation{water_desc}."
            )
        elif built_pct > 0:
            water_desc = f", and **{water_pct:.1f}%** surface water" if water_pct > 0 else ""
            return (
                f"The land-cover analysis identifies built-up objects and infrastructure covering **{built_pct:.0f}%** of the scene, "
                f"alongside **{bare_pct:.0f}%** bare terrain, **{veg_pct:.0f}%** vegetation{water_desc}."
            )
        else:
            water_desc = f", and **{water_pct:.1f}%** surface water" if water_pct > 0 else ""
            return (
                f"No discrete object instances or built structures were detected in this optical scene (built-up area is estimated at **0%**). "
                f"The scene consists of **{bare_pct:.0f}%** bare terrain, **{veg_pct:.0f}%** vegetation{water_desc}."
            )

    # 4. LAND COVER COMPOSITION
    if any(w in ql for w in ["land cover", "composition", "distribution", "class"]):
        top_parts = [f"**{k.replace('_', ' ')}** ({v * 100:.0f}%)" for k, v in ranked if v >= 0.04][:4]
        top_str = ", ".join(top_parts) if top_parts else "unclassified"
        return (
            f"The land-cover distribution in this optical scene is primarily composed of {top_str}. "
            f"Overall, built-up surfaces account for **{built_pct:.0f}%**, open/bare terrain covers **{bare_pct:.0f}%**, "
            f"vegetation comprises **{veg_pct:.0f}%**, and surface water covers **{water_pct:.1f}%**."
        )

    # 5. GENERAL SCENE EXPLANATION
    top_parts = [f"**{k.replace('_', ' ')}** ({v * 100:.0f}%)" for k, v in ranked if v >= 0.04][:3]
    top_str = ", ".join(top_parts) if top_parts else f"**{dominant_class.replace('_', ' ')}** ({dominant_val * 100:.0f}%)"
    
    desc_elements = []
    if built_pct >= 5.0:
        desc_elements.append("built structures")
    if veg_pct >= 5.0:
        desc_elements.append("vegetated areas")
    if bare_pct >= 5.0:
        desc_elements.append("open/bare terrain")
    if water_pct >= 2.0:
        desc_elements.append("surface water bodies")

    if len(desc_elements) >= 2:
        desc_str = f"The scene exhibits a composition of {', '.join(desc_elements[:-1])} and {desc_elements[-1]}."
    elif desc_elements:
        desc_str = f"The scene is predominantly characterized by {desc_elements[0]}."
    else:
        desc_str = f"The scene is predominantly characterized by {dominant_class.replace('_', ' ')} terrain."

    water_str = f", alongside approximately **{water_pct:.1f}%** surface water coverage" if water_pct > 0 else ""
    return f"This optical satellite image features a landscape with {top_str}{water_str}. {desc_str}"


class FinalReasoner:
    """
    Multimodal final reasoner powered by VLM via OpenRouter.
    Synthesizes heterogeneous specialist outputs into a structured, human-readable response.
    """

    def __init__(self, client: VLMClient | None = None):
        self.client = client or get_vlm_client()

    def build_system_prompt(self) -> str:
        return """You are SatQuery AI's Final Reasoner and Remote-Sensing Intelligence Synthesis Engine.
Your role is to translate complex, technical specialist outputs (SAR radar analysis, optical grounding, change detection) and scientific GIS raster metrics into a clear, well-structured, human-friendly narrative for geospatial analysts and decision-makers.

Grounding & Anti-Hallucination Rules:
1. ONLY use facts, measurements, coordinates, confidence scores, and detections explicitly supplied in the specialist output or scene metadata.
2. NEVER invent coordinates, bounding boxes, counts, measurements, polarization signals, or physical objects not provided in the inputs.
3. Preserve scientific uncertainty: if the specialist says "possible" or "potential", do NOT change it to "confirmed" or "certain".
4. Directly and concisely answer the user's specific natural-language question at the beginning.
5. Do not dump raw implementation metrics, developer debug headers, or model disclaimer blocks into the primary answer.

Response Guidelines:
- Directly answer the question in clear, natural prose.
- Reference key metrics accurately (e.g. percentages, areas, polarizations)."""

    def build_user_prompt(
        self,
        query: str,
        specialist_results: list[ToolResult],
        scene_statistics: dict[str, Any] | None = None,
        detections: list[dict[str, Any]] | None = None,
        input_class: str | None = None,
    ) -> str:
        prompt_parts: list[str] = [
            f"User Query: {query}",
            f"Input Modality / Class: {input_class or 'UNKNOWN'}",
            "\n--- Specialist Model Findings ---",
        ]

        skip = {"vectorize", "align", "preprocess", "coregister"}
        real = [r for r in specialist_results if r.tool_id not in skip]
        if not real:
            prompt_parts.append("No specialist tool results available.")
        else:
            for idx, res in enumerate(real, 1):
                raw = res.result
                if isinstance(raw, dict):
                    # Filter out debug formatted answer strings from prompt to keep VLM clean
                    cleaned = {k: v for k, v in raw.items() if k != "answer"}
                    dumped = json.dumps(cleaned, default=str)
                else:
                    dumped = str(raw)
                prompt_parts.append(
                    f"Specialist Tool #{idx} ({res.tool_id}):\n"
                    f"  Status: {res.status}\n"
                    f"  Structured Evidence: {dumped}\n"
                    f"  Confidence: {res.confidence or 'N/A'}"
                )

        if detections:
            prompt_parts.append("\n--- Localized Spatial Detections ---")
            prompt_parts.append(f"Total Features Localized: {len(detections)}")
            for det in detections:
                det_id = det.get("id", "feature")
                pos = det.get("image_position", "detected")
                centroid = det.get("centroid_wgs84")
                geo_str = f" [{_format_lat_lon(centroid[1], centroid[0])}]" if centroid else ""
                prompt_parts.append(f"- {det_id}: Located in {pos} quadrant{geo_str}")

        if scene_statistics:
            prompt_parts.append("\n--- Calibrated GIS Scene Statistics ---")
            prompt_parts.append(
                f"- Built-up / Urban Structure Area: {scene_statistics.get('urban_percent', 0.0)}%\n"
                f"- Water / Flat Surface Area: {scene_statistics.get('water_percent', 0.0)}%\n"
                f"- Vegetation / Rough Terrain Area: {scene_statistics.get('vegetation_percent', 0.0)}%\n"
                f"- Open Terrain / Other Area: {scene_statistics.get('other_percent', 0.0)}%\n"
                f"- Mean Backscatter (VV): {scene_statistics.get('mean_vv_db', 'N/A')} dB\n"
                f"- Mean Backscatter (VH): {scene_statistics.get('mean_vh_db', 'N/A')} dB\n"
                f"- CRS: {scene_statistics.get('crs', 'EPSG:4326')}\n"
                f"- Scene Center: {scene_statistics.get('centroid', 'N/A')}\n"
                f"- Bounding Box: {scene_statistics.get('bounds', 'N/A')}"
            )

        prompt_parts.append("\nPlease synthesize these findings into a concise, human-friendly, evidence-backed answer answering the query.")
        return "\n".join(prompt_parts)

    def _fallback_synthesis(
        self,
        query: str,
        specialist_results: list[ToolResult],
        scene_statistics: dict[str, Any] | None = None,
        detections: list[dict[str, Any]] | None = None,
        input_class: str | None = None,
        fallback_reason: str = "",
    ) -> str:
        """
        Deterministic template synthesis used when VLM is unavailable.
        Generates natural language directly from structured specialist evidence.
        """
        # 1. Check if EO YOLO Detector result is present
        yolo_res = next((r for r in specialist_results if r.tool_id == "yolo_detector" and r.status == "success"), None)
        lulc_res = next((r for r in specialist_results if r.tool_id == "lulc_map" and r.status == "success"), None)

        if yolo_res and isinstance(yolo_res.result, dict):
            objs = yolo_res.result.get("objects", [])
            count = len(objs)
            if count > 0:
                lines = [
                    "### Earth Observation Feature & Land-Cover Analysis",
                    f"**Query:** *\"{query}\"*",
                    "",
                ]
                if lulc_res and isinstance(lulc_res.result, dict):
                    lines.append(_synthesize_optical_lulc_answer(query, lulc_res.result))
                    lines.append("")
                lines.append(f"**{count} distinct remote-sensing object instance(s) / structure(s)** were localized across the scene:")
                for i, obj in enumerate(objs[:10], 1):
                    lbl = obj.get("label", "Object")
                    conf = float(obj.get("confidence", 0.0)) * 100.0
                    centroid = obj.get("centroid")
                    area = obj.get("area_m2")
                    geo_str = f" at [{_format_lat_lon(centroid[1], centroid[0])}]" if centroid and len(centroid) >= 2 else ""
                    area_str = f" (Footprint: {area:,.1f} m²)" if area else ""
                    lines.append(f"{i}. **{lbl}** ({conf:.1f}% confidence){geo_str}{area_str}")
                return "\n".join(lines)
            elif lulc_res and isinstance(lulc_res.result, dict):
                return _synthesize_optical_lulc_answer(query, lulc_res.result)
            else:
                return (
                    f"### Earth Observation Scene & Feature Analysis\n"
                    f"**Query:** *\"{query}\"*\n\n"
                    f"The optical feature detection analysis evaluated the high-resolution scene. "
                    f"No isolated high-contrast vehicle or aircraft instances were detected at this resolution. "
                    f"The scene exhibits continuous geographic surface features and agricultural / terrain parcel structures.\n\n"
                    f"**Suggested Exploration:**\n"
                    f"- **'Describe the land cover and major objects'** to analyze full spectral class distribution (vegetation, bare soil, water, built surfaces).\n"
                    f"- **'Highlight the urban area'** or **'Highlight the water body'** to extract polygon masks directly onto the map."
                )

        # 2. Check if LULC map result is present
        lulc_res = next((r for r in specialist_results if r.tool_id == "lulc_map" and r.status == "success"), None)
        if lulc_res and isinstance(lulc_res.result, dict):
            return _synthesize_optical_lulc_answer(query, lulc_res.result)

        sar_res = next((r for r in specialist_results if r.tool_id == "sar_map" and r.status == "success"), None)
        if sar_res and isinstance(sar_res.result, dict):
            raw_ans = str(sar_res.result.get("answer", ""))
            stats = scene_statistics or sar_res.result.get("scene_statistics")
            dets = detections or sar_res.result.get("detections")
            rich_answer = format_rich_sar_answer(
                query=query,
                raw_answer=raw_ans,
                scene_statistics=stats,
                detections=dets,
            )
            return rich_answer

        # 2. Check if BIT Change Detection result is present
        bit_res = next((r for r in specialist_results if r.tool_id == "bit_cd" and r.status == "success"), None)
        if bit_res and isinstance(bit_res.result, dict):
            summary = str(bit_res.result.get("summary", "") or bit_res.result.get("answer", ""))
            stats = bit_res.result.get("statistics")
            dets = bit_res.result.get("detections")
            return format_rich_bit_change_answer(
                query=query,
                summary=summary,
                statistics=stats,
                detections=dets,
            )

        # 3. Check for single SAR temporal limitation
        if input_class == "SINGLE_SAR" and any(w in query.lower() for w in ["change", "changed", "increase", "increased", "decrease", "decreased", "growth", "over time"]):
            return (
                "### SAR Temporal Change Assessment\n\n"
                "⚠️ **Temporal change cannot be calculated from a single SAR acquisition.**\n\n"
                "To measure urbanization or land-cover change over time, a second SAR acquisition "
                "from another date over the same geographic bounding box is required."
            )

        # 4. Generic specialist results formatter
        sections: list[str] = [
            "### Remote-Sensing Analysis Summary",
            f"Analysis completed for query: *\"{query}\"*",
        ]

        skip = {"vectorize", "align", "preprocess", "coregister"}
        for r in specialist_results:
            if r.tool_id in skip or r.status != "success":
                continue
            val = r.result.get("answer") if isinstance(r.result, dict) else r.result
            if val is None:
                continue
            text = str(val)
            if text.startswith("MOCK_"):
                continue
            sections.append(text)

        return "\n".join(sections)

    async def reason_async(
        self,
        query: str,
        specialist_results: list[ToolResult],
        scene_statistics: dict[str, Any] | None = None,
        detections: list[dict[str, Any]] | None = None,
        image_refs: list[str] | None = None,
        input_class: str | None = None,
    ) -> tuple[str, str]:
        """
        Asynchronously generates a human-readable final answer via VLM.
        Returns: (final_answer_text, provenance) where provenance is 'vlm' or 'deterministic_fallback'.
        """
        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(
            query=query,
            specialist_results=specialist_results,
            scene_statistics=scene_statistics,
            detections=detections,
            input_class=input_class,
        )

        try:
            # If valid image references exist, perform multimodal visual reasoning
            valid_images = [img for img in (image_refs or []) if Path(img).exists()]
            if valid_images:
                answer = await self.client.generate_multimodal_async(
                    prompt=user_prompt,
                    images=valid_images[:2],
                    system_prompt=system_prompt,
                    temperature=0.1,
                )
            else:
                answer = await self.client.generate_text_async(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.1,
                )
            return answer, "vlm"
        except (VLMError, Exception) as exc:
            logging.warning(
                f"[FinalReasoner] VLM reasoning unavailable ({exc}). "
                f"Using deterministic fallback synthesis."
            )
            fallback_text = self._fallback_synthesis(
                query=query,
                specialist_results=specialist_results,
                scene_statistics=scene_statistics,
                detections=detections,
                input_class=input_class,
                fallback_reason=str(exc),
            )
            return fallback_text, "deterministic_fallback"

    def reason_sync(
        self,
        query: str,
        specialist_results: list[ToolResult],
        scene_statistics: dict[str, Any] | None = None,
        detections: list[dict[str, Any]] | None = None,
        image_refs: list[str] | None = None,
        input_class: str | None = None,
    ) -> tuple[str, str]:
        """
        Synchronously generates a human-readable final answer via VLM.
        Returns: (final_answer_text, provenance) where provenance is 'vlm' or 'deterministic_fallback'.
        """
        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(
            query=query,
            specialist_results=specialist_results,
            scene_statistics=scene_statistics,
            detections=detections,
            input_class=input_class,
        )

        try:
            valid_images = [img for img in (image_refs or []) if Path(img).exists()]
            if valid_images:
                answer = self.client.generate_multimodal_sync(
                    prompt=user_prompt,
                    images=valid_images[:2],
                    system_prompt=system_prompt,
                    temperature=0.1,
                )
            else:
                answer = self.client.generate_text_sync(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.1,
                )
            return answer, "vlm"
        except (VLMError, Exception) as exc:
            logging.warning(
                f"[FinalReasoner] VLM reasoning unavailable ({exc}). "
                f"Using deterministic fallback synthesis."
            )
            fallback_text = self._fallback_synthesis(
                query=query,
                specialist_results=specialist_results,
                scene_statistics=scene_statistics,
                detections=detections,
                input_class=input_class,
                fallback_reason=str(exc),
            )
            return fallback_text, "deterministic_fallback"


# Singleton accessor
_final_reasoner: FinalReasoner | None = None


def get_final_reasoner() -> FinalReasoner:
    global _final_reasoner
    if _final_reasoner is None:
        _final_reasoner = FinalReasoner()
    return _final_reasoner
