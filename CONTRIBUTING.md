# Contributing to SatQuery

Thanks for helping. SatQuery is a small SIH team with a **frozen architecture**.
Read this before you open a PR — most rejected patches violate a lock, not a
style rule.

Please also follow the [Code of Conduct](./CODE_OF_CONDUCT.md).

## Architecture locks (do not "improve" these in a drive-by PR)

| Lock | Meaning |
|---|---|
| Router | `qwen2.5:3b-instruct` via Ollama. Text + manifest → JSON. **No pixels.** |
| Talking VLM | `OpenGVLab/InternVL3-1B`. Graph tool IDs stay `geochat_vqa` / `geochat_describe`. |
| Graph | Frozen LangGraph `StateGraph`. Conditional edges only. No free tool invention. |
| Contract | One document: **JobView**. UI and API share [docs/api-spec.md](./docs/api-spec.md). |
| Transport | Client **polls** `GET /jobs/{id}`. No Redis, Kafka, Celery, or WebSocket for MVP. |
| Memory | In-process `SessionContext`. Postgres after the run. Rasters on disk, never as BLOBs. |
| UI | Analyze is an **ops console**. Do not turn it into a 3D marketing globe. |

> [!IMPORTANT]
> If your change needs a lock lifted, open an **architecture** issue first and
> wait. Do not send a PR that adds Redis "just for now".

Master doc: [docs/SatQuery_AI_System_Architecture.md](./docs/SatQuery_AI_System_Architecture.md).

## What we want

- JobView completeness (no disk paths, overlays, traces, confidence)
- Real InternVL / BIT / SAM / fusion specialists behind the existing tool IDs
- Tests for router JSON, graph paths, and JobView
- Analyze console density: keyboard, legend, empty/error states
- Docs that match running code

## What we do not want

- Extra orchestrator models (Qwen-7B, Qwen3-30B, a second VLM at runtime)
- Generic cloud VLM calls for the talking path
- Auth, multi-tenancy, or billing before the specialists work
- Committing `.env`, `data/jobs/**`, or operational satellite scenes
- Rewriting the frontend in Next.js / R3F without an architecture issue

## Development setup

Follow the [README quick start](./README.md#quick-start). Short version:

```bash
# Python 3.12 — OneDrive/Windows: copy mode avoids hardlink failures
uv venv --python 3.12 --link-mode=copy
# Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

cp .env.example .env   # set POSTGRES_PASSWORD
alembic upgrade head

# Rasterio must use its own PROJ, not PostGIS proj.db (Windows)
$proj = (Resolve-Path .venv\Lib\site-packages\rasterio\proj_data).Path
$env:PROJ_LIB = $proj; $env:PROJ_DATA = $proj
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```bash
cd web
npm install
npx vite --host 127.0.0.1 --port 5173
```

Ollama must serve `qwen2.5:3b-instruct` for live routing. Tests that need the
graph without Ollama inject `injected_task` — do not teach production code that
trick.

> [!CAUTION]
> PowerShell `curl` is `Invoke-WebRequest`. Use `curl.exe` for multipart
> GeoTIFF uploads.

## Repository map

| Path | Own this if you are changing… |
|---|---|
| `backend/agents/` | Router, frozen graph, tool selector |
| `backend/services/` | Ingest, JobView, preprocessing, persistence |
| `backend/api/` | HTTP surface |
| `web/src/` | Analyze console |
| `docs/api-spec.md` | JobView fields — **update this in the same PR** as schema changes |
| `migrations/` | Alembic only; do not hand-edit production DBs |
| `tests/` | pytest |

## Coding rules

**Python**

- 3.12, `X | None`, `list` / `dict` builtins. Keep `typing.Any` where the graph
  is genuinely untyped.
- Do not add `Optional` / `List` / `Dict` from `typing` (Ruff UP045 / UP035).
- Graph nodes return **partial state updates**. Do not mutate `GraphState` in
  place and hope.
- Failed / refused runs must never be marked `completed`.
- Confidence comes from evidence signals, not a made-up float.

**JobView / API**

- Zod schema in `web/src/lib/schema.ts` must match `docs/api-spec.md`.
- Extra JSON keys are fine (UI ignores them). Missing required keys are a bug.
- Artifact URLs are relative (`/jobs/{id}/artifacts/composite`), never
  `file://` or `C:\Users\...`.

**Frontend**

- React 19, Vite, Tailwind 4, TanStack Query/Router, Zod, MapLibre.
- Poll 2–3 s while `running`; stop on `completed` | `failed` | `refused`.
- Do not call `/run` when ingest `valid` is false.

**Git**

- Small PRs. One concern each.
- Do not commit `__pycache__/`, `.venv/`, `web/node_modules/`, `web/dist/`,
  logs, or job rasters. They are gitignored for a reason.
- Never force-push `main`.

## Tests

```bash
pytest tests/ -q
cd web && npx tsc -b --pretty false
```

Add or extend tests when you touch:

- Router JSON (`tests/test_router.py`)
- Graph edges (`tests/test_graph_paths.py`)
- JobView assembly (`tests/test_job_view.py`)

A PR that changes JobView without a test and an api-spec update will be asked
to fix that first.

## Pull request process

1. Branch from `main`: `feat/…`, `fix/…`, or `docs/…`.
2. Keep the architecture locks unless an issue already approved the change.
3. Fill in the PR template checklist.
4. Link the issue. Screenshots for UI; `GET /jobs/{id}` JSON for API.
5. Wait for review from a maintainer.

## Commit messages

Imperative, scoped, no trailer noise:

```
feat: persist JobView overlays from PostGIS footprints
fix: refuse empty queries in input_validator
docs: document InternVL talking VLM in api-spec
```

## License

Contributions are accepted under the [MIT License](./LICENSE). By opening a PR
you agree they may be redistributed under that license. Model weights you
download yourself stay under their own terms — see [NOTICE](./NOTICE).
