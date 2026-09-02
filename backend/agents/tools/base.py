"""Tool contract and standardized result definitions.

This module defines the abstract interface that all specialist tools must
implement in Stage 4 and provides a concrete ``ToolResult`` model used for
orchestrating tool execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Mapping

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Standardized result returned by every specialist tool.

    The fields capture provenance, performance metrics, and a human‑readable
    explanation. Mock tools populate these with deterministic, clearly marked
    values.
    """

    tool_id: str = Field(..., description="Identifier of the tool that produced this result")
    status: str = Field(..., description="Execution status – e.g. 'success', 'validation_error', 'error'")
    input_refs: List[str] = Field(default_factory=list, description="References to input artefacts used")
    output_refs: List[str] = Field(default_factory=list, description="References to generated artefacts")
    result: Any = Field(..., description="Primary payload produced by the tool")
    confidence: float | None = Field(None, description="Confidence score if applicable")
    latency_ms: float | None = Field(None, description="Execution latency in milliseconds")
    warnings: List[str] = Field(default_factory=list, description="Any non‑critical warnings raised")
    explanation: str = Field(..., description="Narrative explanation of what the tool did")
    spatial_refs: List[Mapping[str, Any]] = Field(
        default_factory=list,
        description="Optional spatial references (e.g., bounding boxes, geometry) relevant to the result",
    )


class BaseTool(ABC):
    """Abstract contract for specialist tools.

    Concrete implementations must implement the five lifecycle methods. The
    ``execute`` method orchestrates the workflow and returns a ``ToolResult``.
    """

    tool_id: str

    @abstractmethod
    def validate(self, params: Mapping[str, Any]) -> None:
        """Validate input parameters. Raise ``ValueError`` on failure."""

    @abstractmethod
    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        """Perform any lightweight preprocessing and return possibly altered params."""

    @abstractmethod
    def infer(self, params: Mapping[str, Any]) -> Any:
        """Core inference step – returns the raw model output."""

    @abstractmethod
    def postprocess(self, raw_output: Any) -> Any:
        """Transform raw output into a user‑friendly form."""

    @abstractmethod
    def explain_execution(self, result: Any) -> str:
        """Generate a human‑readable explanation of the execution path and result."""

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        """Run the full lifecycle and package a :class:`ToolResult`.

        The method measures latency, catches exceptions and maps them to a
        status string. All mock tools are deterministic and identify themselves
        in the ``result`` field with a ``MOCK_...`` prefix.
        """
        import time

        start = time.time()
        try:
            # 1️⃣ Validation
            self.validate(params)
            # 2️⃣ Preprocess
            processed = self.preprocess(params)
            # 3️⃣ Inference
            raw = self.infer(processed)
            # 4️⃣ Postprocess
            final = self.postprocess(raw)
            # 5️⃣ Explanation
            explanation = self.explain_execution(final)
            status = "success"
        except ValueError as ve:
            # Validation‑related failure
            final = None
            explanation = str(ve)
            status = "validation_error"
        except Exception as exc:
            # Any other runtime error
            final = None
            explanation = f"Tool execution failed: {exc}"
            status = "error"

        latency = (time.time() - start) * 1000.0

        return ToolResult(
            tool_id=self.tool_id,
            status=status,
            input_refs=params.get("input_refs", []),
            output_refs=[],
            result=final,
            confidence=None,
            latency_ms=latency,
            warnings=[],
            explanation=explanation,
            spatial_refs=[],
        )
