# Security Policy

SatQuery ingests GeoTIFFs, runs a local LLM router, and writes rasters to disk.
Treat a running instance as a **trusted-operator console**, not a public SaaS.

## Supported versions

This repository is under active SIH development on `main`. Only `main` receives
security fixes.

| Version | Supported |
|---|---|
| `main` | Yes |
| Older commits / forks | No |

## Report a vulnerability

**Do not open a public issue** for a security report.

Use a [private GitHub security advisory](https://github.com/amulyagavankar20-glitch/SatQuery/security/advisories/new). Do not email personal addresses or open a public issue.

Include:

- Affected path or endpoint (`POST /ingest`, `GET /jobs/{id}/artifacts/...`, etc.)
- Steps to reproduce, or a minimal proof of concept
- Impact (data leak, path traversal, SSRF, auth bypass, model-prompt injection)
- Whether you have already tested it against a local instance only

You should hear back within **7 days**. We will confirm, fix on `main` when
warranted, and credit you if you want to be named.

## In scope

- Path traversal or local-file disclosure via artifact / export URLs
- Unauthenticated write or delete of another operator's jobs (when auth exists)
- SQL injection against PostGIS / SQLAlchemy
- Secret leakage: `.env`, `POSTGRES_PASSWORD`, API keys in logs or JobView
- CORS widening that exposes the API beyond the Analyze origin list
- Prompt injection that causes the router to emit tools outside the frozen catalog
- SSRF from raster / URL fetch paths, if any are added

## Out of scope

- Denial of service by uploading huge GeoTIFFs to a local dev server
- Issues that require a stolen `.env` or OS admin on the same machine
- Model quality, hallucinated captions, or mock specialist answers
- Vulnerabilities only in upstream Ollama, Qwen, InternVL, or PostgreSQL
  (report those upstream)
- "Please add authentication" as a vulnerability report — see below

## Hard rules for this codebase

> [!IMPORTANT]
> JobView must never return local filesystem paths (`C:\…`, `/home/…`).
> Artifacts are API URLs only. `.env` is gitignored — never commit it,
> never paste it into issues, never log `POSTGRES_PASSWORD`.

Current posture (honest, not aspirational):

- Dev API binds to `127.0.0.1` and trusts the CORS origin list
- There is **no operator auth** on `/ingest`, `/run`, or `/jobs/{id}` yet
- In-memory sessions die on process restart; finished jobs live in Postgres
- Talking VLM may be `mock` — do not treat answers as classified intelligence

If you deploy beyond localhost, put the API behind a reverse proxy, restrict
CORS, and add auth **before** exposing port 8000.

## Secrets and rasters

| Never commit | Why |
|---|---|
| `.env` | Database password and runtime config |
| `data/jobs/**` | Operator rasters, tiles, masks |
| Operational Cartosat / RISAT scenes | Agency data, not this repo's to publish |
| Ollama / Hugging Face tokens | If you add them later |

The demo fixture `data/fixtures/cartosat2s_demo.tif` is the only raster
intended for the tree (and may still be gitignored by `*.tif` — keep it local
unless maintainers explicitly track it).

See [NOTICE](./NOTICE) for model licenses and the SIH / ISRO disclaimer.
