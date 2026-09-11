"""Tests for sar_map specialist tool and SAR backscatter radiometry."""

import pytest
import numpy as np
from backend.agents.tools.sar_map import SarMapTool
from backend.services.sar_ben import BenS1Classifier


def test_sar_map_tool_instantiation():
    tool = SarMapTool()
    assert tool.tool_id == "sar_map"


def test_sar_ben_classifier_instance():
    classifier = BenS1Classifier.get_instance()
    assert classifier is not None
    assert classifier.is_available() is True, "reBEN ResNet50 weights must be available"


def test_sar_ben_classifier_predict():
    classifier = BenS1Classifier.get_instance()
    # 2-channel VV/VH dummy tensor (linear amplitude)
    stack = np.random.uniform(0.01, 0.5, size=(2, 120, 120)).astype(np.float32)
    tags = classifier.predict(stack, top_k=3)
    assert len(tags) > 0
    assert "name" in tags[0]
    assert "score" in tags[0]
