# SatQuery project context

**Last reviewed:** 2026-09-06  
**Project:** SIH26167 — a local, analyst-facing satellite-image question-answering system for Cartosat, RISAT, and Sentinel rasters.

## Product in one paragraph

SatQuery accepts one or two GeoTIFFs and a natural-language question, classifies the input configuration, routes the request with a constrained Qwen 2.5 3B planner, follows a fixed LangGraph path, and returns a single `JobView` for the React operations console. The intended outcome is a grounded textual answer, map evidence, and an auditable execution trace—not a generic image caption. Raster binaries remain on disk; PostgreSQL/PostGIS stores job metadata, footprints, traces, tool runs, and outputs.

## What has been developed

### Working application structure

- **FastAPI API:** health/model status plus the current analysis contract: `/ingest`, `/route`, `/run`, `/jobs/{id}`, artifact preview/tile endpoints, and GeoJSON/KML export.
- **Ingest and gate:** uploaded TIFF/GeoTIFF files are written to `data/jobs/{job_id}/raw`; Rasterio metadata is inspected; inputs are classified as `SINGLE_OPTICAL`, `SINGLE_SAR`, `BI_TEMPORAL`, or `OPTICAL_SAR`; two-image inputs are checked for overlap and, for bitemporal work, distinct acquisition dates.
- **Preprocessing:** implemented optical, SAR, bi-temporal, and optical–SAR preprocessors create normalized previews, GeoTIFFs, 256-pixel tiles, and spatial tile references. The disk layout is standardized as `raw/`, `processed/`, `tiles/`, `masks/`, `vectors/`, and `reports/`.
- **Orchestration:** a compiled, closed LangGraph has validation, routing, deterministic tool selection, preprocessing, specialist branches, evidence fusion, audit, report shaping, and refusal paths. The router uses Ollama/Qwen structured JSON; the selector validates fixed task-to-tool paths against a capability matrix and the PostgreSQL `tool_registry`.
- **Persistence:** SQLAlchemy models and one Alembic migration define projects, jobs, assets, tool registry/runs, outputs, traces, and PostGIS spatial features. A live in-memory `SessionContext` holds active runs; `persist_run` writes completion data to Postgres.
- **Web console:** React 19/Vite/Tailwind/MapLibre UI with an analysis thread, file attachment, official query chips, local job history, trace display, evidence-map controls, exports, keyboard shortcuts, an Explore page with bundled demos, and an About page. It speaks the documented `JobView` schema through Zod validation.
- **Automated coverage:** tests target graph-path invariants, routing hardening, tool selection/execution, and JobView behavior. They currently cannot be collected in this checkout because the active Python environment lacks `shapely`.

### Present specialist status

The pipeline interfaces are present, but specialist inference is not production-ready:

- The Qwen router is a real Ollama client when Ollama is available.
- The talking VLM is configured/documented as `OpenGVLab/InternVL3-1B`, but `TALKING_VLM_BACKEND` defaults to `mock`.
- BIT change detection, MobileSAM grounding, optical–SAR fusion, agreement, and vectorization currently use mock tool implementations.
- Current map exports contain input footprints. Change, grounding, uncertain, and agreement geometries remain future work.
- PDF report export intentionally returns HTTP 501.

## Intended execution flow

```text
GeoTIFF(s) + question
  → ingest, inspect metadata, classify input, create session/job
  → Qwen JSON intent router (text + manifest only)
  → deterministic tool path
  → preprocessing + specialist result(s)
  → evidence/trace/report object
  → Postgres/PostGIS + JobView polling in the web console
```

Fixed specialist paths are:

| Task | Path after routing |
|---|---|
| Single VQA / caption | preprocess → `geochat_vqa` |
| Grounding | preprocess → `geochat_vqa` → grounding |
| Change detection | preprocess → align → BIT → vectorize |
| Change VQA | preprocess → align → BIT → vectorize → describe |
| Optical + SAR | preprocess → coregister → fusion → agreement → describe |

## What we are developing next

1. Replace mock specialist tools with the locked local implementations, starting with InternVL3-1B while preserving the `JobView` contract.
2. Implement real BIT masks, polygonization, grounding, and optical/SAR evidence so the map has meaningful non-footprint layers.
3. Complete report generation and make `/report.pdf` available.
4. Make the run path deployable: seed the tool registry, align infrastructure with the no-Redis/Celery architecture, and add a repeatable local/Compose setup.
5. Strengthen execution failure handling, pair-fitness enforcement, and end-to-end test coverage against actual raster fixtures.

## Important implementation realities and risks

- **Registry bootstrapping blocks real runs.** `ToolSelector` validates every path against `tool_registry`, but the migration creates an empty table and no startup/CLI flow calls `seed_tool_registry`. A fresh database will therefore refuse valid runs until it is seeded.
- **Two incompatible backend generations coexist.** The current `/ingest` → `/run` → polling design is in `backend/api/jobs.py`; legacy authenticated `/api/v1/query` and `/api/v1/assets` routes use Celery, Redis, WebSockets, and mock task workers. The architecture and API documents explicitly exclude Redis, Celery, and WebSockets from the MVP.
- **Startup and Compose still depend on legacy infrastructure.** `backend/main.py` initializes `FastAPILimiter` with Redis, and `docker-compose.yml` includes Redis, Qdrant, Celery, Nginx, and API services. It also references a Dockerfile and Nginx configuration that are not present in the repository. This conflicts with the documented target Compose topology.
- **The front end can mask backend failure.** If live ingest/run/polling fails or times out, the console deliberately displays a local mock answer. This is useful for demos but must be visibly labelled or disabled for analyst-facing validation.
- **Upload rules differ across layers.** The web UI accepts PNG/JPEG for demos/drop actions, while the primary backend ingest accepts only `.tif`/`.tiff`.
- **Model naming is inconsistent.** Newer README/API documentation locks InternVL3-1B with legacy `geochat_*` tool IDs; older architecture and tool catalog text still describe GeoChat-7B. The runtime contract should standardize on InternVL while retaining IDs only where backward compatibility requires it.
- **Pair-fitness graph gate is currently observational.** Pair checks happen during ingest, but the LangGraph `pair_fitness_gate` currently records a trace without independently refusing unfit input. `/run` also does not reject an ingested session already marked `refused`.
- **Tests need the intended environment.** `pytest tests -q --maxfail=1` stops during collection with `ModuleNotFoundError: shapely`; the workspace has no `web/node_modules`, so the web build was not run.

## Source of truth and repository map

Use `docs/api-spec.md` as the frontend/backend contract and `docs/SatQuery_AI_System_Architecture.md` for the architecture locks. The root README is the practical setup and capability overview, but its model/tool prose must be reconciled with the API specification.

```text
backend/        FastAPI, sessions, ingest, persistence, LangGraph, specialists
backend/api/    Current jobs API and older v1 auth/query/assets prototype
backend/services/  input analysis, preprocessing, persistence, JobView assembly
backend/agents/ Closed graph, Qwen router, tool selector, tool executor/mocks
web/            React analysis console and Explore/About surfaces
migrations/     Alembic/PostGIS initial schema
tests/          graph, router, selector, executor, and JobView tests
docs/           architecture, API, database, preprocessing, this context brief
```

## Definition of the current milestone

The project is an **implemented MVP shell with live ingest, preprocessing, deterministic routing/orchestration, persistence schema, and polished console**, but it is **not yet a fully operational satellite-analysis service**. The primary remaining work is replacing specialist mocks and resolving the infrastructure/bootstrapping inconsistencies so an uploaded raster can reliably produce real model-backed spatial evidence end to end.
