# Grok Build prompt — SatQuery AI console (frontend)

Copy everything under the line into Grok Build. Do not add login, a 3D globe as the product, cyan HUD chrome, or a pipeline stepper in the header.

---

You are a principal product designer and frontend engineer. Build a **production-grade web console** for **SatQuery AI** (SIH26167, ISRO). This is an operator tool for asking natural-language questions about GeoTIFF satellite scenes (optical, SAR, bi-temporal pairs). It must look like a calm analysis instrument — **not** a generated “space startup,” not ChatGPT with a navy skin, not a cramped three-column cockpit.

Reference of what to **beat and not copy**: https://satqueryaiisro.vercel.app  
That site’s only good idea is vertical breathing room. Reject its cyan-on-grid HUD, “EXECUTE MISSION”, “NO SENSORY DATA MOUNTED”, fake VRAM/latency telemetry, Orbitron energy, and empty frozen columns.

## Product facts (do not invent otherwise)

- Users: ISRO/SAC analysts. No accounts. **No login page.**
- Default route is the **console**. Optional `/about` for judges. Jobs live in a **drawer**, not a primary tab.
- One analysis is a **thread**: attach 1–2 GeoTIFFs, type a question, get text + map evidence + an auditable trace.
- Backend contract (mock it if no API):  
  `POST /ingest` → manifest  
  `POST /run` → `{ job_id, session_id }`  
  `GET /jobs/{id}` → `{ status, answer, overlays, trace, confidence }`  
  exports: `report.pdf`, `export.geojson`, `export.kml`
- Official query chips:  
  Describe land-cover and major objects · Highlight the water body · What changed between these two dates, and where? · Use optical and SAR together for built-up and water · Has built-up increased, decreased, or stayed the same?
- Models are not the UI’s problem. Never show “GeoChat / BIT / SkySense” as marketing. The **trace accordion** may list tool ids after a run: `gate → router → bit_cd → geochat_describe`.

## Information architecture

```
/            Console (thread + scene rail + sticky composer)
/about       One screen: one-line pitch, one architecture figure, eval note. Not the home page.
Jobs drawer  Last runs, reload a thread. Not a top-level “History” HUD.
Explore      NOT in v1. Replace with three “Load demo scene” actions in the empty state.
```

**Do not build:** login, signup, settings, billing, Cesium/R3F globe, Next.js marketing landing, pipeline chips `INGEST → ROUTE → RUN` in the header, a critic loop UI.

## Layout — thread, not cockpit

```
┌─────────────────────────────────────────────────────────────┐
│  wordmark SatQuery     About     Jobs              ● local  │
├─────────────┬───────────────────────────────────────────────┤
│ SCENE RAIL  │  THREAD (this column is the scroll root)      │
│ 240–280px   │                                               │
│ T1 file     │  empty state  OR  turns stacked top→bottom    │
│ T2 / SAR    │                                               │
│ CRS, date   │  user bubble (query)                          │
│ pair-fitness│  assistant block:                             │
│ layer list  │    answer paragraph                           │
│             │    map evidence (~440px)                      │
│             │    ▸ Trace (collapsed)                        │
│             │    PDF · GeoJSON · KML                        │
├─────────────┴───────────────────────────────────────────────┤
│ chips: official questions                                   │
│ [ + attach ]  Ask this scene…                        Send   │
└─────────────────────────────────────────────────────────────┘
```

- Header ~48px, no fake telemetry.
- Scene rail **fixed**. Thread **scrolls**. Composer **sticky**.
- Map lives **inside the assistant turn**, full thread width — not a permanent center pane that is empty on first load.
- Attach files by dropping on the thread, the rail, or the paperclip. Manifest chips (filename, CRS, date, bands, pair-fitness) belong under the file in the rail.
- Follow-up questions append to the same thread so the page grows. Do not reset the viewport.

## Empty state (first paint)

Quiet. No grid overlay. No all-caps void message.

- One sentence: “Attach a GeoTIFF — or load a demo scene.”
- Three demo cards: Water / Coastal built-up / Cloudy optical+SAR. Clicking one fills the rail and enables the composer.
- Large drop target.

## Visual language — anti-slop rules

**Allowed**
- Warm-black ground `#121417`
- Surfaces `#1A1E22` and `#22282E`
- Hairline `#2C343C`
- Text `#E8E4DC` / mute `#8B959E`
- **One accent only:** desaturated teal `#5E8F8A` (links, focus, selected chip). If teal fights the imagery, swap accent to copper `#B8893A` globally — still only one accent.
- Type: Geist, IBM Plex Sans, or Source Sans 3 for UI. IBM Plex Mono or Geist Mono **only** for traces and CRS.
- Radius 8–12px. Spacing scale 8/12/16/24/40. Real contrast.

**Forbidden**
- Cyan `#00E5FF` / electric teal on navy grid
- Orbitron, Audiowide, “MISSION”, “EXECUTE”, “SENSORY DATA”
- Gradient wordmarks, glow borders, glassmorphism stacks
- Fake stats: latency 12ms, VRAM allocated, SYSTEM ONLINE as decoration
- Emoji as navigation
- Three equal columns that never scroll
- 3D Earth on first paint

This must survive a projector in a bright hall. If a control is only visible because it is neon, it is wrong.

## Components to implement

1. **AppShell** — header, rail, thread, composer.
2. **SceneRail** — T1, T2/SAR slots, remove, pair-fitness bar (0–1, quiet), layer checkboxes (optical, SAR, change, uncertain) that control the latest map in the thread.
3. **Thread** — user turns, assistant turns, empty state.
4. **AssistantTurn** — prose, MapEvidence, TraceAccordion (closed by default), export row.
5. **MapEvidence** — MapLibre GL, PNG preview + GeoJSON overlay. Layer toggles on the map. No Cesium. Placeholder raster is fine if no tiles yet.
6. **Composer** — textarea, attach, send, official chips above it. Disable send when no scene and no demo loaded.
7. **JobsDrawer** — list of past job ids, click to restore dummy thread.
8. **About** — pitch: *Satellites write measurement grids. People ask. A router picks a specialist. The specialist answers in words and in pixels.* One simple diagram (CSS/SVG, not a 3D render). Link back to console.

Use React 19 + Vite + TypeScript + Tailwind v4 + shadcn/ui + TanStack Router + TanStack Query + Zod. MapLibre GL for the map. No Next.js. No Three / R3F in this build.

## Interaction details

- Official chips insert text into the composer; they do not auto-send.
- After Send: optimistic user bubble; assistant shows a short pending state (“Reading the pair…”) then a mock answer + map + trace so the UI is demoable offline.
- Mock run: pair-fitness 0.91, confidence Medium, trace `gate → router → bit_cd → geochat_describe`, 2–3 change polygons on the map.
- Trace accordion: tool name, elapsed ms (only if real; omit if mocked as unknown), params as monospace JSON. No chain-of-thought essay.
- Keyboard: `/` focuses composer, `Esc` closes drawer.
- Responsive: below 1024px, scene rail becomes a top sheet; thread still scrolls.

## Quality bar

Ship a complete Vite app that runs with `pnpm i && pnpm dev`. Pixel-tight spacing, no lorem, no leftover “TODO HUD”. README: one paragraph + how to run. Favicon: simple “S” mark in the accent colour on warm-black — not a neon globe.

When in doubt: fewer labels, more whitespace, one accent, the map only appears after someone asked a question.
