"""Tests for query routing and intent classification."""

import pytest
from backend.schemas import RouteRequest, RouterTask
from backend.services.model_slotting import RuleBasedRouterAdapter


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
