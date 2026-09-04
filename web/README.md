# SatQuery console

Operator console for SatQuery AI (SIH26167). Attach one or two GeoTIFFs, ask a question in English, and read the answer as prose plus map evidence with an auditable trace. Works offline with three demo scenes; talks to the FastAPI backend when `POST /ingest` and `GET /jobs/{id}` are reachable.

Palette: ground `#121417`, surface `#1A1E22`, raised `#22282E`, hairline `#2C343C`, ink `#E8E4DC`, mute `#8B959E`, accent `#5E8F8A`.

```bash
pnpm i && pnpm dev
```

Open http://localhost:5173. Optional: set `VITE_API_BASE` (default `http://127.0.0.1:8000`).

**Explore** (`/explore`) is a 2D map of packaged scenes. Click a scene and send it to the console, or drop a GeoTIFF / PNG onto the map.

**Keys.** `Ctrl/⌘ K` command palette · `/` composer · `Ctrl/⌘ Enter` send · `Ctrl/⌘ O` attach · `1–5` official questions · `F` fit scene · `I` inspect · `?` shortcuts · `Esc` close.
