# SatQuery AI — Complete System Architecture & Technical Design

**Project:** SIH26167 — SatQuery AI  
**Document type:** Master technical architecture  
**Status:** Implementation baseline — 2026-09-01 (rev. LangGraph + session store)  
**Sister file:** `project_context.md`. Product locks there and **§0–§1 of this file** override older candidate tables.

> The agent decides WHAT to run. Specialists analyse. GIS says WHERE.  
> An in-memory session holds the live run. Postgres remembers the finished one.  
> The UI shows the answer, the mark on the picture, and the receipt.

---

## 0. What changed in this revision

| Proposal | Verdict |
|---|---|
| LangGraph as a **constrained StateGraph** | **Keep.** Workflow runner, not a second brain. |
| Qwen2.5-7B router + Qwen3-30B-A3B heavy orchestrator | **Reject.** See §6. |
| In-memory `dict[session_id → SessionContext]` during the request; Postgres after | **Keep.** That diagram is the memory design. No Redis. |
| GeoChat + GeoGround + SkySense all loaded | **Reject as runtime set.** One talking VLM. |
| Redis / Kafka / Celery | Stay out. |

---

## 1. Locked runtime models

| Role | Model | Why |
|---|---|---|
| Router (text only) | **Qwen2.5-3B-Instruct**, JSON-schema constrained — or a classifier | Query + manifest → `{task, tools[], params}`. No pixels. |
| Talking VLM | **GeoChat-7B 4-bit + LoRA on BigEarthNet.txt** | VQA, caption, weak grounding, describe a change crop. |
| Grounding fallback | **MobileSAM** prompted by GeoChat’s phrase | Not a second 7B. |
| Change mask | **BIT** | Silent pixel map. Language from GeoChat on the crop. |
| Optical + SAR | **Small dual encoder + linear head** on BigEarthNet S1/S2 | Not SkySense. |
| Graph | **LangGraph StateGraph** with a frozen node list | Conditional edges only. No free tool invention. |

Do not load Qwen2.5-7B *and* Qwen3-30B-A3B *and* GeoChat-7B on one student GPU.

Appendix only: GeoGround (replacement VLM if we drop GeoChat), SkySense (citation, not a service).

---

## 2. Problem and inputs

ISRO / DoS software PS. Users: SAC analysts with Cartosat / RISAT / Sentinel files.

Configs: single optical or SAR; bi-temporal pair; co-registered optical + SAR.  
Formats: GeoTIFF / TIFF. PNG/JPEG only on public benches.  
Must: RS adaptation; VQA + (caption or grounding); change description/VQA; optical–SAR extraction; observable trace; GUI + report.  
Fail: generic cloud VLM, no adaptation.  
Eval: RSVQA, VRSBench, CDVQA + hidden Cartosat-2S + RISAT.

---

## 3. High-level pipeline

```
USER  query + GeoTIFF(s)
  → GATE          metadata, modality, pair-fitness
  → ROUTER        Qwen-3B JSON from query + manifest (no pixels)
  → LANGGRAPH     frozen nodes, conditional edges
       GeoChat │ BIT │ fusion head │ SAM │ vectorize
  → FUSION        text + overlays + agreement + uncertain
  → UI + EXPORT   PDF / GeoJSON / KML / mask GeoTIFF + trace

LIVE MEMORY (in FastAPI process)
  sessions[session_id] = SessionContext

AFTER THE RUN
  Postgres / PostGIS  ← traces, GeoJSON, logs
  disk                ← rasters, thumbs, masks, reports
```

Adaptation is train-time. Not a runtime branch.

---

## 4. Session store — the in-memory diagram already is the design

```
FASTAPI / PYTHON BACKEND PROCESS
  In-memory session store  dict
    key:   session_id  (UUID)
    value: SessionContext dataclass
  Working memory for the active run
    tool inputs, VLM outputs
    tools already attempted
    pair-fitness, artifacts in flight
                 │  request / graph ends
                 v
POSTGRES / POSTGIS
  completed traces, GeoJSON, job rows, logs
```

This does **not** already exist as code. It is the intended shape. Implement it once.

Rules:

- One analysis = one `session_id` = one LangGraph state. Do not keep a second “critic” object in MVP.
- `SessionContext` **is** `SatQueryState` (or a thin wrapper around it).
- Process restart loses in-flight runs. Acceptable for SIH. Finished jobs live in Postgres.
- No Redis. No LangGraph Postgres checkpointer in week 1. If BIT dies mid-run, mark the job `failed` and retry.
- Optional later: write checkpoints into the same `executions` table. Still not Redis.

```python
@dataclass
class SessionContext:
    session_id: str
    job_id: str
    query: str
    input_mode: str
    task: str
    metadata: dict
    pair_fitness: dict
    route: dict
    tool_results: list
    artifacts: list
    status: str
    errors: list
```

---

## 5. Gate / pair-fitness

Extract format, bands, modality, CRS, bounds, dates, nodata, overlap.

Refuse change / fusion when overlap, date gap, cloud fraction, or registration residual fails. Write the reason into the session and the trace.

Never pass a raw multi-GB GeoTIFF into GeoChat. Composite → RGB or SAR gray → optional windows.

---

## 6. Router LLM — verdict on the screenshot

| Role in screenshot | Model | Call |
|---|---|---|
| Fast intent / router | Qwen2.5-7B-Instruct | **Downsize to 3B.** Routing is classification + a tool list. |
| Heavy orchestrator | Qwen3-30B-A3B-Instruct-2507 | **Do not add.** LangGraph is the orchestrator. A 30B planner invents tools, fights the registry, and evicts GeoChat from VRAM. “Only 3B active experts” still costs RAM and another failure mode. |

Locked router: **Qwen2.5-3B-Instruct**, temperature 0, JSON schema only.

```json
{
  "task": "CHANGE_VQA",
  "input_mode": "BI_TEMPORAL_OPTICAL",
  "tools": ["geospatial_validator", "bit_cd", "vectorizer", "geochat_describe"],
  "need_overlay": true,
  "params": { "tile_size": 256 }
}
```

If 3B is still heavy, use a classifier. ISRO scores the observable plan, not planner size. Query rewriting is optional and must not change meaning.

---

## 7. LangGraph — keep it small

Allowed because branches are **known** (single / change / optical–SAR / refuse), not because we want an autonomous agent.

```
START
  input_validator
  metadata_parser
  pair_fitness_gate          → REFUSE if unfit
  query_router               → Qwen-3B JSON
  tool_selector              → registry lookup only
     ├ SINGLE_*    → preprocess → geochat_vqa → [optional sam]
     ├ CHANGE_*    → align → bit_cd → vectorize → geochat_describe
     └ OPTICAL_SAR → coregister → fusion_s1s2 → agreement
  evidence_fusion
  audit_logger
  report_generator
END
```

Node list is closed. Adding a node is a code change.

Do not add: critic, replanner, web_search, geoground-as-default, skysense.

State is execution state. No hidden chain-of-thought in state or UI.

---

## 8. Specialists

**GeoChat-7B** — required talking model. LLaVA-1.5, CLIP ViT-L/14 336, Vicuna 1.5. Apache-2.  
https://github.com/mbzuai-oryx/GeoChat · arXiv:2311.15826  
RGB composite in. temperature 0. LoRA on BigEarthNet.txt = mandatory adaptation. Ignore the 3×A100 paper recipe.

**BIT** — required change. https://github.com/justchenhao/BIT_CD · arXiv:2103.00208  
Pretrained checkpoint, modern PyTorch, 256 tiles. Ignore Python 3.6 pins.

**Fusion head** — required optical–SAR. Frozen S1+S2 encoders + small head. Train on BigEarthNet S1/S2. Water / built-up + agreement.

**MobileSAM** — optional grounding from GeoChat’s phrase.

**GeoGround** — appendix. Use *instead of* GeoChat, never beside it.  
**SkySense** — citation only.

ONNX Runtime later for BIT / fusion / SAM. GeoChat may stay quantized PyTorch.

---

## 9. Tool contract

Each tool: `validate → preprocess → infer → postprocess → explain_execution`.

```json
{
  "request_id": "REQ-001",
  "tool_id": "vqa_geochat",
  "model_version": "geochat-7b-qlora-ben-v1",
  "status": "success",
  "text": "...",
  "confidence": 0.81,
  "spatial_evidence": [],
  "artifacts": ["mask.png"],
  "metrics": { "latency_ms": 4200 }
}
```

---

## 10. Fusion, confidence, audit

Signals: pair-fitness, uncalibrated model score, spatial consistency, optical↔SAR agreement.  
MVP label: High / Medium / Low + the signals.

Map layers: optical, SAR, change, **uncertain**, **agreement**.

Audit JSON written to Postgres at END, REFUSE, or FAIL. That is the evaluator trace.

---

## 11. Data layer

Disk: `data/jobs/{id}/{raw,processed,tiles,masks,vectors,reports}`  
Postgres: jobs, assets, traces, outputs, tool_registry.  
PostGIS when needed: footprints, AOIs, change MULTIPOLYGONs.  
Rasterio = pixels. PostGIS = polygons. No GeoTIFFs in rows.  
MVP may emit GeoJSON files and add PostGIS when spatial SQL is actually queried.

---

## 12. API

FastAPI + Pydantic v2. No Redis queue.

```
POST /ingest          → job_id + manifest
POST /route           → router JSON (also runs inside /run)
POST /run             → 202 { job_id, session_id }
GET  /jobs/{id}       → status, answer, overlays, trace
GET  /jobs/{id}/report.pdf
GET  /jobs/{id}/export.geojson
GET  /jobs/{id}/export.kml
GET  /health
GET  /models
```

`POST /run` creates `SessionContext`, starts the graph via FastAPI BackgroundTasks, client polls `GET /jobs/{id}`.

---

## 13. Frontend

**Analyze** first: ingest | MapLibre evidence | query + trace + export. Official question chips. OFFLINE badge.  
**Explore** last: globe only to open packaged GeoTIFF cards. No WebGL screenshot as model input.

Stack: React 19, Vite, TS, Tailwind 4, shadcn, TanStack Router/Query/Form, Zod, MapLibre. No R3F on Analyze.

---

## 14. Infra

```
compose:  web | api (FastAPI + LangGraph + sessions + GPU tools) | postgres | ollama (3B only)
```

Weights on a volume. GeoChat + BIT + fusion loaded once at API start.

Out: Redis, Kafka, Celery, K8s, second Qwen, cloud VLM.

---

## 15. Workflows

VQA: gate → SINGLE_VQA → GeoChat on composite.  
Ground: GeoChat phrase → MobileSAM → CRS overlay.  
Change: pair-fitness → align/tile → BIT → vectorize → GeoChat on crop.  
Optical+SAR: coregister → fusion head → agreement → short GeoChat caption.  
Unfit pair: graph ends at REFUSE; UI shows why.

---

## 16. Datasets

Adapt: BigEarthNet.txt (txt.bigearth.net, arXiv:2603.29630).  
Public eval: RSVQA, VRSBench, CDVQA as prescribed.  
BIT warmup: LEVIR / WHU.  
Demo pack staged locally: water, coastal built-up, cloudy optical+SAR.

---

## 17. Team and GPU

2 UI · 1 API/rasters · 2 models · 1 glue.  
One 16–24 GB GPU. Resident: GeoChat-7B-4bit + BIT + tiny fusion + 3B router.  
A 30B orchestrator is how GeoChat gets offloaded and the hidden RISAT pair is never answered.

---

## 18. Decision table

| Component | Status |
|---|---|
| LangGraph constrained StateGraph | Required (workflow) |
| Qwen2.5-3B JSON router | Required (or classifier) |
| Qwen2.5-7B + Qwen3-30B-A3B | **Not used** |
| GeoChat-7B 4-bit + LoRA | Required |
| BIT | Required |
| S1/S2 fusion head | Required |
| GeoGround / SkySense | Appendix |
| In-memory SessionContext dict | Required for live run — implement, it is not code yet |
| Postgres persist at end | Required |
| Redis / LangGraph checkpointer | Not in MVP |
| React + MapLibre Analyze UI | Required |
| R3F globe as input | Forbidden |
