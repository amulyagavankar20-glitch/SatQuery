"""Unit tests for the Model Slotting & Adapter Architecture and PDF export."""

import pytest
from backend.schemas import JobView, RouteRequest, RouterTask
from backend.services.model_slotting import (
    ModelSlotRegistry,
    MockRouterAdapter,
    MockTalkingVLMAdapter,
    BITChangeDetectionAdapter,
    MobileSAMAdapter,
    OpticalSARFusionAdapter,
    SlotID,
)
from backend.services.pdf_report import generate_job_pdf


def test_slot_registry_reports_all_five_slots():
    registry = ModelSlotRegistry()
    slots = registry.get_slot_statuses()
    assert len(slots) == 5
    slot_ids = {s.slot_id for s in slots}
    assert SlotID.ROUTER.value in slot_ids
    assert SlotID.TALKING_VLM.value in slot_ids
    assert SlotID.BIT_CD.value in slot_ids
    assert SlotID.MOBILE_SAM.value in slot_ids
    assert SlotID.FUSION_S1S2.value in slot_ids


def test_mock_router_intent_mapping():
    router = MockRouterAdapter()

    # VQA
    res_vqa = router.route(RouteRequest(query="What is the dominant land cover class?", manifest={}))
    assert res_vqa.task == RouterTask.SINGLE_VQA
    assert not res_vqa.requires_change_analysis

    # Change
    res_change = router.route(RouteRequest(query="Detect changes between t1 and t2 in this region", manifest={}))
    assert res_change.task == RouterTask.CHANGE_DETECTION
    assert res_change.requires_change_analysis

    # Grounding
    res_ground = router.route(RouteRequest(query="Locate and segment the airport runway", manifest={}))
    assert res_ground.task == RouterTask.GROUNDING
    assert res_ground.requires_grounding

    # Captioning
    res_cap = router.route(RouteRequest(query="Provide an overview description of the scene", manifest={}))
    assert res_cap.task == RouterTask.CAPTIONING


def test_talking_vlm_adapter():
    vlm = MockTalkingVLMAdapter()
    answer = vlm.answer_vqa("What land cover classes are visible?", ["scene.tif"])
    assert "land-cover" in answer.lower() or "urban" in answer.lower()

    desc = vlm.describe(["scene.tif"])
    assert "earth observation" in desc.lower()


def test_specialist_adapters():
    bit = BITChangeDetectionAdapter(weights_path=None)
    bit_out = bit.predict_change_mask("pre.tif", "post.tif")
    assert "mask_id" in bit_out

    sam = MobileSAMAdapter(weights_path=None)
    sam_out = sam.segment_prompt("scene.tif", "river")
    assert "segment_id" in sam_out

    fusion = OpticalSARFusionAdapter(weights_path=None)
    fus_out = fusion.fuse_and_assess_agreement("opt.tif", "sar.tif")
    assert "agreement_score" in fus_out


def test_pdf_report_generation():
    from backend.schemas import JobAnswer
    job_view = JobView(
        job_id="11111111-2222-3333-4444-555555555555",
        session_id="22222222-3333-4444-5555-666666666666",
        status="completed",
        input_class="SINGLE_OPTICAL",
        task="SINGLE_VQA",
        query="What land cover classes are visible?",
        answer=JobAnswer(text="The scene features predominantly agricultural and urban land cover."),
    )
    pdf_bytes = generate_job_pdf(job_view)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")
