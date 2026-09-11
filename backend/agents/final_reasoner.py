"""
SatQuery AI — Final Reasoner & Specialist Output Synthesis Engine

Transforms technical specialist model outputs (e.g. SARChat, GeoChat) and calibrated
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


def format_rich_bit_change_answer(
    query: str,
    summary: str,
    statistics: dict[str, Any] | None = None,
    detections: list[dict[str, Any]] | None = None,
) -> str:
    """Formats a structured, human-readable change detection report."""
    sections = [
        "### Optical Bi-Temporal Change Detection Analysis (BIT-LEVIR)",
        f"**Analysis Objective:** *\"{query}\"*\n",
    ]
    if summary:
        sections.append(f"**Observation Summary:**\n{summary}\n")

    if statistics:
        pct = statistics.get("change_percentage", 0.0)
        area_m2 = statistics.get("changed_area_m2", 0.0)
        area_km2 = statistics.get("changed_area_km2", 0.0)
        regions = statistics.get("region_count", len(detections or []))
        total_px = statistics.get("total_pixels", 0)
        changed_px = statistics.get("changed_pixels", 0)
        crs = statistics.get("crs", "EPSG:4326")

        sections.append("#### Quantitative Surface Alteration Metrics")
        sections.append(
            f"- **Surface Area Alteration:** {pct:.2f}% of AOI\n"
            f"- **Estimated Changed Footprint:** {area_m2:,.1f} m² ({area_km2:.4f} km²)\n"
            f"- **Identified Change Clusters:** {regions} distinct geographic region(s)\n"
            f"- **Pixel Metric:** {changed_px:,} changed / {total_px:,} total valid pixels\n"
            f"- **Coordinate Reference System:** {crs}"
        )

    if detections:
        sections.append("\n#### Localized Change Clusters (WGS84 Coordinates)")
        for i, det in enumerate(detections[:10], 1):
            centroid = det.get("centroid")
            area = det.get("area_m2", "N/A")
            geo_str = f" [Lat: {centroid[1]:.5f}°N, Lon: {centroid[0]:.5f}°E]" if centroid and len(centroid) >= 2 else ""
            sections.append(f"{i}. **Cluster #{i}:** Footprint ~{area} m²{geo_str}")

    sections.append("\n*Evidence produced via Bitemporal Image Transformer (BIT) ONNX runtime.*")
    return "\n".join(sections)


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
4. Explain technical remote-sensing terminology in accessible terms (e.g., explain that high double-bounce radar returns indicate man-made structures, or low specular reflection indicates calm water/smooth surfaces).
5. Directly and concisely answer the user's specific natural-language question at the beginning.

Response Format Guidelines:
- **Executive Summary**: Direct answer to the user query in natural language.
- **Key Evidence & Observations**: Bullet points summarizing specialist model findings, backscatter signals, and localized features.
- **Spatial & Geographic Context**: Mention coordinates, scene center, or bounding box if provided in the metadata.
- **Scientific Confidence & Limitations**: Clarify sensor characteristics, radiometric approximations, and potential ambiguities."""

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

        if not specialist_results:
            prompt_parts.append("No specialist tool results available.")
        else:
            for idx, res in enumerate(specialist_results, 1):
                prompt_parts.append(
                    f"Specialist Tool #{idx} ({res.tool_id}):\n"
                    f"  Status: {res.status}\n"
                    f"  Raw Result: {json.dumps(res.result, default=str) if isinstance(res.result, dict) else res.result}\n"
                    f"  Explanation: {res.explanation or 'None'}\n"
                    f"  Confidence: {res.confidence or 'N/A'}"
                )

        if detections:
            prompt_parts.append("\n--- Localized Spatial Detections ---")
            prompt_parts.append(f"Total Features Localized: {len(detections)}")
            for det in detections:
                det_id = det.get("id", "feature")
                pos = det.get("image_position", "detected")
                centroid = det.get("centroid_wgs84")
                geo_str = f" [Lat: {centroid[1]}°N, Lon: {centroid[0]}°E]" if centroid else ""
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

        prompt_parts.append("\nPlease synthesize these findings into a human-friendly, evidence-backed answer.")
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
        Explicitly marked so it is never misrepresented as VLM output.
        """
        # 1. Check if SARChat result is present
        sarchat_res = next((r for r in specialist_results if r.tool_id == "sar_map" and r.status == "success"), None)
        if sarchat_res and isinstance(sarchat_res.result, dict):
            raw_ans = str(sarchat_res.result.get("answer", ""))
            stats = scene_statistics or sarchat_res.result.get("scene_statistics")
            dets = detections or sarchat_res.result.get("detections")
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

        for r in specialist_results:
            if r.status == "success":
                val = r.result.get("answer") if isinstance(r.result, dict) else r.result
                if val:
                    sections.append(f"\n**{r.tool_id.upper()} Observation:**\n{val}")
                if r.explanation:
                    sections.append(f"*{r.explanation}*")

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
