"""
SatQuery AI — LangGraph State Definition

This is the ONE canonical GraphState used by all nodes in graph.py.
graph.py MUST NOT define a second GraphState.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from backend.schemas import PreprocessResult, RouteResponse
from backend.agents.schemas import ToolSelection, Confidence, Evidence
from backend.agents.tools.base import ToolResult  # canonical definition


class GraphState(TypedDict, total=False):
    # ── Core Identifiers ──────────────────────────────────────────────────────
    job_id: str
    session_id: str

    # ── Input Processing ──────────────────────────────────────────────────────
    user_query: str
    normalized_query: str
    input_class: str
    assets: List[str]          # file paths or Asset IDs
    asset_metadata: Dict[str, Any]
    pair_fitness: Dict[str, Any]

    # ── Routing & Planning ────────────────────────────────────────────────────
    detected_task: str
    target: str
    requested_operation: str
    requested_output: str
    route: RouteResponse
    selected_tools: List[str]
    execution_plan: List[ToolSelection]

    # ── Execution & Results ───────────────────────────────────────────────────
    preprocessing_result: Optional[PreprocessResult]
    specialist_results: List[ToolResult]
    grounding_result: Optional[ToolResult]
    alignment_result: Optional[ToolResult]
    change_result: Optional[ToolResult]
    fusion_result: Optional[ToolResult]

    # ── Evidence & Output ─────────────────────────────────────────────────────
    spatial_evidence: List[Evidence]
    evidence_items: List[Dict[str, Any]]
    confidence: Optional[Confidence]
    execution_trace: List[Dict[str, Any]]

    # ── Status & Errors ───────────────────────────────────────────────────────
    warnings: List[str]
    refusal_reason: Optional[str]
    final_answer: Optional[str]
    report_paths: List[str]
    status: str
    report: Optional[Dict[str, Any]]
