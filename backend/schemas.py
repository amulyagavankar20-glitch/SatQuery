"""
SatQuery AI — Pydantic v2 Data Validation and API Schemas
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Input Classification & Modality Enums
# ---------------------------------------------------------------------------
class InputClass(str, Enum):
    SINGLE_OPTICAL = "SINGLE_OPTICAL"
    SINGLE_SAR = "SINGLE_SAR"
    BI_TEMPORAL = "BI_TEMPORAL"
    OPTICAL_SAR = "OPTICAL_SAR"


class Modality(str, Enum):
    OPTICAL = "OPTICAL"
    SAR = "SAR"
    UNKNOWN = "UNKNOWN"

class RouterTask(str, Enum):
    SINGLE_VQA = "SINGLE_VQA"
    CAPTIONING = "CAPTIONING"
    GROUNDING = "GROUNDING"
    CHANGE_DETECTION = "CHANGE_DETECTION"
    CHANGE_VQA = "CHANGE_VQA"
    OPTICAL_SAR_ANALYSIS = "OPTICAL_SAR_ANALYSIS"

class RouterInputMode(str, Enum):
    SINGLE_OPTICAL = "SINGLE_OPTICAL"
    SINGLE_SAR = "SINGLE_SAR"
    BI_TEMPORAL_OPTICAL = "BI_TEMPORAL_OPTICAL"
    OPTICAL_SAR = "OPTICAL_SAR"

class RouterTool(str, Enum):
    GEOGROUND_ANALYZE = "geoground_analyze"
    SARCHAT_VQA = "sarchat_vqa"
    BIT_ANALYZE = "bit_analyze"
    GEOSPATIAL_VALIDATOR = "geospatial_validator"
    GEOCHAT_VQA = "geochat_vqa"
    GEOCHAT_DESCRIBE = "geochat_describe"
    BIT_CD = "bit_cd"
    FUSION_S1S2 = "fusion_s1s2"
    MOBILESAM = "mobilesam"
    VECTORIZER = "vectorizer"


# ---------------------------------------------------------------------------
# Spatial & Temporal Relationship Schemas
# ---------------------------------------------------------------------------
class SpatialRelationship(BaseModel):
    overlap_fraction_1: float = Field(..., ge=0.0, le=1.0, description="Overlap fraction relative to asset 1 area")
    overlap_fraction_2: float = Field(..., ge=0.0, le=1.0, description="Overlap fraction relative to asset 2 area")
    iou: float = Field(..., ge=0.0, le=1.0, description="Intersection over Union of footprints")
    intersection_bbox_wgs84: list[float] | None = Field(None, description="[min_lon, min_lat, max_lon, max_lat]")
    intersection_wkt: str | None = Field(None, description="WKT polygon of intersection")
    has_sufficient_overlap: bool = Field(..., description="Whether overlap meets minimum threshold")


class TemporalRelationship(BaseModel):
    date_1: datetime | None = None
    date_2: datetime | None = None
    days_difference: float | None = None
    is_distinct_time: bool = Field(..., description="True if acquisitions occurred at different timestamps")
    is_chronological: bool = Field(True, description="True if date_1 <= date_2")


# ---------------------------------------------------------------------------
# Input Classification Result Schema
# ---------------------------------------------------------------------------
class InputClassification(BaseModel):
    input_class: InputClass | None = Field(None, description="SINGLE_OPTICAL, SINGLE_SAR, BI_TEMPORAL, OPTICAL_SAR")
    valid: bool = Field(..., description="True if input configuration meets criteria for analysis")
    asset_ids: list[str] = Field(default_factory=list, description="IDs/keys of input assets analyzed")
    modalities: list[str] = Field(default_factory=list, description="Modalities of respective inputs")
    acquisition_dates: list[datetime | None] = Field(default_factory=list)
    spatial_relationship: SpatialRelationship | None = None
    temporal_relationship: TemporalRelationship | None = None
    validation_messages: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    refusal_reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Preprocessing Output Schemas
# ---------------------------------------------------------------------------
class TileReference(BaseModel):
    tile_id: str = Field(..., description="Unique identifier for the tile")
    tile_index: int = Field(..., description="Zero-based tile index in grid")
    source_asset_id: str = Field(..., description="Parent asset identifier")
    modality: str = Field(..., description="OPTICAL or SAR")
    file_path: str = Field(..., description="Path to generated tile raster/image file")
    col_off: int = Field(..., description="Column offset in source raster")
    row_off: int = Field(..., description="Row offset in source raster")
    width: int = Field(..., description="Tile width in pixels")
    height: int = Field(..., description="Tile height in pixels")
    bounds: list[float] = Field(..., description="[min_x, min_y, max_x, max_y] in spatial CRS")
    bounds_wgs84: list[float] | None = Field(None, description="[min_lon, min_lat, max_lon, max_lat]")
    bbox_wkt: str | None = Field(None, description="WKT polygon in spatial CRS")
    crs: str = Field(..., description="CRS of the tile coordinates")
    transform: list[float] | None = Field(None, description="Affine transform for this tile (a, b, c, d, e, f[, ...])")
    pair_tag: str | None = Field(None, description="Tag for paired tiles (t1, t2, optical, sar)")
    pair_tile_id: str | None = Field(None, description="Corresponding tile_id in paired modality/timestamp")
    acquisition_date: datetime | None = None


class TilePair(BaseModel):
    pair_index: int
    tile_id_1: str
    tile_id_2: str
    file_path_1: str
    file_path_2: str
    tag_1: str  # e.g., 't1' or 'optical'
    tag_2: str  # e.g., 't2' or 'sar'
    bounds: list[float]
    crs: str


class PreprocessResult(BaseModel):
    input_class: InputClass
    success: bool
    processed_assets: list[dict[str, Any]] = Field(default_factory=list)
    tile_references: list[TileReference] = Field(default_factory=list)
    tile_pairs: list[TilePair] | None = None
    preprocessing_steps: list[str] = Field(default_factory=list)
    spatial_reference: dict[str, Any] = Field(default_factory=dict)
    output_paths: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Project Schemas
# ---------------------------------------------------------------------------
class ProjectBase(BaseModel):
    name: str = Field(..., max_length=255, description="Project name")
    description: str | None = Field(None, description="Detailed project description")


class ProjectCreate(ProjectBase):
    pass


class ProjectResponse(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# Asset Schemas
# ---------------------------------------------------------------------------
class AssetMetadata(BaseModel):
    """Normalized metadata extracted from GeoTIFF / satellite headers."""
    format: str = Field(..., description="Raster format (e.g., GeoTIFF, TIFF)")
    modality: str = Field(..., description="Sensor modality (OPTICAL, SAR)")
    sensor: str | None = Field(None, description="Satellite sensor (e.g., Sentinel-2, RISAT)")
    crs: str | None = Field(None, description="Coordinate reference system (e.g., EPSG:4326)")
    width: int | None = Field(None, description="Raster width in pixels")
    height: int | None = Field(None, description="Raster height in pixels")
    bands: Any | None = Field(None, description="Band details and channel names")
    nodata: float | None = Field(None, description="Nodata pixel value")
    cloud_fraction: float | None = Field(None, ge=0.0, le=1.0, description="Cloud coverage fraction")
    acquired_at: datetime | None = Field(None, description="Timestamp of imagery acquisition")


class AssetCreate(AssetMetadata):
    job_id: uuid.UUID
    file_path: str = Field(..., max_length=1024)
    filename: str = Field(..., max_length=255)
    bbox_wkt: str | None = Field(None, description="WKT representation of footprint polygon")


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    file_path: str
    filename: str
    format: str
    modality: str
    sensor: str | None = None
    acquired_at: datetime | None = None
    crs: str | None = None
    width: int | None = None
    height: int | None = None
    bands: Any | None = None
    nodata: float | None = None
    cloud_fraction: float | None = None
    bbox: Any | None = Field(None, description="PostGIS geometry or GeoJSON representation")

    @field_validator("bbox", mode="before")
    @classmethod
    def convert_bbox(cls, v: Any) -> Any:
        if v is None:
            return None
        if hasattr(v, "data") or "WKBElement" in type(v).__name__:
            try:
                from geoalchemy2.shape import to_shape
                return to_shape(v).__geo_interface__
            except (ImportError, AttributeError, TypeError, ValueError):
                return str(v)
        return v


# ---------------------------------------------------------------------------
# Tool Registry & Tool Run Schemas
# ---------------------------------------------------------------------------
class ToolRegistryBase(BaseModel):
    tool_id: str = Field(..., max_length=64, description="Unique identifier (e.g., geochat_vqa, bit_cd)")
    name: str = Field(..., max_length=255)
    tool_type: str = Field(..., max_length=64, description="VLM, CHANGE_DETECTOR, SEGMENTATION, FUSION, UTILITY")
    model_name: str | None = Field(None, max_length=128)
    model_version: str | None = Field(None, max_length=64)
    description: str | None = None
    supported_tasks: list[str] | None = None
    supported_modalities: list[str] | None = None
    parameter_schema: dict[str, Any] | None = None
    enabled: bool = True


class ToolRegistryCreate(ToolRegistryBase):
    pass


class ToolRegistryResponse(ToolRegistryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class ToolRunCreate(BaseModel):
    job_id: uuid.UUID
    tool_id: uuid.UUID
    sequence_no: int = 1
    status: str = "pending"
    parameters: dict[str, Any] | None = None
    input_refs: Any | None = None
    output_refs: Any | None = None
    confidence: float | None = None
    latency_ms: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class ToolRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    tool_id: uuid.UUID
    sequence_no: int
    status: str
    parameters: dict[str, Any] | None = None
    input_refs: Any | None = None
    output_refs: Any | None = None
    confidence: float | None = None
    latency_ms: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Outputs & Trace Schemas
# ---------------------------------------------------------------------------
class OutputCreate(BaseModel):
    job_id: uuid.UUID
    output_type: str = Field(..., description="TEXT, MASK, GEOJSON, KML, REPORT_PDF, OVERLAY")
    text_result: str | None = None
    file_path: str | None = None
    mime_type: str | None = None
    confidence_label: str | None = None
    confidence_score: float | None = None


class OutputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    output_type: str
    text_result: str | None = None
    file_path: str | None = None
    mime_type: str | None = None
    confidence_label: str | None = None
    confidence_score: float | None = None
    created_at: datetime


class TraceCreate(BaseModel):
    job_id: uuid.UUID
    event_type: str = Field(..., description="NODE_START, NODE_END, TOOL_EXEC, ROUTING, REFUSAL, ERROR, FUSION")
    node_name: str | None = None
    tool_id: str | None = None
    model_version: str | None = None
    parameters: dict[str, Any] | None = None
    message: str | None = None
    trace_metadata: dict[str, Any] | None = None


class TraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    event_type: str
    node_name: str | None = None
    tool_id: str | None = None
    model_version: str | None = None
    parameters: dict[str, Any] | None = None
    message: str | None = None
    timestamp: datetime
    trace_metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Spatial Features Schemas
# ---------------------------------------------------------------------------
class SpatialFeatureCreate(BaseModel):
    job_id: uuid.UUID
    asset_id: uuid.UUID | None = None
    feature_type: str = Field(..., description="AOI, FOOTPRINT, CHANGE, GROUNDING")
    geometry_wkt: str = Field(..., description="WKT or GeoJSON geometry string")
    class_label: str | None = None
    confidence: float | None = None
    area_m2: float | None = None
    properties: dict[str, Any] | None = None


class SpatialFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    asset_id: uuid.UUID | None = None
    feature_type: str
    geometry: Any | None = Field(None, description="PostGIS geometry or GeoJSON representation")
    class_label: str | None = None
    confidence: float | None = None
    area_m2: float | None = None
    properties: dict[str, Any] | None = None
    created_at: datetime

    @field_validator("geometry", mode="before")
    @classmethod
    def convert_geometry(cls, v: Any) -> Any:
        if v is None:
            return None
        if hasattr(v, "data") or "WKBElement" in type(v).__name__:
            try:
                from geoalchemy2.shape import to_shape
                return to_shape(v).__geo_interface__
            except (AttributeError, ImportError, TypeError, ValueError):
                return str(v)
        return v


# ---------------------------------------------------------------------------
# Job Schemas & Route Models
# ---------------------------------------------------------------------------
class RouteRequest(BaseModel):
    query: str = Field(..., description="User question or analysis instruction")
    manifest: dict[str, Any] = Field(..., description="Extracted raster metadata and input modalities")


class RouteResponse(BaseModel):
    task: RouterTask = Field(..., description="Identified task from user intent")
    target: str | None = Field(None, description="Identified semantic target (e.g., BUILT_UP_AREA, SHIPS, VEGETATION)")
    operation: str | None = Field(None, description="Requested operation (e.g., SPATIAL_EXPANSION, DETECTION, IDENTIFICATION)")
    output_type: str | None = Field(None, description="Desired output format (e.g., TEXT, TEXT_AND_SPATIAL, SPATIAL_MASK)")
    requires_grounding: bool = Field(default=False, description="Whether intent requires spatial grounding")
    requires_change_analysis: bool = Field(default=False, description="Whether intent requires temporal change analysis")
    requires_optical_sar_analysis: bool = Field(default=False, description="Whether intent requires cross-modal optical+SAR analysis")
    input_mode: RouterInputMode | None = Field(None, description="Optional input configuration")
    tools: list[RouterTool] = Field(default_factory=list, description="Ordered list of tools")
    need_overlay: bool = True
    params: dict[str, Any] = Field(default_factory=dict)
    reasoning: str | None = Field(None, description="Explanation or classification provenance (Qwen-VL vs deterministic fallback)")


class JobCreate(BaseModel):
    project_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = Field(None, description="Reuse a job created by POST /ingest")
    query: str = Field(..., min_length=1, description="Natural language satellite query")
    input_mode: str | None = Field(None, description="SINGLE_OPTICAL, BI_TEMPORAL_OPTICAL, OPTICAL_SAR. Inferred from ingest when job_id is set.")
    task: str = Field(default="UNROUTED", description="SINGLE_VQA, CHANGE_VQA, GROUNDING, OPTICAL_SAR_FUSION. Qwen overwrites this during /run.")
    route_json: dict[str, Any] | None = None


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None = None
    session_id: uuid.UUID
    query: str
    input_mode: str
    task: str
    status: str
    route_json: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    assets: list[AssetResponse] = Field(default_factory=list)
    outputs: list[OutputResponse] = Field(default_factory=list)
    traces: list[TraceResponse] = Field(default_factory=list)
    spatial_features: list[SpatialFeatureResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Analyze UI contract (docs/api-spec.md JobView)
# ---------------------------------------------------------------------------
class JobAnswer(BaseModel):
    text: str | None = None
    model: str = "OpenGVLab/InternVL3-1B"
    backend: str = Field("mock", description="mock | internvl")
    confidence: str | None = None


class JobAssetView(BaseModel):
    filename: str
    modality: str
    sensor: str | None = None
    bounds_wgs84: list[float] | None = None
    preview_url: str | None = None


class JobOverlay(BaseModel):
    type: str = Field(..., description="FOOTPRINT | CHANGE | GROUNDING | UNCERTAIN | AGREEMENT")
    geojson_url: str
    confidence: float | None = None


class JobTraceView(BaseModel):
    event_type: str
    node_name: str | None = None
    tool_id: str | None = None
    message: str | None = None
    timestamp: str | None = None


class JobLulcTag(BaseModel):
    name: str
    score: float
    source: str | None = None


class JobLulcView(BaseModel):
    """Pixel fractions (Dynamic World 9-class) plus BigEarthNet-19 scene tags."""

    backend: str
    focus: str
    fractions: dict[str, float] = Field(default_factory=dict)
    scene_tags: list[JobLulcTag] = Field(default_factory=list)


class JobView(BaseModel):
    """Canonical document for GET /jobs/{id}. UI Zod schema must match."""

    job_id: str
    session_id: str
    status: str
    query: str = ""
    input_class: str = ""
    task: str = "UNROUTED"
    route: dict[str, Any] | None = None
    answer: JobAnswer | None = None
    assets: list[JobAssetView] = Field(default_factory=list)
    overlays: list[JobOverlay] = Field(default_factory=list)
    traces: list[JobTraceView] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    refusal_reason: str | None = None
    tile_count: int = 0
    lulc: JobLulcView | None = None
