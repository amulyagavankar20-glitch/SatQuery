"""Tests for output validation schemas."""

import pytest
from backend.agents.output_validation import validate_output
from backend.schemas import RouterTask


def test_validate_output_valid_payload():
    result = {
        "final_answer": "Analysis confirmed scene composition.",
        "status": "completed",
        "detected_task": RouterTask.SINGLE_VQA.value,
        "input_class": "SINGLE_SAR",
        "confidence": "MEDIUM",
        "specialist_results": [
            {
                "tool_id": "sar_map",
                "status": "success",
                "result": {"status": "success", "summary": "Identified backscatter"},
            }
        ],
    }
    validated = validate_output(result)
    assert validated.is_valid is True


def test_validate_output_empty_payload():
    result = {}
    validated = validate_output(result)
    assert hasattr(validated, "is_valid")
