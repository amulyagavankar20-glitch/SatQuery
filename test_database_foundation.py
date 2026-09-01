"""
SatQuery AI — Comprehensive Database Foundation Verification Test
"""
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, text, func
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Polygon, MultiPolygon, box

from backend.config import settings
from backend.database import SessionLocal, engine, check_db_connection
from backend.models import (
    Base,
    Project,
    Job,
    Asset,
    ToolRegistry,
    ToolRun,
    Output,
    Trace,
    SpatialFeature,
)
from backend.schemas import (
    JobResponse,
    JobStatusResponse,
    AssetResponse,
    SpatialFeatureResponse,
    ToolRegistryResponse,
    ToolRunResponse,
    OutputResponse,
    TraceResponse,
)
from backend.utils import (
    create_job_directory,
    validate_file_extension,
    calculate_file_hash,
    bbox_to_geometry,
    wkt_to_geometry,
    geometry_to_geojson,
    geometry_to_wkt,
    normalize_confidence,
)


def run_all_tests():
    print("==================================================")
    print("1. VERIFYING DATABASE CONNECTION & POSTGIS")
    print("==================================================")
    status = check_db_connection()
    print("DB Connection Status:", status["status"])
    print("Database Version:", status["database_version"])
    print("PostGIS Full Version:", status["postgis_version"])
    assert "3.6" in status["postgis_version"] or "PostGIS" in status["postgis_version"]

    print("\n==================================================")
    print("2. VERIFYING CREATED TABLES IN POSTGRESQL")
    print("==================================================")
    expected_tables = {
        "projects",
        "jobs",
        "assets",
        "tool_registry",
        "tool_runs",
        "outputs",
        "traces",
        "spatial_features",
    }
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
        )
        existing_tables = {r[0] for r in res.fetchall()}
        print("Existing public tables:", sorted(list(existing_tables)))
        for table in expected_tables:
            assert table in existing_tables, f"Missing table: {table}"
            print(f"  [OK] Table '{table}' verified.")

    print("\n==================================================")
    print("3. VERIFYING POSTGIS GEOMETRY COLUMNS & INDEXES")
    print("==================================================")
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT f_table_name, f_geometry_column, type, srid FROM geometry_columns WHERE f_table_schema='public';")
        )
        geom_cols = { (r[0], r[1]): (r[2], r[3]) for r in res.fetchall() }
        print("Registered geometry columns:", geom_cols)
        assert ("assets", "bbox") in geom_cols, "assets.bbox not registered in geometry_columns"
        assert ("spatial_features", "geometry") in geom_cols, "spatial_features.geometry not registered in geometry_columns"
        print("  [OK] assets.bbox type:", geom_cols[("assets", "bbox")])
        print("  [OK] spatial_features.geometry type:", geom_cols[("spatial_features", "geometry")])

        # Test direct spatial query
        area_test = conn.execute(
            text("SELECT ST_Area(ST_GeomFromText('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))', 4326)::geography);")
        ).scalar()
        print(f"  [OK] PostGIS ST_Area query calculated: {area_test:.2f} m²")

    print("\n==================================================")
    print("4. VERIFYING ORM CRUD, RELATIONSHIPS & POSTGIS STORAGE")
    print("==================================================")
    db = SessionLocal()
    try:
        test_tool_id = f"geochat_vqa_test_{uuid.uuid4().hex[:6]}"
        # A. Create Tool in ToolRegistry
        tool = ToolRegistry(
            tool_id=test_tool_id,
            name="GeoChat 7B VQA Specialist",
            tool_type="VLM",
            model_name="GeoChat-7B",
            model_version="4bit-lora-ben-v1",
            description="Talking VLM for satellite VQA and natural language captioning",
            supported_tasks=["SINGLE_VQA", "CHANGE_VQA"],
            supported_modalities=["OPTICAL"],
            parameter_schema={"temperature": 0.0, "max_new_tokens": 256},
            enabled=True,
        )
        db.add(tool)
        db.flush()
        print(f"  [OK] Inserted ToolRegistry item: {tool.tool_id} (ID: {tool.id})")

        # B. Create Project
        project = Project(
            name="ISRO Coastal Monitoring 2026",
            description="Monitoring land-use change and water boundary shifts",
        )
        db.add(project)
        db.flush()
        print(f"  [OK] Inserted Project: {project.name} (ID: {project.id})")

        # C. Create Job
        job = Job(
            project_id=project.id,
            session_id=uuid.uuid4(),
            query="Detect coastal erosion and describe newly formed water bodies",
            input_mode="BI_TEMPORAL_OPTICAL",
            task="CHANGE_VQA",
            status="running",
            route_json={
                "task": "CHANGE_VQA",
                "input_mode": "BI_TEMPORAL_OPTICAL",
                "tools": ["geospatial_validator", "bit_cd", "vectorizer", "geochat_vqa"],
                "need_overlay": True,
            },
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.flush()
        print(f"  [OK] Inserted Job: {job.id} (Task: {job.task})")

        # D. Create Asset with Bounding Box Geometry
        # Bounding box around a sample area in EPSG:4326: min_x=72.8, min_y=18.9, max_x=73.0, max_y=19.1 (Mumbai coast)
        asset_bbox = bbox_to_geometry(72.80, 18.90, 73.00, 19.10, srid=4326)
        asset = Asset(
            job_id=job.id,
            file_path="data/jobs/" + str(job.id) + "/raw/sentinel2_t1.tif",
            filename="sentinel2_t1.tif",
            format="GeoTIFF",
            modality="OPTICAL",
            sensor="Sentinel-2",
            crs="EPSG:4326",
            width=2048,
            height=2048,
            bands=["B02", "B03", "B04", "B08"],
            nodata=0.0,
            cloud_fraction=0.02,
            bbox=asset_bbox,
            acquired_at=datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
        )
        db.add(asset)
        db.flush()
        print(f"  [OK] Inserted Asset: {asset.filename} with PostGIS polygon bbox")

        # E. Create Spatial Features (AOI and CHANGE MultiPolygon)
        aoi_geom = wkt_to_geometry("POLYGON((72.82 18.92, 72.82 19.05, 72.98 19.05, 72.98 18.92, 72.82 18.92))", srid=4326)
        sf_aoi = SpatialFeature(
            job_id=job.id,
            asset_id=asset.id,
            feature_type="AOI",
            geometry=aoi_geom,
            class_label="Region of Interest",
            confidence=1.0,
            area_m2=1250000.0,
            properties={"name": "Harbor Zone AOI"},
        )
        db.add(sf_aoi)

        change_geom = wkt_to_geometry(
            "MULTIPOLYGON(((72.85 18.95, 72.85 18.97, 72.87 18.97, 72.87 18.95, 72.85 18.95)),"
            "((72.90 19.00, 72.90 19.02, 72.92 19.02, 72.92 19.00, 72.90 19.00)))",
            srid=4326
        )
        sf_change = SpatialFeature(
            job_id=job.id,
            asset_id=asset.id,
            feature_type="CHANGE",
            geometry=change_geom,
            class_label="Water expansion",
            confidence=0.89,
            area_m2=45000.0,
            properties={"method": "BIT_CD", "change_class": "water"},
        )
        db.add(sf_change)
        db.flush()
        print(f"  [OK] Inserted SpatialFeatures: AOI and CHANGE MultiPolygon")

        # F. Create ToolRun
        tool_run = ToolRun(
            job_id=job.id,
            tool_id=tool.id,
            sequence_no=1,
            status="success",
            parameters={"tile_size": 256, "crop_coords": [72.85, 18.95, 72.87, 18.97]},
            input_refs=["sentinel2_t1.tif", "sentinel2_t2.tif"],
            output_refs=["change_mask_crop.png"],
            confidence=0.88,
            latency_ms=1840.5,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(tool_run)

        # G. Create Output
        output_mask = Output(
            job_id=job.id,
            output_type="MASK",
            file_path="data/jobs/" + str(job.id) + "/masks/change_mask.tif",
            mime_type="image/tiff",
            confidence_label="HIGH",
            confidence_score=0.89,
        )
        output_text = Output(
            job_id=job.id,
            output_type="TEXT",
            text_result="Significant water expansion detected along the northern shoreline covering approximately 4.5 hectares.",
            confidence_label="HIGH",
            confidence_score=0.89,
        )
        db.add_all([output_mask, output_text])

        # H. Create Trace
        trace1 = Trace(
            job_id=job.id,
            event_type="NODE_START",
            node_name="bit_cd",
            tool_id="bit_cd",
            model_version="bit-resnet18-v1",
            parameters={"threshold": 0.5},
            message="Starting bitemporal change inference on 256x256 tiles",
            trace_metadata={"gpu_allocated_mb": 1420},
        )
        trace2 = Trace(
            job_id=job.id,
            event_type="NODE_END",
            node_name="geochat_vqa",
            tool_id="geochat_vqa",
            model_version="geochat-7b-qlora-ben-v1",
            parameters={"temperature": 0.0},
            message="Generated natural language explanation for detected change region",
            trace_metadata={"confidence": 0.88, "tokens_generated": 48},
        )
        db.add_all([trace1, trace2])

        db.commit()
        print("  [OK] Successfully committed all records with transactions and foreign keys!")

        # -------------------------------------------------------------------
        # Verification Queries via SQLAlchemy 2.0 select()
        # -------------------------------------------------------------------
        print("\n==================================================")
        print("5. VERIFYING ORM QUERIES & RELATIONSHIP TRAVERSAL")
        print("==================================================")
        stmt = select(Job).where(Job.id == job.id)
        fetched_job = db.scalars(stmt).one()

        assert fetched_job.project.name == "ISRO Coastal Monitoring 2026"
        assert len(fetched_job.assets) == 1
        assert len(fetched_job.spatial_features) == 2
        assert len(fetched_job.tool_runs) == 1
        assert len(fetched_job.outputs) == 2
        assert len(fetched_job.traces) == 2

        print(f"  [OK] Fetched Job query: '{fetched_job.query}'")
        print(f"  [OK] Job -> Project: '{fetched_job.project.name}'")
        print(f"  [OK] Job -> Assets: {len(fetched_job.assets)} asset(s)")
        print(f"  [OK] Job -> ToolRuns: {len(fetched_job.tool_runs)} run(s) with tool '{fetched_job.tool_runs[0].tool.name}'")
        print(f"  [OK] Job -> Outputs: {len(fetched_job.outputs)} output(s)")
        print(f"  [OK] Job -> Traces: {len(fetched_job.traces)} trace(s)")
        print(f"  [OK] Job -> SpatialFeatures: {len(fetched_job.spatial_features)} feature(s)")

        # Verify PostGIS functions via ORM
        spatial_query = select(
            SpatialFeature.feature_type,
            func.ST_AsGeoJSON(SpatialFeature.geometry).label("geojson"),
            func.ST_Area(func.ST_Transform(SpatialFeature.geometry, 3857)).label("area_sqm"),
        ).where(SpatialFeature.job_id == job.id)
        spatial_results = db.execute(spatial_query).fetchall()
        for s_type, geojson, area in spatial_results:
            print(f"  [OK] PostGIS ST_AsGeoJSON for {s_type}: {geojson[:60]}... Area (WebMercator): {area:.1f} m²")

        # -------------------------------------------------------------------
        # Verification of Pydantic v2 Schemas
        # -------------------------------------------------------------------
        print("\n==================================================")
        print("6. VERIFYING PYDANTIC V2 SCHEMA SERIALIZATION")
        print("==================================================")
        job_response = JobStatusResponse.model_validate(fetched_job)
        print(f"  [OK] JobStatusResponse validated: status={job_response.status}, id={job_response.id}")

        full_job_resp = JobResponse.model_validate(fetched_job)
        print(f"  [OK] Full JobResponse validated with {len(full_job_resp.assets)} asset(s), {len(full_job_resp.outputs)} output(s), {len(full_job_resp.traces)} trace(s), {len(full_job_resp.spatial_features)} spatial feature(s)")

        tool_resp = ToolRegistryResponse.model_validate(fetched_job.tool_runs[0].tool)
        print(f"  [OK] ToolRegistryResponse validated: tool_id={tool_resp.tool_id}")

        trace_resp = TraceResponse.model_validate(fetched_job.traces[0])
        print(f"  [OK] TraceResponse validated: event_type={trace_resp.event_type}, metadata={trace_resp.trace_metadata}")

        # Test storage utils
        job_dirs = create_job_directory(job.id)
        assert job_dirs["raw"].exists()
        assert job_dirs["processed"].exists()
        assert job_dirs["tiles"].exists()
        assert job_dirs["masks"].exists()
        assert job_dirs["vectors"].exists()
        assert job_dirs["reports"].exists()
        print(f"  [OK] Job disk storage directories verified at: {job_dirs['root']}")

        # Clean up test records
        db.delete(fetched_job.project)  # CASCADE deletes job and child records
        db.delete(tool)
        db.commit()
        print("  [OK] Cleaned up test records from satquery database.")

    finally:
        db.close()

    print("\n==================================================")
    print("ALL DATABASE FOUNDATION VERIFICATION TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()
