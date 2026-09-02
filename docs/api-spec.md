# SatQuery AI — Analyze API Spec

**Project:** SIH26167 — SatQuery AI  
**Audience:** FastAPI backend and the Analyze UI (React 19 / Vite / TanStack Query / Zod / MapLibre)  
**Status:** Contract for frontend MVP — 2026-09-02  
**Talking VLM (locked):** `OpenGVLab/InternVL3-1B` (replaces GeoChat-7B at the tool implementation; graph tool IDs stay `geochat_vqa` / `geochat_describe`)  
**Router:** `qwen2.5:3b-instruct` via Ollama (text only, no pixels)

The UI and the agent share one document: **`JobView`**.  
Qwen fills `route`. InternVL (or the current mock) fills `answer`. GIS fills `overlays`. The graph never invents fields.

No Redis. No WebSocket. Client polls `GET /jobs/{id}`.

Base URL (dev): `http://127.0.0.1:8000`

---

## 1. Status machine

| Status | Meaning |
|---|---|
| `ingested` | Rasters saved, classified, not run |
| `running` | LangGraph in flight |
| `completed` | Report produced (answer may still be mock text) |
| `failed` | Tool or infrastructure error |
| `refused` | Gate / router / empty query refused; `refusal_reason` set |

Poll every 2–3 s while `running`. Stop on `completed` | `failed` | `refused`.

---

## 2. Endpoints

### `GET /health`

```json
{
  "status": "ok",
  "router_model": "qwen2.5:3b-instruct",
  "talking_vlm": "OpenGVLab/InternVL3-1B",
  "ollama": "ok",
  "postgres": { "status": "connected" }
}
```

UI OFFLINE badge: `ollama != "ok"` or `postgres.status != "connected"`.

### `GET /models`

```json
{
  "router_model": "qwen2.5:3b-instruct",
  "router_ready": true,
  "talking_vlm": "OpenGVLab/InternVL3-1B",
  "talking_vlm_backend": "mock",
  "available": ["qwen2.5:3b-instruct"]
}
```

`talking_vlm_backend` is `mock` until InternVL is loaded, then `internvl`.

### `POST /ingest` `multipart/form-data`

| Field | Type | Required |
|---|---|---|
| `files` | one or more `.tif` / `.tiff` | yes |
| `sensor` | string (e.g. `Cartosat-2S`, `RISAT`) | no |
| `query` | string | no |

**200**

```json
{
  "job_id": "uuid",
  "session_id": "uuid",
  "status": "ingested",
  "input_class": "SINGLE_OPTICAL",
  "valid": true,
  "validation_messages": ["Classified as SINGLE_OPTICAL: Exactly one optical raster."],
  "refusal_reason": null,
  "assets": [
    {
      "filename": "scene.tif",
      "modality": "OPTICAL",
      "sensor": "Cartosat-2S",
      "width": 512,
      "height": 512,
      "crs": "EPSG:4326",
      "bounds_wgs84": [72.5, 23.0, 72.7, 23.2]
    }
  ]
}
```

`input_class`: `SINGLE_OPTICAL` | `SINGLE_SAR` | `BI_TEMPORAL` | `OPTICAL_SAR`.  
**400** on bad extension or unreadable raster. If `valid` is false, still returns `job_id`; UI shows `refusal_reason` and must not call `/run`.

### `POST /run` `application/json`

```json
{ "job_id": "uuid", "query": "What land-cover classes are visible?" }
```

`input_mode` is optional when `job_id` refers to an ingested job.

**202**

```json
{ "job_id": "uuid", "session_id": "uuid", "status": "running" }
```

**404** if `job_id` is unknown (process restart loses in-memory ingest; re-ingest).  
**400** if `job_id` omitted and `input_mode` missing.

### `POST /route` `application/json`

Planner only. UI does not need this for Analyze MVP (`/run` already routes).

```json
{ "query": "...", "manifest": { "input_class": "SINGLE_OPTICAL", "modality": "OPTICAL" } }
```

**200** `RouteResponse`: `{ task, input_mode, tools, need_overlay, params }`.

### `GET /jobs/{id}`

Always **`JobView`** (section 3). Same shape from live session or Postgres after persist.

### `GET /jobs/{id}/artifacts/composite`

Processed RGB (or SAR gray) preview. **200** `image/png` or `image/tiff`. **404** if not preprocessed yet.

### `GET /jobs/{id}/artifacts/tiles/{index}`

Zero-based 256 tile PNG. **200** `image/png`. **404** if missing.

### `GET /jobs/{id}/export.geojson`

FeatureCollection of footprints (and later CHANGE / GROUNDING). CRS EPSG:4326. **200** `application/geo+json`.

### `GET /jobs/{id}/export.kml`

Same features as KML. **200** `application/vnd.google-earth.kml+xml`.

### `GET /jobs/{id}/report.pdf`

**501** until report generation exists.

---

## 3. JobView (canonical)

The Analyze UI Zod schema must match this object. Extra keys are ignored; missing required keys are a backend bug.

```json
{
  "job_id": "uuid",
  "session_id": "uuid",
  "status": "completed",
  "query": "What land-cover classes are visible?",
  "input_class": "SINGLE_OPTICAL",
  "task": "CAPTIONING",
  "route": {
    "task": "CAPTIONING",
    "input_mode": "SINGLE_OPTICAL",
    "tools": ["geochat_describe"],
    "need_overlay": false,
    "params": {}
  },
  "answer": {
    "text": "…",
    "model": "OpenGVLab/InternVL3-1B",
    "backend": "mock",
    "confidence": "MEDIUM"
  },
  "assets": [
    {
      "filename": "scene.tif",
      "modality": "OPTICAL",
      "sensor": "Cartosat-2S",
      "bounds_wgs84": [min_lon, min_lat, max_lon, max_lat],
      "preview_url": "/jobs/{id}/artifacts/composite"
    }
  ],
  "overlays": [
    {
      "type": "FOOTPRINT",
      "geojson_url": "/jobs/{id}/export.geojson",
      "confidence": null
    }
  ],
  "traces": [
    {
      "event_type": "QUERY_ROUTED",
      "node_name": "query_router",
      "tool_id": null,
      "message": null,
      "timestamp": "2026-09-02T17:36:06.173582+00:00"
    }
  ],
  "warnings": [],
  "errors": [],
  "refusal_reason": null,
  "tile_count": 4
}
```

| Field | Source |
|---|---|
| `route` | Qwen JSON (`RouteResponse`) |
| `answer.text` | InternVL / mock specialist `ToolResult` |
| `answer.backend` | `mock` or `internvl` |
| `assets[].bounds_wgs84` | Rasterio header → PostGIS footprint |
| `overlays` | Footprint now; CHANGE / GROUNDING / UNCERTAIN when BIT/SAM exist |
| `traces` | LangGraph node events |

`task` values: `SINGLE_VQA` | `CAPTIONING` | `GROUNDING` | `CHANGE_DETECTION` | `CHANGE_VQA` | `OPTICAL_SAR_ANALYSIS` | `UNROUTED`.

`overlay.type`: `FOOTPRINT` | `CHANGE` | `GROUNDING` | `UNCERTAIN` | `AGREEMENT`.

Never return local filesystem paths (`C:\…`) in JobView. Only relative API URLs.

---

## 4. Official question chips (UI constants)

Not an API. Hard-code in the Analyze query box:

| Chip | Query | Typical task |
|---|---|---|
| VQA | What land-cover classes are visible? | `SINGLE_VQA` / `CAPTIONING` |
| Caption | Describe this satellite scene. | `CAPTIONING` |
| Ground | Where are the built-up areas? | `GROUNDING` |
| Change | What changed between these two dates? | `CHANGE_VQA` |
| Optical+SAR | Fuse optical and SAR over this AOI. | `OPTICAL_SAR_ANALYSIS` |

---

## 5. Frontend mapping

Stack: React 19, Vite, TS, Tailwind 4, shadcn, TanStack Router/Query/Form, Zod, MapLibre. No R3F on Analyze.

1. Upload → `POST /ingest` → draw `assets[].bounds_wgs84` on MapLibre.  
2. Query + chip → `POST /run`.  
3. Poll `GET /jobs/{id}` until terminal status.  
4. Show `answer.text`, trace list, `preview_url` image, overlay GeoJSON.  
5. Export buttons hit `/export.geojson` and `/export.kml`.  
6. OFFLINE from `/health`.

---

## 6. Out of contract (do not add)

Redis, Kafka, Celery, second Qwen, cloud VLM, WebGL screenshot as model input, free tool invention, GeoTIFF blobs in JSON.

---

## 7. Current vs next

| Item | Now | Next |
|---|---|---|
| Talking VLM | `answer.backend = mock` | InternVL3-1B, same JobView |
| Change overlays | Footprint only | BIT polygons |
| PDF | 501 | Report generator |
| CORS | Vite `localhost:5173` | Production origin via env |
