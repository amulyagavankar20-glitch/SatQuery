# SatQuery docs

Technical design and community files for **SIH26167 — SatQuery AI**.

The agent decides WHAT to run. Specialists analyse. GIS says WHERE.

## Technical

| Document | Freezes |
|---|---|
| [System architecture](./SatQuery_AI_System_Architecture.md) | Models, frozen LangGraph, session store, product locks |
| [Analyze API spec](./api-spec.md) | JobView, HTTP surface, question chips, InternVL id |
| [Database architecture](./database_architecture.md) | PostGIS ER, disk layout, no rasters in BLOBs |
| [Input classification](./input_classification_and_preprocessing.md) | Gate, modalities, pair-fitness |

## Community (repo root)

| File | Purpose |
|---|---|
| [README](../README.md) | Hero, quick start, pipeline |
| [CONTRIBUTING](../CONTRIBUTING.md) | How to change the code without breaking locks |
| [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md) | Contributor Covenant 2.1 |
| [SECURITY](../SECURITY.md) | Private vulnerability reports |
| [SUPPORT](../SUPPORT.md) | Where to ask, what not to file |
| [LICENSE](../LICENSE) | MIT |
| [NOTICE](../NOTICE) | Model licenses + SIH / ISRO disclaimer |

## Issue templates

New issues: [choose a template](https://github.com/amulyagavankar20-glitch/SatQuery/issues/new/choose).

- **Bug** — API, graph, Analyze
- **Feature** — fits the frozen graph
- **Architecture lock** — discuss before lifting a lock
- **Question** — running / JobView
