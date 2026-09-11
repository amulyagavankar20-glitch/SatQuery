"""Tests for bit_cd specialist tool and BIT-LEVIR ONNX change detection."""

from pathlib import Path
import pytest
import numpy as np
from backend.agents.tools.bit_cd import BITChangeDetectionTool
from backend.services.bit_service import BITService


def test_bit_cd_tool_instantiation():
    tool = BITChangeDetectionTool()
    assert tool.tool_id == "bit_cd"


def test_bit_service_instantiation():
    service = BITService()
    assert service is not None


def test_bit_onnx_model_availability():
    onnx_path = Path("models/BIT_LEVIR_model.onnx")
    assert onnx_path.exists(), "BIT-LEVIR ONNX model file must exist in models/"
