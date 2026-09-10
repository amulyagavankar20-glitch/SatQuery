"""
SatQuery AI — LangGraph State Definition

This is the ONE canonical GraphState used by all nodes in graph.py.
graph.py MUST NOT define a second GraphState.
"""
from __future__ import annotations

from typing import Any, TypedDict

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
    assets: list[str]          # file paths or Asset IDs
    asset_metadata: dict[str, Any]
    pair_fitness: dict[str, Any]

    # ── Routing & Planning ────────────────────────────────────────────────────
    detected_task: str
    target: str
    requested_operation: str
    requested_output: str
    route: RouteResponse
    selected_tools: list[str]
    execution_plan: list[ToolSelection]
    plan_summary: dict[str, Any]
    retry_count: int
    injected_task: str | None  # test-only bypass of the live Qwen router
    db_factory: Any               # test/request-injected SQLAlchemy session factory

    # ── Execution & Results ───────────────────────────────────────────────────
    preprocessing_result: PreprocessResult | None
    specialist_results: list[ToolResult]
    grounding_result: ToolResult | None
    alignment_result: ToolResult | None
    change_result: ToolResult | None
    fusion_result: ToolResult | None

    # ── Evidence & Output ─────────────────────────────────────────────────────
    spatial_evidence: list[Evidence]
    evidence_items: list[dict[str, Any]]
    confidence: Confidence | None
    execution_trace: list[dict[str, Any]]

    # ── Status & Errors ───────────────────────────────────────────────────────
    warnings: list[str]
    refusal_reason: str | None
    final_answer: str | None
    report_paths: list[str]
    status: str
    report: dict[str, Any] | None
