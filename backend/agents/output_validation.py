"""Stage 4 output validation, confidence aggregation and evidence fusion.

This module provides pure-logic utilities that operate on the final
``GraphState`` produced by the LangGraph execution. It validates that the
generated outputs are compatible with the user's intent, aggregates a
human-readable confidence level (HIGH/MEDIUM/LOW), and fuses the collected
evidence into a structured representation.

GraphState is the canonical TypedDict defined in backend.agents.state.
This module does NOT import from graph.py to avoid circular dependencies.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from backend.agents.tools.base import ToolResult

if TYPE_CHECKING:
    from backend.agents.state import GraphState


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Evidence(BaseModel):
    model_evidence: list[ToolResult] = Field(default_factory=list)
    spatial_evidence: list[dict[str, Any]] = Field(default_factory=list)
    temporal_evidence: list[ToolResult] = Field(default_factory=list)
    cross_modal_evidence: list[ToolResult] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


def _required_tools_for_task(task: str, input_class: str = "") -> list[str]:
    """Return the list of tool identifiers that must have produced results for *task*.

    The mapping mirrors the graph paths defined in ``backend.agents.graph`` and
    takes into account whether the modality is SAR or Optical.
    """
    if input_class in ("SINGLE_SAR", "InputClass.SINGLE_SAR"):
        sar_mapping: dict[str, list[str]] = {
            "SINGLE_VQA":           ["sar_map"],
            "CAPTIONING":           ["sar_map"],
            "GROUNDING":            ["sar_map", "grounding"],
        }
        if task in sar_mapping:
            return sar_mapping[task]

    mapping: dict[str, list[str]] = {
        "SINGLE_VQA":           ["lulc_map"],
        "CAPTIONING":           ["lulc_map"],
        "GROUNDING":            ["lulc_map"],
        "CHANGE_DETECTION":     ["bit_cd"],
        "CHANGE_VQA":           ["bit_cd"],
        "OPTICAL_SAR_ANALYSIS": ["coregister", "fusion_s1s2", "agreement"],
    }
    return mapping.get(task, [])


def _collect_evidence(state: "GraphState") -> Evidence:
    ev = Evidence()
    for tr in state.get("specialist_results", []):  # type: ignore[union-attr]
        tool_id = getattr(tr, "tool_id", None) or (tr.get("tool_id") if isinstance(tr, dict) else None)
        spatial_refs = getattr(tr, "spatial_refs", None) or (tr.get("spatial_refs") if isinstance(tr, dict) else None)
        # Model evidence – tools that produce a textual or semantic answer
        if tool_id in {"sar_map", "lulc_map"}:
            ev.model_evidence.append(tr)
        # Temporal evidence – tools that operate on a time series
        if tool_id in {"bit_cd", "vectorize", "align"}:
            ev.temporal_evidence.append(tr)
        # Cross-modal evidence – fusion and agreement tools
        if tool_id in {"fusion_s1s2", "agreement", "coregister"}:
            ev.cross_modal_evidence.append(tr)
        # Spatial evidence – any spatial_refs attached to the result
        if spatial_refs:
            ev.spatial_evidence.extend(spatial_refs)  # type: ignore[arg-type]
    return ev


def _validate_spatial_refs(spatial_refs: list[dict[str, Any]]) -> bool:
    """Lightweight geometry validity check.

    Each entry must contain a ``type`` (e.g. "Polygon") and ``coordinates``.
    """
    for geo in spatial_refs:
        if not isinstance(geo, dict):
            return False
        if "type" not in geo or "coordinates" not in geo:
            return False
        if not geo["type"] or not geo["coordinates"]:
            return False
    return True


def _aggregate_signals(state: "GraphState", evidence: Evidence) -> list[str]:
    """Derive a list of qualitative signals from the execution.

    Signals are simple strings that later map to a confidence level.
    Confidence MUST NOT be presented as a calibrated probability.
    """
    signals: list[str] = []

    # Pair fitness – explicit flag set during metadata / pair-fitness processing
    pair_fitness = state.get("pair_fitness", {})  # type: ignore[union-attr]
    if isinstance(pair_fitness, dict) and pair_fitness.get("fitness") == "high":
        signals.append("pair_fitness")

    # Tool success – all required tools completed without error
    task = state.get("detected_task", "") or ""
    raw_input_class = state.get("input_class", "")
    input_class_str = raw_input_class.value if hasattr(raw_input_class, "value") else str(raw_input_class or "")
    required = _required_tools_for_task(task, input_class_str)
    tool_ids = {
        getattr(tr, "tool_id", None) or (tr.get("tool_id") if isinstance(tr, dict) else None)
        for tr in state.get("specialist_results", [])
        if (getattr(tr, "status", None) or (tr.get("status") if isinstance(tr, dict) else None)) == "success"
    } - {None}
    if required and set(required).issubset(tool_ids):
        signals.append("tool_success")

    # Spatial consistency – at least one valid spatial evidence entry
    if evidence.spatial_evidence and _validate_spatial_refs(evidence.spatial_evidence):  # type: ignore[arg-type]
        signals.append("spatial_consistency")

    # Cross-modal agreement – both fusion and agreement ran successfully
    if "fusion_s1s2" in tool_ids and "agreement" in tool_ids:
        signals.append("cross_modal_agreement")

    # Evidence completeness – we have at least one specialist evidence item
    if evidence.model_evidence or evidence.temporal_evidence or evidence.cross_modal_evidence:
        signals.append("evidence_completeness")

    return signals


def _map_signals_to_confidence(signals: list[str]) -> ConfidenceLevel:
    """Map collected signals to a qualitative confidence level.

    * HIGH   – all key signals present.
    * MEDIUM – at least half present.
    * LOW    – otherwise.

    The mapping is transparent and task-aware (signals carry semantic meaning).
    """
    key_signals = {
        "pair_fitness",
        "tool_success",
        "spatial_consistency",
        "cross_modal_agreement",
        "evidence_completeness",
    }
    present = len(set(signals) & key_signals)
    total = len(key_signals)
    if present == total:
        return ConfidenceLevel.HIGH
    if present >= total // 2:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


class ValidationResult(BaseModel):
    is_valid: bool
    confidence: ConfidenceLevel
    evidence: Evidence
    messages: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


def validate_output(state: "GraphState") -> ValidationResult:
    """Perform Stage 4 output validation.

    Checks:
    1. Intent/task compatibility via structured intent/task specification.
    2. Required tool outputs exist.
    3. Each ToolResult conforms to the schema (status, result field).
    4. Spatial evidence validity where applicable.
    5. Geometry validity via ``_validate_spatial_refs``.
    6. Evidence completeness.
    7. Cross-modal agreement where required.

    Intent mismatch is detected by comparing the *structured* intent recorded
    in the route/metadata against the detected task.  Simple string matching
    against the raw user query is NOT used.
    """
    messages: list[str] = []

    # 1. Intent / task compatibility using structured route information
    task = state.get("detected_task", "") or ""
    route = state.get("route")
    if route is not None:
        route_task = getattr(route, "task", None)
        if route_task is not None and hasattr(route_task, "value"):
            if route_task.value != task:
                messages.append(
                    f"Intent/task mismatch: Qwen routed '{route_task.value}' "
                    f"but executor received '{task}'."
                )
                return ValidationResult(
                    is_valid=False,
                    confidence=ConfidenceLevel.LOW,
                    evidence=Evidence(),
                    messages=messages,
                )

    raw_input_class = state.get("input_class", "")
    input_class_str = raw_input_class.value if hasattr(raw_input_class, "value") else str(raw_input_class or "")
    required_tools = _required_tools_for_task(task, input_class_str)
    available_tools = {
        getattr(tr, "tool_id", None) or (tr.get("tool_id") if isinstance(tr, dict) else None)
        for tr in state.get("specialist_results", [])
    } - {None}
    missing = set(required_tools) - available_tools
    if missing:
        messages.append(f"Missing required tool results: {', '.join(sorted(missing))}.")

    # 3. Tool result schema validation
    for tr in state.get("specialist_results", []):  # type: ignore[union-attr]
        status = getattr(tr, "status", None) or (tr.get("status") if isinstance(tr, dict) else None)
        tool_id = getattr(tr, "tool_id", None) or (tr.get("tool_id") if isinstance(tr, dict) else None)
        result_val = getattr(tr, "result", None) if hasattr(tr, "result") else (tr.get("result") if isinstance(tr, dict) else None)
        if status != "success":
            messages.append(f"Tool '{tool_id}' reported status '{status}'.")
        if result_val is None and status == "success":
            messages.append(f"Tool '{tool_id}' produced no result despite status=success.")

    # 4-5. Spatial evidence validation
    evidence = _collect_evidence(state)
    if evidence.spatial_evidence:
        if not _validate_spatial_refs(evidence.spatial_evidence):  # type: ignore[arg-type]
            messages.append("Spatial evidence contains invalid geometry.")

    # 6. Evidence completeness
    has_evidence = bool(evidence.model_evidence or evidence.temporal_evidence or evidence.cross_modal_evidence)
    if not has_evidence and required_tools:
        messages.append("No model or specialist evidence was generated.")

    # 7. Cross-modal agreement where applicable
    if task == "OPTICAL_SAR_ANALYSIS":
        if not ("fusion_s1s2" in available_tools and "agreement" in available_tools):
            messages.append("Cross-modal agreement evidence missing for OPTICAL_SAR_ANALYSIS.")

    is_valid = len(messages) == 0

    # Confidence aggregation based on evidence signals
    signals = _aggregate_signals(state, evidence)
    confidence = _map_signals_to_confidence(signals)

    return ValidationResult(
        is_valid=is_valid,
        confidence=confidence,
        evidence=evidence,
        messages=messages,
    )
