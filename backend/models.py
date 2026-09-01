"""
SatQuery AI — SQLAlchemy 2.x Declarative Models
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Project(Base):
    """Optional top-level project container for grouping analysis jobs."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    jobs: Mapped[List["Job"]] = relationship(
        "Job",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class Job(Base):
    """Core analysis job record representing a single query run."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        index=True,
        nullable=False,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    input_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    task: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    route_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="jobs")
    assets: Mapped[List["Asset"]] = relationship(
        "Asset",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    tool_runs: Mapped[List["ToolRun"]] = relationship(
        "ToolRun",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ToolRun.sequence_no",
    )
    outputs: Mapped[List["Output"]] = relationship(
        "Output",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    traces: Mapped[List["Trace"]] = relationship(
        "Trace",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Trace.timestamp",
    )
    spatial_features: Mapped[List["SpatialFeature"]] = relationship(
        "SpatialFeature",
        back_populates="job",
        cascade="all, delete-orphan",
    )


class Asset(Base):
    """Metadata and bounding footprint for input/reference satellite rasters."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    modality: Mapped[str] = mapped_column(String(32), nullable=False)
    sensor: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    acquired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    crs: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bands: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    nodata: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cloud_fraction: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False),
        nullable=True,
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="assets")
    spatial_features: Mapped[List["SpatialFeature"]] = relationship(
        "SpatialFeature",
        back_populates="asset",
    )


class ToolRegistry(Base):
    """Fixed tool and model definitions available to the SatQuery orchestrator."""

    __tablename__ = "tool_registry"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tool_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supported_tasks: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    supported_modalities: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    parameter_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    runs: Mapped[List["ToolRun"]] = relationship("ToolRun", back_populates="tool")


class ToolRun(Base):
    """Record of an individual tool or model execution within a job."""

    __tablename__ = "tool_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tool_registry.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    input_refs: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    output_refs: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="tool_runs")
    tool: Mapped["ToolRegistry"] = relationship("ToolRegistry", back_populates="runs")


class Output(Base):
    """Generated analysis artifacts (text results, mask paths, GeoJSON, reports)."""

    __tablename__ = "outputs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    output_type: Mapped[str] = mapped_column(String(64), nullable=False)
    text_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    confidence_label: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="outputs")


class Trace(Base):
    """Persistent audit trail and execution trace for observable agentic workflow."""

    __tablename__ = "traces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    node_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tool_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    trace_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="traces")


class SpatialFeature(Base):
    """Vector evidence layer (AOI polygons, footprint bounds, change multipolygons, grounding)."""

    __tablename__ = "spatial_features"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    feature_type: Mapped[str] = mapped_column(String(64), nullable=False)
    geometry: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
        nullable=False,
    )
    class_label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    properties: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="spatial_features")
    asset: Mapped[Optional["Asset"]] = relationship("Asset", back_populates="spatial_features")
