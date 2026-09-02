"""Tests for the specialist tool execution layer (mock tools).

These tests cover successful execution, validation failures, runtime errors,
malformed parameters, unknown tools, disabled tools, and result
propagation. They use a lightweight mocked SQLAlchemy ``Session`` that
returns a minimal ``ToolRegistry`` stub.
"""

import pytest
from unittest.mock import Mock

from backend.agents.tools.executor import run_tool
from backend.agents.tools.base import ToolResult

# Simple stub representing a row from the ``ToolRegistry`` table
class _FakeToolRegistry:
    def __init__(self, tool_id: str, enabled: bool = True):
        self.tool_id = tool_id
        self.enabled = enabled
        # The real model also includes supported_tasks/modalities, but they are
        # not consulted by ``run_tool`` for the mock implementations.

# Helper to build a mocked ``Session`` that returns the provided registry stub
def make_mock_session(registry_stub: _FakeToolRegistry | None):
    mock_session = Mock()
    # ``query`` returns an object with ``filter`` and ``one_or_none``
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.one_or_none.return_value = registry_stub
    mock_session.query.return_value = mock_query
    return mock_session

# ---------------------------------------------------------------------------
# 1. Successful execution
# ---------------------------------------------------------------------------
def test_successful_execution():
    db = make_mock_session(_FakeToolRegistry("geochat_vqa", enabled=True))
    params = {"question": "What is shown?", "image_refs": ["img1"]}
    result: ToolResult = run_tool("geochat_vqa", params, db)
    assert result.status == "success"
    assert result.tool_id == "geochat_vqa"
    assert result.result == "MOCK_VQA_ANSWER to 'What is shown?'"

# ---------------------------------------------------------------------------
# 2. Validation failure
# ---------------------------------------------------------------------------
def test_validation_failure():
    db = make_mock_session(_FakeToolRegistry("grounding", enabled=True))
    # Omit required ``text`` field – validator should raise ValueError
    params = {"image_refs": ["img1"]}
    result = run_tool("grounding", params, db)
    assert result.status == "validation_error"
    assert "Missing or invalid 'text'" in result.explanation

# ---------------------------------------------------------------------------
# 3. Tool runtime failure (exception inside infer)
# ---------------------------------------------------------------------------
def test_tool_failure(monkeypatch):
    db = make_mock_session(_FakeToolRegistry("bit_cd", enabled=True))
    params = {"pre_image": "pre", "post_image": "post"}
    # Patch the MockBitCD.infer method to raise an exception
    from backend.agents.tools.mock_tools import MockBitCD

    def bad_infer(self, params):
        raise RuntimeError("mock inference crash")

    monkeypatch.setattr(MockBitCD, "infer", bad_infer, raising=False)
    result = run_tool("bit_cd", params, db)
    assert result.status == "error"
    assert "mock inference crash" in result.explanation

# ---------------------------------------------------------------------------
# 4. Malformed parameters (non‑mapping)
# ---------------------------------------------------------------------------
def test_malformed_parameters():
    db = make_mock_session(_FakeToolRegistry("geochat_vqa", enabled=True))
    with pytest.raises(ValueError, match="params must be a mapping"):
        run_tool("geochat_vqa", [1, 2, 3], db)  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# 5. Unknown tool
# ---------------------------------------------------------------------------
def test_unknown_tool():
    db = make_mock_session(None)  # No registry entry
    params = {"question": "test", "image_refs": []}
    with pytest.raises(ValueError, match="Unknown tool 'unknown_tool'"):
        run_tool("unknown_tool", params, db)

# ---------------------------------------------------------------------------
# 6. Disabled tool
# ---------------------------------------------------------------------------
def test_disabled_tool():
    db = make_mock_session(_FakeToolRegistry("geochat_vqa", enabled=False))
    params = {"question": "test", "image_refs": []}
    with pytest.raises(ValueError, match="is disabled"):
        run_tool("geochat_vqa", params, db)

# ---------------------------------------------------------------------------
# 7. Result propagation – ensure ``input_refs`` are copied into the result
# ---------------------------------------------------------------------------
def test_result_propagation_input_refs():
    db = make_mock_session(_FakeToolRegistry("mobile_sam", enabled=True))
    params = {"image_ref": "img1", "prompt": "tree", "input_refs": ["ref1", "ref2"]}
    result = run_tool("mobile_sam", params, db)
    assert result.status == "success"
    assert result.input_refs == ["ref1", "ref2"]
    assert result.result == {"segment_id": "MOCK_SAM_SEGMENT_TREE"}
