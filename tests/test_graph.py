"""Tests for LangGraph graph construction and node compilation."""

import pytest
from backend.agents.graph import app, workflow


def test_graph_compiled():
    assert app is not None
    assert workflow is not None


def test_graph_nodes_registered():
    nodes = set(workflow.nodes.keys())
    assert "input_validator" in nodes
    assert "metadata_parser" in nodes
    assert "pair_fitness_gate" in nodes
    assert "query_router" in nodes
    assert "tool_selector" in nodes
    assert "preprocess" in nodes
    assert "sar_map" in nodes
    assert "lulc_map" in nodes
    assert "bit_cd" in nodes
    assert "evidence_fusion" in nodes
    assert "audit_logger" in nodes
    assert "report_generator" in nodes
