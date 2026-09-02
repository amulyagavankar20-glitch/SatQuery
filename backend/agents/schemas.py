"""
Agentic Workflow specific schemas for SatQuery AI

NOTE: ToolResult is defined canonically in backend.agents.tools.base.
      This module re-exports it for backwards compatibility and imports
      by state.py / output_validation.py.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Reusing some core schemas from the backend
from backend.schemas import (
    TraceCreate,
    RouteResponse,
    PreprocessResult,
)

# Canonical ToolResult – defined in tools/base, re-exported here.
from backend.agents.tools.base import ToolResult  # noqa: F401  (re-export)


class ToolSelection(BaseModel):
    """Schema for selecting a tool during execution planning."""
    tool_id: str = Field(..., description="Unique identifier for the tool")
    reason: str = Field(..., description="Reason for selecting this tool")
    parameters: Dict[str, Any] = Field(default_factory=dict)


class Confidence(BaseModel):
    """Qualitative confidence level for the final answer."""
    level: str = Field(..., description="HIGH, MEDIUM, or LOW")
    signals: List[str] = Field(default_factory=list, description="Supporting evidence signals")
    reasoning: Optional[str] = Field(None, description="Narrative explanation")


class Evidence(BaseModel):
    """Spatial evidence extracted during analysis."""
    evidence_type: str = Field(..., description="E.g., 'change_mask', 'grounding_box', 'water_body'")
    geometry_wkt: Optional[str] = Field(None, description="WKT string of the geometry")
    file_path: Optional[str] = Field(None, description="Path to a raster mask if applicable")
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphOutput(BaseModel):
    """The final structured output of the LangGraph workflow."""
    status: str = Field(..., description="Final status of the workflow")
    final_answer: Optional[str] = Field(None, description="The comprehensive answer presented to the user")
    confidence: Optional[Confidence] = None
    spatial_evidence: List[Evidence] = Field(default_factory=list)
    report_paths: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
