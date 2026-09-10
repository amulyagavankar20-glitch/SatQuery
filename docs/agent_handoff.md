# SatQuery — agent handoff memory

## Mission

Build SatQuery (SIH26167): a local analyst tool that accepts one or two satellite GeoTIFFs plus an English question and returns a grounded answer, spatial evidence, and an auditable execution trace. Target imagery includes Cartosat, RISAT, and Sentinel.

## Architecture that must stay intact

- FastAPI backend; React 19/Vite/MapLibre operations console.
- `POST /ingest` → `POST /run` → poll `GET /jobs/{id}`. `JobView` is the single backend/frontend contract; see `docs/api-spec.md`.
- Raster pixels live on disk at `data/jobs/{job_id}/`; Postgres/PostGIS stores metadata, footprints, traces, tool runs, outputs, and vectors. Do not store rasters as database blobs.
- Active work uses an in-process `SessionContext`; finished work is persisted to Postgres.
- Qwen2.5 3B via Ollama is text-only router. It chooses a task but cannot invent or execute tools.
- LangGraph is a closed deterministic workflow, not an autonomous planner. No free tool use, second orchestrator, cloud VLM, Redis, Kafka, Celery, or WebSockets in the target MVP.
- Current talking VLM contract is `OpenGVLab/InternVL3-1B`; retain legacy `geochat_vqa` / `geochat_describe` tool IDs if needed for compatibility.

## Input classes and fixed paths

| Input/task | Required path |
|---|---|
| Single optical/SAR + VQA/caption | preprocess → `geochat_vqa` |
| Single optical/SAR + grounding | preprocess → `geochat_vqa` → grounding |
| Bi-temporal + change detection | preprocess → align → `bit_cd` → vectorize |
| Bi-temporal + change question | preprocess → align → `bit_cd` → vectorize → `geochat_describe` |
| Optical + SAR | preprocess → coregister → `fusion_s1s2` → agreement → `geochat_describe` |

Unsupported input/task combinations must refuse safely and expose the reason in `JobView`.

## What already works

- GeoTIFF ingestion, Rasterio metadata analysis, modality/input classification, pair overlap/date checks, job disk layout, and asset persistence.
- Optical, SAR, bitemporal, and optical-SAR preprocessing with normalized previews and 256px spatial tiles.
- Fixed LangGraph routing, Qwen schema client, selector/capability matrix, database models/migration, `JobView` assembly, GeoJSON/KML footprint exports.
- Polished web console: upload, question chips, polling, answer thread, MapLibre evidence view, traces, exports, local demo scenes/history.

## Current truth: not production-ready yet

- InternVL is configured but defaults to `mock`; BIT, grounding/SAM, fusion, agreement, and vectorization are mocks.
- GeoJSON exports currently provide footprints only; real change/grounding/uncertain/agreement layers are missing.
- PDF endpoint is deliberately HTTP 501.
- A fresh database lacks automatic `tool_registry` seeding, which blocks live tool selection.
- Legacy `/api/v1/*`, Redis/Celery/Qdrant code, startup rate limiting, and `docker-compose.yml` conflict with the newer no-Redis MVP. Compose also references missing Dockerfile/Nginx files.
- Frontend falls back to mock answers when backend calls fail; make this conspicuous or disable it for real analyst evaluation.
- Graph pair-fitness node currently records instead of independently enforcing the gate.

## Priority implementation order

1. Add reliable tool-catalog seeding during bootstrap/migration and prove a fresh DB can execute one job.
2. Remove or isolate the legacy Redis/Celery/Qdrant path; align startup, dependencies, and Compose with the documented architecture.
3. Load InternVL3-1B behind the existing tool contract; preserve `JobView` fields and trace behavior.
4. Replace mock BIT/SAM/fusion implementations and persist real masks/vectors as evidence layers.
5. Enforce invalid/unfit sessions at `/run` and in the graph; surface explicit refusal states.
6. Implement PDF report generation after real outputs exist.
7. Run/repair tests in the managed environment (`shapely` is currently missing) and add an end-to-end raster fixture test.

## Useful files

- `docs/api-spec.md` — canonical HTTP and `JobView` contract.
- `backend/api/jobs.py` — current analysis API.
- `backend/agents/graph.py` — closed execution graph.
- `backend/agents/tool_selector.py` — fixed paths/capabilities.
- `backend/services/ingest.py`, `backend/services/preprocessing/` — raster pipeline.
- `backend/services/persistence.py`, `backend/services/job_view.py` — durable state and UI view.
- `backend/services/tool_catalog.py` — required tool registry seed source.
- `web/src/state/console.tsx` — client ingest/run/poll/fallback flow.
- `docs/project_context.md` — full project review.
