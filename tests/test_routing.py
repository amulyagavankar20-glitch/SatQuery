"""Tests for query routing and intent classification."""

import pytest
from backend.schemas import RouteRequest, RouterTask
from backend.services.model_slotting import RuleBasedRouterAdapter
from backend.agents.router import VLMRouter


def test_rule_based_router_intent_mapping():
    adapter = RuleBasedRouterAdapter()
    
    # Change query -> CHANGE_DETECTION
    res_change = adapter.route(RouteRequest(query="What changed between these two dates?", manifest={"input_class": "BI_TEMPORAL"}))
    assert res_change.task == RouterTask.CHANGE_DETECTION
    assert res_change.requires_change_analysis is True
    
    # Grounding query -> GROUNDING
    res_ground = adapter.route(RouteRequest(query="Where is the airport located?", manifest={"input_class": "SINGLE_OPTICAL"}))
    assert res_ground.task == RouterTask.GROUNDING
    assert res_ground.requires_grounding is True
    
    # Description query -> CAPTIONING
    res_cap = adapter.route(RouteRequest(query="Give an overview and description of this scene.", manifest={"input_class": "SINGLE_SAR"}))
    assert res_cap.task == RouterTask.CAPTIONING


def test_query_router_change_phrases_bi_temporal():
    """Verify various temporal change query phrasings route to CHANGE_DETECTION or CHANGE_VQA."""
    adapter = RuleBasedRouterAdapter()

    change_queries = [
        "explain the changes",
        "explain me the changes",
        "what changed?",
        "what are the differences?",
        "compare them",
        "compare the two images",
        "describe the change",
        "changes between the two images",
    ]

    for q in change_queries:
        req = RouteRequest(
            query=q,
            manifest={"input_class": "BI_TEMPORAL", "mode": "pair"},
            session_history=[],
        )
        res = adapter.route(req)
        assert res.task in [RouterTask.CHANGE_DETECTION, RouterTask.CHANGE_VQA], f"Query '{q}' failed to route to change detection"
        assert res.requires_change_analysis is True


def test_query_router_sar_single_vs_pair():
    """Verify SAR single image goes to CAPTIONING / SINGLE_VQA while SAR pair goes to CHANGE_DETECTION."""
    adapter = RuleBasedRouterAdapter()

    # SAR Single Scene
    req_single = RouteRequest(
        query="Explain me the SAR image",
        manifest={"input_class": "SINGLE_SAR"},
        session_history=[],
    )
    res_single = adapter.route(req_single)
    assert res_single.task in [RouterTask.CAPTIONING, RouterTask.SINGLE_VQA]
    assert res_single.requires_change_analysis is False

    # SAR Temporal Pair
    req_pair = RouteRequest(
        query="Explain me the changes between the two SAR images",
        manifest={"input_class": "BI_TEMPORAL", "mode": "pair"},
        session_history=[],
    )
    res_pair = adapter.route(req_pair)
    assert res_pair.task in [RouterTask.CHANGE_DETECTION, RouterTask.CHANGE_VQA]
    assert res_pair.requires_change_analysis is True



