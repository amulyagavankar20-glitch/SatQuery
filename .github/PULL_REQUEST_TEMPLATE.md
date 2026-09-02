## Summary

<!-- What does this PR change, and why? -->

## Type

- [ ] Backend (API / graph / ingest / JobView)
- [ ] Analyze UI
- [ ] Docs / community
- [ ] Tests only
- [ ] Chore

## Architecture

I have read `docs/SatQuery_AI_System_Architecture.md` and `docs/api-spec.md`.

- [ ] This PR does **not** add Redis, Kafka, Celery, WebSockets, or a second orchestrator model
- [ ] Graph tool IDs still include `geochat_vqa` / `geochat_describe` if I touched specialists
- [ ] JobView still returns API URLs, never local filesystem paths
- [ ] If I changed JobView fields, I updated `docs/api-spec.md` **and** `web/src/lib/schema.ts` in this PR
- [ ] If I need a lock lifted, an architecture issue is linked: #

## Test plan

- [ ] `pytest tests/ -q`
- [ ] `cd web && npx tsc -b` (UI PRs)
- [ ] Manual: ingest `data/fixtures/cartosat2s_demo.tif` → `/run` → poll `GET /jobs/{id}` (if runtime path)

## Notes

<!-- Screenshots, JobView JSON, follow-ups. -->
