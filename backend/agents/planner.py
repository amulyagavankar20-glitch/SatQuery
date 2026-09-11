"""Turn verified modality facts plus Qwen task intent into a bounded plan."""

from __future__ import annotations

from typing import Any

from backend.schemas import InputClass, RouterTask


def build_plan(input_class: InputClass, task: RouterTask, assets: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the only specialist topology permitted for a validated input set."""
    if input_class == InputClass.SINGLE_OPTICAL:
        return {"specialists": ["geoground_analyze"], "parallel": False}
    if input_class == InputClass.SINGLE_SAR:
        return {"specialists": ["sarchat_vqa"], "parallel": False}
    if input_class == InputClass.OPTICAL_SAR:
        return {
            "specialists": ["geoground_analyze", "sarchat_vqa"],
            "parallel": True,
            "rule": "GeoGround receives optical/S2 only; SARChat receives SAR/S1 only.",
        }
    if input_class == InputClass.BI_TEMPORAL:
        plan: dict[str, Any] = {"specialists": ["bit_analyze"], "parallel": False}
        if task == RouterTask.CHANGE_VQA:
            modalities = {str(asset.get("modality", "")).upper() for asset in assets}
            if modalities == {"OPTICAL"}:
                plan["follow_up"] = ["geoground_analyze"]
            elif modalities == {"SAR"}:
                plan["follow_up"] = ["sarchat_vqa"]
        return plan
    raise ValueError(f"Unsupported validated input class: {input_class.value}")
