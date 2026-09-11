"""
SatQuery AI — Utility Functions for Database, File Management, and Geospatial Helpers
"""
import hashlib
import uuid
from pathlib import Path
from typing import Any
import sys
from src.logger import logging
from src.exception import CustomException

from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import box, shape
from shapely import wkt

from backend.config import settings

# Supported satellite raster and artifact extensions
ALLOWED_RASTER_EXTENSIONS = {".tif", ".tiff", ".geotiff", ".png", ".jpg", ".jpeg"}
ALLOWED_VECTOR_EXTENSIONS = {".geojson", ".json", ".kml", ".shp"}
ALLOWED_REPORT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


# ---------------------------------------------------------------------------
# UUID Utilities
# ---------------------------------------------------------------------------
def generate_uuid() -> uuid.UUID:
    """Generate a standard UUIDv4."""
    return uuid.uuid4()


def is_valid_uuid(val: Any) -> bool:
    """Check if a given value or string is a valid UUID."""
    if isinstance(val, uuid.UUID):
        return True
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def parse_uuid(val: str | uuid.UUID) -> uuid.UUID:
    """Parse a string into a UUID object, raising ValueError if invalid."""
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(str(val))


# ---------------------------------------------------------------------------
# File & Storage Utilities
# ---------------------------------------------------------------------------
def validate_file_extension(filename: str, allowed_extensions: set | None = None) -> bool:
    """Validate whether the file extension is within the allowed set."""
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_RASTER_EXTENSIONS | ALLOWED_VECTOR_EXTENSIONS | ALLOWED_REPORT_EXTENSIONS
    suffix = Path(filename).suffix.lower()
    return suffix in allowed_extensions


def calculate_file_hash(file_path: str | Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file for integrity tracking and caching."""
    path = Path(file_path)
    if not path.exists():
        logging.error(f"File not found for hashing: {file_path}")
        raise CustomException(f"File not found for hashing: {file_path}", sys)
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_job_directory(job_id: str | uuid.UUID, base_dir: Path | None = None) -> dict[str, Path]:
    """
    Create the standardized SatQuery storage directory structure on disk for a job.
    
    Structure:
    data/jobs/{job_id}/
        ├── raw/         (uploaded source GeoTIFFs)
        ├── processed/   (resampled, cropped, aligned rasters)
        ├── tiles/       (256x256 tiles for BIT / VLM crops)
        ├── masks/       (generated binary/multiclass change masks)
        ├── vectors/     (exported GeoJSON, KML spatial footprints)
        └── reports/     (generated PDF summaries & plots)
    """
    base = base_dir or settings.full_job_storage_dir
    job_dir = base / str(job_id)

    subdirs = {
        "root": job_dir,
        "raw": job_dir / "raw",
        "processed": job_dir / "processed",
        "tiles": job_dir / "tiles",
        "masks": job_dir / "masks",
        "vectors": job_dir / "vectors",
        "reports": job_dir / "reports",
    }

    for path in subdirs.values():
        path.mkdir(parents=True, exist_ok=True)

    return subdirs


# ---------------------------------------------------------------------------
# Geospatial & PostGIS Helpers
# ---------------------------------------------------------------------------
def bbox_to_geometry(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    srid: int = 4326,
) -> WKBElement:
    """Create a PostGIS WKBElement Polygon from bounding box coordinates (min_x, min_y, max_x, max_y)."""
    polygon_shape = box(min_x, min_y, max_x, max_y)
    return from_shape(polygon_shape, srid=srid)


def wkt_to_geometry(wkt_str: str, srid: int = 4326) -> WKBElement:
    """Convert a WKT string to a GeoAlchemy2 PostGIS WKBElement."""
    geom_shape = wkt.loads(wkt_str)
    return from_shape(geom_shape, srid=srid)


def geojson_to_geometry(geojson_dict: dict[str, Any], srid: int = 4326) -> WKBElement:
    """Convert a GeoJSON geometry dictionary to a PostGIS WKBElement."""
    geom_shape = shape(geojson_dict)
    return from_shape(geom_shape, srid=srid)


def geometry_to_geojson(geom: WKBElement | None) -> dict[str, Any] | None:
    """Convert a PostGIS WKBElement geometry to a GeoJSON mapping."""
    if geom is None:
        return None
    try:
        shapely_geom = to_shape(geom)
        return shapely_geom.__geo_interface__
    except Exception as e:
        logging.error(f"Error converting geometry to geojson: {e}")
        raise CustomException(e, sys)


def geometry_to_wkt(geom: WKBElement | None) -> str | None:
    """Convert a PostGIS WKBElement geometry to a WKT string."""
    if geom is None:
        return None
    try:
        shapely_geom = to_shape(geom)
        return shapely_geom.wkt
    except Exception as e:
        logging.error(f"Error converting geometry to wkt: {e}")
        raise CustomException(e, sys)


# ---------------------------------------------------------------------------
# Metadata & Confidence Helpers
# ---------------------------------------------------------------------------
def normalize_confidence(score: float | None) -> tuple[str, float]:
    """
    Normalize confidence score to a (ConfidenceLabel, clamped_score) pair.
    Labels: HIGH (>= 0.75), MEDIUM (>= 0.45), LOW (< 0.45).
    """
    if score is None:
        return "MEDIUM", 0.50
    clamped = max(0.0, min(1.0, float(score)))
    if clamped >= 0.75:
        label = "HIGH"
    elif clamped >= 0.45:
        label = "MEDIUM"
    else:
        label = "LOW"
    return label, round(clamped, 4)


def serialize_trace_event(
    event_type: str,
    node_name: str | None = None,
    tool_id: str | None = None,
    message: str | None = None,
    parameters: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize an execution trace event for persistence into the traces table."""
    return {
        "event_type": event_type,
        "node_name": node_name,
        "tool_id": tool_id,
        "message": message,
        "parameters": parameters or {},
        "metadata": metadata or {},
    }
