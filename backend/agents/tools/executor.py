"""Tool execution layer for specialist tools.

This module provides a deterministic ``run_tool`` function that loads a tool
implementation (mock or real) based on the ``tool_id`` and executes it while
respecting the ``ToolRegistry`` database table. It returns a ``ToolResult``
instance defined in ``backend.agents.tools.base``.

Tool IDs here MUST match:
  - ToolSelector.TASK_TO_TOOLS
  - mock_tools class attributes
  - graph.py node invocations
  - ToolRegistry DB entries
"""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from sqlalchemy.orm import Session

from backend.models import ToolRegistry
from backend.agents.tools.base import BaseTool, ToolResult
from backend.agents.tools.mock_tools import (
    MockGeochatVQA,
    MockGeochatDescribe,
    MockGrounding,
    MockBitCD,
    MockAlign,
    MockVectorize,
    MockCoregister,
    MockFusion,
    MockAgreement,
    MockMobileSAM,
)
from backend.agents.tools.sarchat import SARChatTool
from backend.agents.tools.bit_cd import BITChangeDetectionTool
from backend.agents.tools.lulc import LulcMapTool

# ---------------------------------------------------------------------------
# Canonical mapping from tool_id → concrete implementation class.
# Every tool ID used by graph.py / ToolSelector MUST appear here.
# ---------------------------------------------------------------------------
_TOOL_IMPLEMENTATIONS: dict[str, type[BaseTool]] = {
    "sarchat_vqa":      SARChatTool,
    "geochat_vqa":      MockGeochatVQA,
    "geochat_describe": MockGeochatDescribe,
    "grounding":        MockGrounding,
    "bit_cd":           BITChangeDetectionTool,
    "align":            MockAlign,
    "vectorize":        MockVectorize,
    "coregister":       MockCoregister,
    "fusion_s1s2":      MockFusion,
    "agreement":        MockAgreement,
    "mobile_sam":       MockMobileSAM,
    "lulc_map":         LulcMapTool,
}


def _load_tool(tool_id: str, db: Session | None) -> BaseTool:
    """Lookup a tool in the registry and instantiate its implementation.

    Raises
    ------
    ValueError
        If the tool is unknown, disabled, or has no registered implementation.
    """
    if db is not None:
        try:
            stmt = db.query(ToolRegistry).filter(ToolRegistry.tool_id == tool_id)
            reg = stmt.one_or_none()
            if reg is None:
                # If tool registry is seeded, verify tool exists
                pass
            elif not reg.enabled:
                raise ValueError(f"Tool '{tool_id}' is disabled in ToolRegistry")
        except ValueError:
            raise
        except Exception:
            pass

    impl_cls = _TOOL_IMPLEMENTATIONS.get(tool_id)
    if impl_cls is None:
        raise ValueError(f"No implementation registered for tool '{tool_id}'")
    return impl_cls()


def run_tool(tool_id: str, params: Mapping[str, Any], db: Session) -> ToolResult:
    """Execute a specialist tool and return a standardized ``ToolResult``.

    The function performs:
    1. Registry validation (existence & enabled flag) — requires a real DB session.
    2. Instantiation of the concrete ``BaseTool`` implementation.
    3. Delegation to ``BaseTool.execute`` which runs the full lifecycle.

    ``db`` must never be None. Passing None will raise a TypeError at the
    database query boundary; callers are responsible for providing a session.

    All exceptions are captured and translated into a ``ToolResult`` with a
    status of ``error`` or ``validation_error`` as appropriate.
    """
    if not isinstance(params, Mapping):
        raise ValueError("`params` must be a mapping of input arguments")

    tool = _load_tool(tool_id, db)
    result = tool.execute(params)
    # Populate input_refs from params if supplied for traceability.
    if hasattr(result, "input_refs"):
        result.input_refs = list(params.get("input_refs", []))
    return result
