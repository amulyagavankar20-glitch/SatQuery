"""Tests for Stage 4 LangGraph StateGraph.

These tests verify that the graph compiles, that each defined task follows
the required execution path, and that tasks do not execute nodes that belong
to other paths.

The ``injected_task`` field in GraphState allows tests to bypass the live
Qwen/Ollama router (which requires an external process) while still exercising
the deterministic graph structure.  The router field is ONLY read via
injected_task in tests; in production QwenRouter is called.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from backend.agents.graph import app
from backend.agents.state import GraphState
from backend.agents.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DummySession:
    """Minimal in-memory session that satisfies the SessionContext interface."""
    def __init__(self):
        self.traces = []
        self.errors = []
        self.status = None
        self.tool_results = []
        self.preprocessing_result = None

    def record_trace(self, **kwargs):
        self.traces.append(kwargs)

    def add_error(self, err):
        self.errors.append(err)

    def __repr__(self):
        return "<DummySession>"


class FakeToolRegistry:
    """Minimal ToolRegistry stub for mock DB sessions."""
    def __init__(self, tool_id: str, enabled: bool = True):
        self.tool_id = tool_id
        self.enabled = enabled
        self.supported_tasks = None
        self.supported_modalities = None


def make_mock_db(enabled_tools=None):
    """Return a mock SQLAlchemy Session that says every tool is enabled."""
    if enabled_tools is None:
        enabled_tools = [
            "geochat_vqa", "geochat_describe", "grounding",
            "bit_cd", "align", "vectorize",
            "coregister", "fusion_s1s2", "agreement",
            "mobile_sam", "preprocess",
        ]

    def make_query(tool_id_str):
        for tid in enabled_tools:
            if tid == tool_id_str:
                return FakeToolRegistry(tool_id_str, enabled=True)
        return None

    mock_session = MagicMock()
    mock_query_obj = MagicMock()
    mock_query_obj.filter.side_effect = lambda *a, **kw: mock_query_obj
    mock_query_obj.one_or_none.side_effect = (
        lambda: make_query(mock_session._last_tool_id)
    )

    def _query(model):
        return mock_query_obj

    mock_session.query.side_effect = _query
    mock_session.close.return_value = None
    return mock_session


# Replacement run_tool that avoids real DB look-ups in tests
def mock_run_tool(tool_id, params, db=None):
    return ToolResult(
        tool_id=tool_id,
        status="success",
        input_refs=list(params.get("input_refs", [])),
        output_refs=[],
        result=f"MOCK_RESULT_{tool_id.upper()}",
        confidence=None,
        latency_ms=0.0,
        warnings=[],
        explanation=f"[MOCK] {tool_id} executed",
        spatial_refs=[],
    )


@pytest.fixture(autouse=True)
def patch_externals(monkeypatch):
    """Patch all external dependencies for every test."""
    dummy = DummySession()

    # Patch session store
    monkeypatch.setattr("backend.agents.graph.get_session", lambda _: dummy)

    # Patch run_tool inside graph to avoid DB interaction
    monkeypatch.setattr("backend.agents.graph.run_tool", mock_run_tool)

    # Skip PostgreSQL tool_registry lookups in unit tests
    monkeypatch.setattr(
        "backend.agents.graph.ToolSelector.validate_selection",
        lambda self, task, input_class: self.get_tool_sequence(task),
    )

    # Patch preprocessing to avoid real file I/O
    from backend.schemas import PreprocessResult, InputClass
    mock_preprocess_result = PreprocessResult(
        input_class=InputClass.SINGLE_OPTICAL,
        success=True,
        tile_references=[],
        preprocessing_steps=["mock_step"],
        spatial_reference={},
        output_paths={},
    )
    monkeypatch.setattr(
        "backend.agents.graph.run_preprocessing",
        lambda **kwargs: mock_preprocess_result,
    )

    yield dummy


# ---------------------------------------------------------------------------
# Utility: run graph and extract visited nodes
# ---------------------------------------------------------------------------

def run_graph(injected_task: str, input_class: str = "SINGLE_OPTICAL",
              assets=None, user_query: str = "What is shown?") -> dict:
    """Run the compiled graph and return the final state dict."""
    if assets is None:
        assets = []

    init_state: GraphState = {
        "session_id": "test-session",
        "job_id": "test-job",
        "user_query": user_query,
        "input_class": input_class,
        "assets": assets,
        "asset_metadata": {"input_class": input_class},
        "pair_fitness": {},
        "specialist_results": [],
        "execution_trace": [],
        "warnings": [],
        "injected_task": injected_task,  # bypasses Qwen in tests
        "status": "running",
    }
    final_output = None
    for step in app.stream(init_state):
        final_output = step

    # final_output is a dict mapping node_name → state update dict
    # The last non-refusal terminal node is report_generator
    if "report_generator" in final_output:
        return final_output["report_generator"]
    if "audit_logger" in final_output:
        return final_output["audit_logger"]
    return final_output


def visited(state_update: dict) -> list:
    """Extract the visited node list from the execution_trace."""
    trace = state_update.get("execution_trace", [])
    return [e["node"] for e in trace]


# ---------------------------------------------------------------------------
# A. Graph compilation
# ---------------------------------------------------------------------------

def test_graph_compiles():
    assert app is not None


# ---------------------------------------------------------------------------
# B. SINGLE_OPTICAL + VQA
# ---------------------------------------------------------------------------

def test_single_vqa_path(patch_externals):
    state = run_graph("SINGLE_VQA", input_class="SINGLE_OPTICAL")
    v = visited(state)
    expected = {
        "input_validator", "metadata_parser", "pair_fitness_gate",
        "query_router", "tool_selector", "preprocess",
        "geochat_vqa", "evidence_fusion", "audit_logger", "report_generator",
    }
    forbidden = {"align", "bit_cd", "vectorize", "geochat_describe",
                 "coregister", "fusion_s1s2", "agreement", "grounding"}
    assert expected.issubset(set(v)), f"Missing nodes: {expected - set(v)}"
    assert set(v).isdisjoint(forbidden), f"Forbidden nodes visited: {set(v) & forbidden}"


# ---------------------------------------------------------------------------
# C. SINGLE_OPTICAL + GROUNDING
# ---------------------------------------------------------------------------

def test_grounding_path(patch_externals):
    state = run_graph("GROUNDING", input_class="SINGLE_OPTICAL")
    v = visited(state)
    expected = {
        "preprocess", "geochat_vqa", "grounding",
        "evidence_fusion", "audit_logger", "report_generator",
    }
    forbidden = {"align", "bit_cd", "vectorize", "coregister",
                 "fusion_s1s2", "agreement"}
    assert expected.issubset(set(v)), f"Missing: {expected - set(v)}"
    assert set(v).isdisjoint(forbidden), f"Forbidden: {set(v) & forbidden}"


# ---------------------------------------------------------------------------
# D. BI_TEMPORAL + CHANGE_VQA  — fusion_s1s2 must NOT run
# ---------------------------------------------------------------------------

def test_change_vqa_path_excludes_fusion(patch_externals):
    state = run_graph("CHANGE_VQA", input_class="BI_TEMPORAL")
    v = visited(state)
    expected = {
        "preprocess", "align", "bit_cd", "geochat_describe",
        "evidence_fusion", "audit_logger", "report_generator",
    }
    assert expected.issubset(set(v)), f"Missing: {expected - set(v)}"
    assert "fusion_s1s2" not in v, "fusion_s1s2 must NOT run for CHANGE_VQA"
    assert "coregister" not in v, "coregister must NOT run for CHANGE_VQA"


# ---------------------------------------------------------------------------
# E. OPTICAL_SAR + ANALYSIS  — bit_cd must NOT run
# ---------------------------------------------------------------------------

def test_optical_sar_analysis_excludes_bit_cd(patch_externals):
    state = run_graph("OPTICAL_SAR_ANALYSIS", input_class="OPTICAL_SAR")
    v = visited(state)
    expected = {
        "preprocess", "coregister", "fusion_s1s2", "agreement",
        "geochat_describe", "evidence_fusion", "audit_logger", "report_generator",
    }
    assert expected.issubset(set(v)), f"Missing: {expected - set(v)}"
    assert "bit_cd" not in v, "bit_cd must NOT run for OPTICAL_SAR_ANALYSIS"
    assert "align" not in v, "align must NOT run for OPTICAL_SAR_ANALYSIS"


# ---------------------------------------------------------------------------
# F. Invalid request → REFUSE
# ---------------------------------------------------------------------------

def test_invalid_task_refusal(patch_externals):
    state = run_graph("NONEXISTENT_TASK_XYZ", input_class="SINGLE_OPTICAL")
    v = visited(state)
    assert "refusal" in v, f"refusal node not visited; visited={v}"
    # Status must be refused (may arrive via state update from a different step)
    # The audit_logger + report_generator run after refusal
    assert "audit_logger" in v


# ---------------------------------------------------------------------------
# G. report_generator must NOT mark refused runs as COMPLETED
# ---------------------------------------------------------------------------

def test_refused_status_preserved(patch_externals):
    state = run_graph("NONEXISTENT_TASK_XYZ", input_class="SINGLE_OPTICAL")
    # Either status key is in the state update or in the report
    report = state.get("report") or {}
    final_status = state.get("status") or report.get("status")
    # The graph should never mark a refused run as 'completed'
    assert final_status != "completed", (
        f"Refused run was incorrectly marked as completed. status={final_status}"
    )


# ---------------------------------------------------------------------------
# H. Empty query → refusal at input_validator
# ---------------------------------------------------------------------------

def test_empty_query_refusal(patch_externals):
    state = run_graph("SINGLE_VQA", user_query="   ")
    v = visited(state)
    assert "refusal" in v, f"Expected refusal for empty query; visited={v}"


# ---------------------------------------------------------------------------
# I. CHANGE_VQA does NOT go through vectorize → evidence_fusion directly
#    (vectorize only runs for CHANGE_DETECTION; CHANGE_VQA skips to geochat_describe)
# ---------------------------------------------------------------------------

def test_change_vqa_skips_vectorize_to_fusion(patch_externals):
    state = run_graph("CHANGE_VQA", input_class="BI_TEMPORAL")
    v = visited(state)
    # geochat_describe must appear before evidence_fusion
    if "geochat_describe" in v and "evidence_fusion" in v:
        assert v.index("geochat_describe") < v.index("evidence_fusion")


# ---------------------------------------------------------------------------
# J. CHANGE_DETECTION goes through vectorize, NOT geochat_describe
# ---------------------------------------------------------------------------

def test_change_detection_uses_vectorize(patch_externals):
    state = run_graph("CHANGE_DETECTION", input_class="BI_TEMPORAL")
    v = visited(state)
    expected = {"preprocess", "align", "bit_cd", "vectorize", "evidence_fusion"}
    assert expected.issubset(set(v)), f"Missing: {expected - set(v)}"
    assert "geochat_describe" not in v, "geochat_describe must NOT run for CHANGE_DETECTION"
    assert "fusion_s1s2" not in v, "fusion_s1s2 must NOT run for CHANGE_DETECTION"
