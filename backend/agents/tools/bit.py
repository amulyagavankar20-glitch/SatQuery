"""Qwen-callable bi-temporal BIT tool."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.agents.tools.base import BaseTool
from backend.inference import get_bit_runtime


class BITTool(BaseTool):
    """Adapter for BIT structured change evidence, not language generation."""

    tool_id = "bit_analyze"

    def validate(self, params: Mapping[str, Any]) -> None:
        pairs = params.get("tile_pairs")
        if pairs:
            if not isinstance(pairs, list) or not all(isinstance(pair, Mapping) and pair.get("before_image") and pair.get("after_image") for pair in pairs):
                raise ValueError("BIT tile_pairs must contain aligned before_image and after_image references.")
            return
        if not str(params.get("before_image", "")).strip() or not str(params.get("after_image", "")).strip():
            raise ValueError("BIT requires aligned before_image and after_image references.")

    def preprocess(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def infer(self, params: Mapping[str, Any]) -> Any:
        pairs = params.get("tile_pairs") or [{
            "before_image": params["before_image"], "after_image": params["after_image"], "tile_index": 0,
        }]
        runtime = get_bit_runtime()
        tile_results = [
            runtime.analyze(
                str(pair["before_image"]), str(pair["after_image"]),
                artifact_prefix=f"bit_tile_{int(pair.get('tile_index', index)):04d}",
            )
            for index, pair in enumerate(pairs)
        ]
        changed = sum(int(result["changed_pixel_count"]) for result in tile_results)
        total = sum(int(result["total_pixels"]) for result in tile_results)
        regions = [
            {**region, "tile_index": int(pair.get("tile_index", index))}
            for index, (pair, result) in enumerate(zip(pairs, tile_results, strict=True))
            for region in result["regions"]
        ]
        artifacts = [path for result in tile_results for path in result["artifact_paths"]]
        crops = [path for result in tile_results for path in result.get("region_crops", [])]
        return {
            "model": "BIT", "tile_count": len(tile_results),
            "changed_pixel_count": changed, "total_pixels": total,
            "change_percentage": round((changed / total * 100) if total else 0.0, 4),
            "regions": regions, "num_regions": len(regions), "region_crops": crops, "tile_results": tile_results,
            "artifact_paths": artifacts,
        }

    def postprocess(self, raw_output: Any) -> Any:
        return raw_output

    def explain_execution(self, result: Any) -> str:
        return "BIT produced structured bi-temporal change evidence: mask, statistics, and regions."

    def execute(self, params: Mapping[str, Any]):  # type: ignore[override]
        result = super().execute(params)
        if isinstance(result.result, dict):
            result.output_refs = list(result.result.get("artifact_paths", []))
            result.spatial_refs = list(result.result.get("regions", []))
            result.confidence = 1.0 if result.status == "success" else None
        return result
