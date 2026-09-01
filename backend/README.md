# SatQuery AI — Database Foundation & Backend Architecture

This document provides the technical overview and operational guide for the SatQuery AI database foundation.

---

## 1. Overview

SatQuery AI couples an in-memory execution pipeline with a relational + spatial persistent storage layer:
- **In-Memory (`SessionContext` / `SatQueryState`)**: Holds active request state, intermediate model tensors, and tool inputs during the LangGraph execution.
- **PostgreSQL 17 + PostGIS 3.6 (`satquery` database)**: Persists completed jobs, asset metadata, tool registries, execution traces, generated output manifests, and vector evidence (polygons, footprints, and change masks).
- **Disk Storage (`data/jobs/{job_id}/...`)**: Stores multi-gigabyte satellite rasters (GeoTIFFs), resampled tiles, binary mask rasters, vector files, and PDF reports.

```
projects (optional)
   ↓ 1:N
jobs
 ├── assets             (spatial bbox footprint via PostGIS Geometry)
 ├── tool_runs          (execution telemetry & status per tool)
 │    └── tool_registry (catalog of fixed models/tools: GeoChat, BIT, SAM, etc.)
 ├── outputs            (references to generated files: masks, reports, text)
 ├── traces             (observable audit log for LangGraph nodes & specialists)
 └── spatial_features   (PostGIS Geometry: AOIs, change polygons, grounding)
```

---

## 2. Why PostGIS & Storage Design Rationale

### Why PostGIS?
- **Genuine Spatial Operations**: SatQuery processes Earth Observation data. Storing bounding boxes and polygons as plain text or JSON makes spatial filtering (`ST_Intersects`, `ST_Contains`, `ST_Area`, `ST_Union`) slow and unindexed.
- **Spatial Indexing**: PostGIS provides R-Tree based GIST indexes (`idx_assets_bbox`, `idx_spatial_features_geometry`) enabling sub-millisecond bounding box and AOI spatial queries across thousands of satellite scenes.
- **Multipolygon & Coordinate Reference Systems**: PostGIS natively understands EPSG:4326 (WGS84 lat/lon) and coordinate transformations for accurate geodesic area and perimeter measurements.

### Why Imagery is Stored on Disk (Not in PostgreSQL)
- High-resolution multispectral scenes (Sentinel-2, Cartosat-2S, RISAT) are hundreds of megabytes to gigabytes.
- Storing large binary BLOBs in PostgreSQL causes database bloat, exhausts connection pool memory, slows down backups, and hurts write-ahead logging (WAL).
- SatQuery uses a clean separation of concerns:
  - **Rasterio / Disk**: `data/jobs/{job_id}/raw/`, `processed/`, `tiles/`, `masks/`
  - **PostgreSQL / PostGIS**: Stores paths, metadata, band descriptions, acquisition timestamps, spatial footprints, confidence scores, and audit traces.

---

## 3. Database Schema Reference

| Table | Description | Key Fields |
|---|---|---|
| `projects` | Container for grouping related analysis jobs | `id` (UUID), `name`, `description`, `created_at` |
| `jobs` | Analysis run corresponding to a user query | `id` (UUID), `project_id`, `session_id`, `query`, `input_mode`, `task`, `status`, `route_json`, `started_at`, `completed_at`, `error_message` |
| `assets` | Satellite raster metadata & footprint | `id` (UUID), `job_id`, `file_path`, `filename`, `format`, `modality`, `sensor`, `crs`, `width`, `height`, `bands` (JSONB), `nodata`, `cloud_fraction`, `bbox` (PostGIS Polygon) |
| `tool_registry` | Fixed orchestrator tools / models catalog | `id` (UUID), `tool_id` (Unique string), `name`, `tool_type`, `model_name`, `model_version`, `supported_tasks` (JSONB), `supported_modalities` (JSONB), `parameter_schema` (JSONB), `enabled` |
| `tool_runs` | Individual tool executions within a job | `id` (UUID), `job_id`, `tool_id`, `sequence_no`, `status`, `parameters` (JSONB), `input_refs` (JSONB), `output_refs` (JSONB), `confidence`, `latency_ms` |
| `outputs` | Derived artifacts (text, masks, reports) | `id` (UUID), `job_id`, `output_type`, `text_result`, `file_path`, `mime_type`, `confidence_label`, `confidence_score` |
| `traces` | Observable audit log for evaluation | `id` (UUID), `job_id`, `event_type`, `node_name`, `tool_id`, `model_version`, `parameters` (JSONB), `message`, `metadata` (JSONB), `timestamp` |
| `spatial_features` | Vector evidence layer | `id` (UUID), `job_id`, `asset_id`, `feature_type` (AOI, CHANGE, FOOTPRINT, GROUNDING), `geometry` (PostGIS Geometry), `class_label`, `confidence`, `area_m2`, `properties` (JSONB) |

---

## 4. Environment Configuration

Configuration is loaded from environment variables or `.env`:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://localhost/satquery` | PostgreSQL connection string using `psycopg3` |
| `ENVIRONMENT` | `development` | Deployment environment (`development` / `production`) |
| `LOG_LEVEL` | `INFO` | Application log verbosity |
| `DATA_DIR` | `data` | Base directory for file storage |
| `JOB_STORAGE_PATH` | `data/jobs` | Job artifact directory |
| `DEFAULT_SRID` | `4326` | Spatial Reference System ID (WGS84) |

---

## 5. Alembic Migrations

Alembic manages all schema changes:

```bash
# Activate virtual environment
source venv/bin/activate

# Apply migrations to satquery database
alembic upgrade head

# Generate a new migration after editing models.py
alembic revision --autogenerate -m "description_of_change"

# Roll back the most recent migration
alembic downgrade -1
```

---

## 6. How to Run Verification Tests

Run the standalone database verification test:

```bash
./venv/bin/python test_database_foundation.py
```

---

## 7. Starting the Backend (Future Phases)

When the FastAPI routers and LangGraph state graph are implemented:

```bash
./venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
