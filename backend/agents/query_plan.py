"""
SatQuery AI — Explicit Structured Query Planning Engine

Defines canonical query intents, target classes, spatial operations,
synonym normalization, and QueryPlan construction.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class QueryIntent(str, Enum):
    SCENE_EXPLANATION = "SCENE_EXPLANATION"
    CLASS_STATISTIC = "CLASS_STATISTIC"
    SPATIAL_QUERY = "SPATIAL_QUERY"
    SPATIAL_HIGHLIGHT = "SPATIAL_HIGHLIGHT"
    CHANGE_DETECTION = "CHANGE_DETECTION"
    OBJECT_QUERY = "OBJECT_QUERY"
    MODALITY_QUERY = "MODALITY_QUERY"
    OPTICAL_SAR_FUSION = "OPTICAL_SAR_FUSION"
    UNROUTED = "UNROUTED"


class TargetClass(str, Enum):
    WATER = "WATER"
    BUILT = "BUILT"
    TREES = "TREES"
    GRASS = "GRASS"
    CROPS = "CROPS"
    BARE = "BARE"
    FLOOD = "FLOOD"
    VEGETATION = "VEGETATION"


class SpatialOperation(str, Enum):
    HIGHLIGHT = "HIGHLIGHT"
    LOCATE = "LOCATE"
    CHANGE_MAP = "CHANGE_MAP"


# ---------------------------------------------------------------------------
# Canonical Synonym Mappings
# ---------------------------------------------------------------------------
SYNONYM_MAP: dict[TargetClass, list[str]] = {
    TargetClass.BUILT: [
        "urban", "built", "city", "buildings", "building", "built-up", "built up",
        "infrastructure", "settlement", "developed", "concrete", "town", "roads",
        "road", "pavement", "urbanization", "urban area", "built area", "built-up area",
    ],
    TargetClass.WATER: [
        "water", "waterbody", "water body", "surface water", "river", "lake",
        "ocean", "sea", "pond", "reservoir", "coastal water", "canal", "waterway",
    ],
    TargetClass.FLOOD: [
        "flood", "flooding", "flooded", "inundation", "standing water", "submerged",
    ],
    TargetClass.TREES: [
        "tree", "trees", "forest", "woodland", "canopy", "woods", "timber", "jungle",
    ],
    TargetClass.GRASS: [
        "grass", "grassland", "lawn", "meadow", "pasture",
    ],
    TargetClass.CROPS: [
        "crop", "crops", "farmland", "agriculture", "paddy", "cultivated",
        "field", "fields", "farming", "agricultural",
    ],
    TargetClass.BARE: [
        "bare", "bare land", "bare soil", "sand", "dirt", "exposed ground",
        "soil", "barren", "desert", "open terrain", "land", "the land", "open land",
        "dry land", "terrain", "ground",
    ],
    TargetClass.VEGETATION: [
        "vegetation", "greenery", "green area", "plants", "flora", "green space",
        "vegetated area", "green",
    ],
}


def normalize_target_class(query: str) -> TargetClass | None:
    """Extract canonical TargetClass from query text with synonym normalization."""
    q = query.lower()
    
    # Check Flood first
    for syn in SYNONYM_MAP[TargetClass.FLOOD]:
        if syn in q:
            return TargetClass.FLOOD

    # Check Built / Urban
    for syn in SYNONYM_MAP[TargetClass.BUILT]:
        if syn in q:
            return TargetClass.BUILT

    # Check Water
    for syn in SYNONYM_MAP[TargetClass.WATER]:
        if syn in q:
            return TargetClass.WATER

    # Check specific vegetation subclasses before generic vegetation
    for syn in SYNONYM_MAP[TargetClass.TREES]:
        if syn in q:
            return TargetClass.TREES

    for syn in SYNONYM_MAP[TargetClass.GRASS]:
        if syn in q:
            return TargetClass.GRASS

    for syn in SYNONYM_MAP[TargetClass.CROPS]:
        if syn in q:
            return TargetClass.CROPS

    for syn in SYNONYM_MAP[TargetClass.BARE]:
        if syn in q:
            return TargetClass.BARE

    for syn in SYNONYM_MAP[TargetClass.VEGETATION]:
        if syn in q:
            return TargetClass.VEGETATION

    return None


class QueryPlan(BaseModel):
    """
    Explicit, validated, and immutable query plan executed by the LangGraph pipeline.
    """
    intent: QueryIntent = Field(default=QueryIntent.SCENE_EXPLANATION)
    mode: str = Field(default="single_scene", description="'single_scene' or 'pair'")
    source_asset_ids: list[str] = Field(default_factory=list)
    target_class: TargetClass | None = Field(default=None)
    spatial_operation: SpatialOperation | None = Field(default=None)
    required_specialists: list[str] = Field(default_factory=list)
    response_type: str = Field(default="explanation", description="'explanation', 'statistic', 'spatial', 'comparison', 'limitation'")
    reasoning: str | None = Field(default=None)


def build_query_plan(
    query: str,
    active_slot: str | None = None,
    mode_hint: str | None = None,
    manifest: dict[str, Any] | None = None,
) -> QueryPlan:
    """
    Deterministic QueryPlan constructor that parses natural language query intent,
    resolves target classes, and binds to active scene context.
    """
    q = (query or "").strip().lower()
    
    # 1. Determine Mode (single_scene vs pair)
    pair_keywords = [
        "change", "changed", "difference", "differences", "compare",
        "comparison", "between t1 and t2", "between both", "increase", "decrease",
        "what changed", "show change", "show changes"
    ]
    is_pair = mode_hint == "pair" or any(w in q for w in pair_keywords)
    mode = "pair" if is_pair else "single_scene"

    # 2. Extract Target Class
    target_class = normalize_target_class(q)

    # 3. Determine Spatial Operation
    highlight_keywords = ["highlight", "segment", "isolate", "outline", "mark", "mask", "show on map", "visualize"]
    locate_keywords = ["where is", "locate", "find where", "where are", "spatial distribution"]
    
    if is_pair:
        spatial_op = SpatialOperation.CHANGE_MAP
    elif any(w in q for w in highlight_keywords):
        spatial_op = SpatialOperation.HIGHLIGHT
    elif any(w in q for w in locate_keywords):
        spatial_op = SpatialOperation.LOCATE
    else:
        spatial_op = None

    # 4. Determine Intent & Specialists
    if is_pair:
        intent = QueryIntent.CHANGE_DETECTION
        specialists = ["bit_cd"]
        resp_type = "comparison"
    elif any(w in q for w in ["sar or optical", "optical or sar", "is this sar", "is this optical", "sensor type", "what modality"]):
        intent = QueryIntent.MODALITY_QUERY
        specialists = ["metadata_parser"]
        resp_type = "explanation"
    elif any(w in q for w in ["vehicle", "ship", "bridge", "airplane", "individual building", "object detection", "what objects are visible", "detect objects", "find objects", "locate structures"]):
        intent = QueryIntent.OBJECT_QUERY
        specialists = ["yolo_detector"]
        resp_type = "spatial"

    elif spatial_op == SpatialOperation.HIGHLIGHT:
        intent = QueryIntent.SPATIAL_HIGHLIGHT
        specialists = ["lulc_map"]
        resp_type = "spatial"
    elif spatial_op == SpatialOperation.LOCATE:
        intent = QueryIntent.SPATIAL_QUERY
        specialists = ["lulc_map"]
        resp_type = "spatial"
    elif target_class is not None and any(w in q for w in ["how much", "percentage", "percent", "%", "fraction", "ratio", "proportion", "amount", "area"]):
        intent = QueryIntent.CLASS_STATISTIC
        specialists = ["lulc_map"]
        resp_type = "statistic"
    elif any(w in q for w in ["fuse", "fusion", "s1 and s2", "optical and sar", "sar and optical"]):
        intent = QueryIntent.OPTICAL_SAR_FUSION
        specialists = ["fusion_s1s2"]
        resp_type = "explanation"
    else:
        intent = QueryIntent.SCENE_EXPLANATION
        specialists = ["lulc_map"]
        resp_type = "explanation"

    # Source asset IDs
    if mode == "pair":
        source_assets = ["T1", "T2"]
    else:
        source_assets = [active_slot or "T1"]

    return QueryPlan(
        intent=intent,
        mode=mode,
        source_asset_ids=source_assets,
        target_class=target_class,
        spatial_operation=spatial_op,
        required_specialists=specialists,
        response_type=resp_type,
        reasoning=f"Intent: {intent.value}, TargetClass: {target_class.value if target_class else 'None'}, SpatialOp: {spatial_op.value if spatial_op else 'None'}",
    )
