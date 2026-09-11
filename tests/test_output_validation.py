"""
Tests for Stage 4 Output Validation (InputClass & Task aware).
"""

import pytest
from backend.agents.output_validation import validate_output, _required_tools_for_task, ConfidenceLevel
from backend.agents.tools.base import ToolResult
from backend.schemas import InputClass, RouterTask


def test_required_tools_mapping():
    """Verify that required tools are modality and task specific."""
    # SAR modality
    sar_vqa_tools = _required_tools_for_task(RouterTask.SINGLE_VQA.value, InputClass.SINGLE_SAR.value)
    assert sar_vqa_tools == ["sarchat_vqa"]

    sar_caption_tools = _required_tools_for_task(RouterTask.CAPTIONING.value, InputClass.SINGLE_SAR.value)
    assert sar_caption_tools == ["sarchat_vqa"]

    # Optical modality
    opt_vqa_tools = _required_tools_for_task(RouterTask.SINGLE_VQA.value, InputClass.SINGLE_OPTICAL.value)
    assert opt_vqa_tools == ["geochat_vqa"]

    # Bi-temporal change detection
    bit_tools = _required_tools_for_task(RouterTask.CHANGE_DETECTION.value, InputClass.BI_TEMPORAL.value)
    assert bit_tools == ["bit_cd"]


def test_validate_output_single_sar_success():
    """Verify validation passes for SINGLE_SAR when sarchat_vqa succeeds."""
    sar_result = ToolResult(
        tool_id="sarchat_vqa",
        status="success",
        result={"answer": "SAR backscatter indicates high density urban structures.", "detections": []},
        explanation="SAR analysis complete",
        spatial_refs=[],
    )

    state = {
        "job_id": "job_sar_001",
        "detected_task": RouterTask.SINGLE_VQA.value,
        "input_class": InputClass.SINGLE_SAR.value,
        "specialist_results": [sar_result],
        "spatial_evidence": [],
    }

    validation = validate_output(state)
    assert validation.is_valid is True
    assert len(validation.messages) == 0
    assert len(validation.evidence.model_evidence) == 1
    assert validation.evidence.model_evidence[0].tool_id == "sarchat_vqa"


def test_validate_output_single_sar_missing_tool_fails():
    """Verify validation fails for SINGLE_SAR if sarchat_vqa did not run."""
    state = {
        "job_id": "job_sar_002",
        "detected_task": RouterTask.SINGLE_VQA.value,
        "input_class": InputClass.SINGLE_SAR.value,
        "specialist_results": [],
        "spatial_evidence": [],
    }

    validation = validate_output(state)
    assert validation.is_valid is False
    assert any("sarchat_vqa" in msg for msg in validation.messages)


def test_validate_output_single_optical_success():
    """Verify validation passes for SINGLE_OPTICAL when geochat_vqa succeeds."""
    opt_result = ToolResult(
        tool_id="geochat_vqa",
        status="success",
        result="The optical scene shows agricultural land.",
        explanation="GeoChat complete",
        spatial_refs=[],
    )

    state = {
        "job_id": "job_opt_001",
        "detected_task": RouterTask.SINGLE_VQA.value,
        "input_class": InputClass.SINGLE_OPTICAL.value,
        "specialist_results": [opt_result],
        "spatial_evidence": [],
    }

    validation = validate_output(state)
    assert validation.is_valid is True
    assert len(validation.messages) == 0


def test_validate_output_bitemporal_success():
    """Verify validation passes for BI_TEMPORAL when bit_cd succeeds."""
    bit_result = ToolResult(
        tool_id="bit_cd",
        status="success",
        result={
            "statistics": {"change_percentage": 2.5},
            "geojson": {"type": "FeatureCollection", "features": []},
        },
        explanation="BIT change detection complete",
        spatial_refs=[],
    )

    state = {
        "job_id": "job_bit_001",
        "detected_task": RouterTask.CHANGE_DETECTION.value,
        "input_class": InputClass.BI_TEMPORAL.value,
        "specialist_results": [bit_result],
        "spatial_evidence": [],
    }

    validation = validate_output(state)
    assert validation.is_valid is True
    assert len(validation.messages) == 0
