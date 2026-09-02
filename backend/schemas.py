"""
SatQuery AI — Pydantic v2 Data Validation and API Schemas
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
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


# ---------------------------------------------------------------------------
# Spatial & Temporal Relationship Schemas
# ---------------------------------------------------------------------------
class SpatialRelationship(BaseModel):
    overlap_fraction_1: float = Field(..., ge=0.0, le=1.0, description="Overlap fraction relative to asset 1 area")
    overlap_fraction_2: float = Field(..., ge=0.0, le=1.0, description="Overlap fraction relative to asset 2 area")
    iou: float = Field(..., ge=0.0, le=1.0, description="Intersection over Union of footprints")
    intersection_bbox_wgs84: Optional[List[float]] = Field(None, description="[min_lon, min_lat, max_lon, max_lat]")
    intersection_wkt: Optional[str] = Field(None, description="WKT polygon of intersection")
    has_sufficient_overlap: bool = Field(..., description="Whether overlap meets minimum threshold")


class TemporalRelationship(BaseModel):
    date_1: Optional[datetime] = None
    date_2: Optional[datetime] = None
    days_difference: Optional[float] = None
    is_distinct_time: bool = Field(..., description="True if acquisitions occurred at different timestamps")
    is_chronological: bool = Field(True, description="True if date_1 <= date_2")


# ---------------------------------------------------------------------------
# Input Classification Result Schema
# ---------------------------------------------------------------------------
class InputClassification(BaseModel):
    input_class: Optional[InputClass] = Field(None, description="SINGLE_OPTICAL, SINGLE_SAR, BI_TEMPORAL, OPTICAL_SAR")
    valid: bool = Field(..., description="True if input configuration meets criteria for analysis")
    asset_ids: List[str] = Field(default_factory=list, description="IDs/keys of input assets analyzed")
    modalities: List[str] = Field(default_factory=list, description="Modalities of respective inputs")
    acquisition_dates: List[Optional[datetime]] = Field(default_factory=list)
    spatial_relationship: Optional[SpatialRelationship] = None
    temporal_relationship: Optional[TemporalRelationship] = None
    validation_messages: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    refusal_reason: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


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
    bounds: List[float] = Field(..., description="[min_x, min_y, max_x, max_y] in spatial CRS")
    bounds_wgs84: Optional[List[float]] = Field(None, description="[min_lon, min_lat, max_lon, max_lat]")
    bbox_wkt: Optional[str] = Field(None, description="WKT polygon in spatial CRS")
    crs: str = Field(..., description="CRS of the tile coordinates")
    pair_tag: Optional[str] = Field(None, description="Tag for paired tiles (t1, t2, optical, sar)")
    pair_tile_id: Optional[str] = Field(None, description="Corresponding tile_id in paired modality/timestamp")
    acquisition_date: Optional[datetime] = None


class TilePair(BaseModel):
    pair_index: int
    tile_id_1: str
    tile_id_2: str
    file_path_1: str
    file_path_2: str
    tag_1: str  # e.g., 't1' or 'optical'
    tag_2: str  # e.g., 't2' or 'sar'
    bounds: List[float]
    crs: str


class PreprocessResult(BaseModel):
    input_class: InputClass
    success: bool
    processed_assets: List[Dict[str, Any]] = Field(default_factory=list)
    tile_references: List[TileReference] = Field(default_factory=list)
    tile_pairs: Optional[List[TilePair]] = None
    preprocessing_steps: List[str] = Field(default_factory=list)
    spatial_reference: Dict[str, Any] = Field(default_factory=dict)
    output_paths: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Project Schemas
# ---------------------------------------------------------------------------
class ProjectBase(BaseModel):
    name: str = Field(..., max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Detailed project description")


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
    sensor: Optional[str] = Field(None, description="Satellite sensor (e.g., Sentinel-2, RISAT)")
    crs: Optional[str] = Field(None, description="Coordinate reference system (e.g., EPSG:4326)")
    width: Optional[int] = Field(None, description="Raster width in pixels")
    height: Optional[int] = Field(None, description="Raster height in pixels")
    bands: Optional[Any] = Field(None, description="Band details and channel names")
    nodata: Optional[float] = Field(None, description="Nodata pixel value")
    cloud_fraction: Optional[float] = Field(None, ge=0.0, le=1.0, description="Cloud coverage fraction")
    acquired_at: Optional[datetime] = Field(None, description="Timestamp of imagery acquisition")


class AssetCreate(AssetMetadata):
    job_id: uuid.UUID
    file_path: str = Field(..., max_length=1024)
    filename: str = Field(..., max_length=255)
    bbox_wkt: Optional[str] = Field(None, description="WKT representation of footprint polygon")


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    file_path: str
    filename: str
    format: str
    modality: str
    sensor: Optional[str] = None
    acquired_at: Optional[datetime] = None
    crs: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    bands: Optional[Any] = None
    nodata: Optional[float] = None
    cloud_fraction: Optional[float] = None
    bbox: Optional[Any] = Field(None, description="PostGIS geometry or GeoJSON representation")

    @field_validator("bbox", mode="before")
    @classmethod
    def convert_bbox(cls, v: Any) -> Any:
        if v is None:
            return None
        if hasattr(v, "data") or "WKBElement" in type(v).__name__:
            try:
                from geoalchemy2.shape import to_shape
                return to_shape(v).__geo_interface__
            except Exception:
                return str(v)
        return v


# ---------------------------------------------------------------------------
# Tool Registry & Tool Run Schemas
# ---------------------------------------------------------------------------
class ToolRegistryBase(BaseModel):
    tool_id: str = Field(..., max_length=64, description="Unique identifier (e.g., geochat_vqa, bit_cd)")
    name: str = Field(..., max_length=255)
    tool_type: str = Field(..., max_length=64, description="VLM, CHANGE_DETECTOR, SEGMENTATION, FUSION, UTILITY")
    model_name: Optional[str] = Field(None, max_length=128)
    model_version: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = None
    supported_tasks: Optional[List[str]] = None
    supported_modalities: Optional[List[str]] = None
    parameter_schema: Optional[Dict[str, Any]] = None
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
    parameters: Optional[Dict[str, Any]] = None
    input_refs: Optional[Any] = None
    output_refs: Optional[Any] = None
    confidence: Optional[float] = None
    latency_ms: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ToolRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    tool_id: uuid.UUID
    sequence_no: int
    status: str
    parameters: Optional[Dict[str, Any]] = None
    input_refs: Optional[Any] = None
    output_refs: Optional[Any] = None
    confidence: Optional[float] = None
    latency_ms: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Outputs & Trace Schemas
# ---------------------------------------------------------------------------
class OutputCreate(BaseModel):
    job_id: uuid.UUID
    output_type: str = Field(..., description="TEXT, MASK, GEOJSON, KML, REPORT_PDF, OVERLAY")
    text_result: Optional[str] = None
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    confidence_label: Optional[str] = None
    confidence_score: Optional[float] = None


class OutputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    output_type: str
    text_result: Optional[str] = None
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    confidence_label: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: datetime


class TraceCreate(BaseModel):
    job_id: uuid.UUID
    event_type: str = Field(..., description="NODE_START, NODE_END, TOOL_EXEC, ROUTING, REFUSAL, ERROR, FUSION")
    node_name: Optional[str] = None
    tool_id: Optional[str] = None
    model_version: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    trace_metadata: Optional[Dict[str, Any]] = None


class TraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    event_type: str
    node_name: Optional[str] = None
    tool_id: Optional[str] = None
    model_version: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    timestamp: datetime
    trace_metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Spatial Features Schemas
# ---------------------------------------------------------------------------
class SpatialFeatureCreate(BaseModel):
    job_id: uuid.UUID
    asset_id: Optional[uuid.UUID] = None
    feature_type: str = Field(..., description="AOI, FOOTPRINT, CHANGE, GROUNDING")
    geometry_wkt: str = Field(..., description="WKT or GeoJSON geometry string")
    class_label: Optional[str] = None
    confidence: Optional[float] = None
    area_m2: Optional[float] = None
    properties: Optional[Dict[str, Any]] = None


class SpatialFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    asset_id: Optional[uuid.UUID] = None
    feature_type: str
    geometry: Optional[Any] = Field(None, description="PostGIS geometry or GeoJSON representation")
    class_label: Optional[str] = None
    confidence: Optional[float] = None
    area_m2: Optional[float] = None
    properties: Optional[Dict[str, Any]] = None
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
            except Exception:
                return str(v)
        return v


# ---------------------------------------------------------------------------
# Job Schemas & Route Models
# ---------------------------------------------------------------------------
class RouteRequest(BaseModel):
    query: str = Field(..., description="User question or analysis instruction")
    manifest: Dict[str, Any] = Field(..., description="Extracted raster metadata and input modalities")


class RouteResponse(BaseModel):
    task: str = Field(..., description="Identified task (SINGLE_VQA, CHANGE_VQA, OPTICAL_SAR_FUSION, etc.)")
    input_mode: str = Field(..., description="Input configuration (SINGLE_OPTICAL, BI_TEMPORAL_OPTICAL, OPTICAL_SAR)")
    tools: List[str] = Field(..., description="Ordered list of tools to execute")
    need_overlay: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)


class JobCreate(BaseModel):
    project_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    query: str = Field(..., min_length=1, description="Natural language satellite query")
    input_mode: str = Field(..., description="SINGLE_OPTICAL, BI_TEMPORAL_OPTICAL, OPTICAL_SAR")
    task: str = Field(..., description="SINGLE_VQA, CHANGE_VQA, GROUNDING, OPTICAL_SAR_FUSION")
    route_json: Optional[Dict[str, Any]] = None


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    session_id: uuid.UUID
    query: str
    input_mode: str
    task: str
    status: str
    route_json: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    assets: List[AssetResponse] = Field(default_factory=list)
    outputs: List[OutputResponse] = Field(default_factory=list)
    traces: List[TraceResponse] = Field(default_factory=list)
    spatial_features: List[SpatialFeatureResponse] = Field(default_factory=list)
