import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Activity, Copy, Focus, Layers } from "lucide-react";
import { useNavigate, useSearch } from "@tanstack/react-router";

import { TopBar } from "@/components/TopBar";
import { FooterBar } from "@/components/FooterBar";
import { LeftDrawer } from "@/components/LeftDrawer";
import { IngestPanel } from "@/components/IngestPanel";
import { ChatPanel } from "@/components/ChatPanel";
import { ResultCard } from "@/components/ResultCard";
import { CommandPalette, type PaletteCommand } from "@/components/CommandPalette";
import { EvidenceMap, type EvidenceMapHandle } from "@/components/EvidenceMap";

import { apiUrl, downloadExport, fetchHealth, fetchJob, fetchModels, ingestRasters, runJob } from "@/lib/api";
import { QUESTION_CHIPS, SENSORS } from "@/lib/chips";
import { cn } from "@/lib/cn";
import {
  copyText,
  formatBbox,
  formatElapsed,
} from "@/lib/format";
import { TERMINAL_STATUSES, type IngestResponse, type JobView } from "@/lib/schema";

const LS_JOB = "satquery.lastJobId";

type Toast = { id: number; kind: "ok" | "bad" | "info"; text: string };

export function AnalyzePage() {
  const { job: urlJob } = useSearch({ from: "/" });
  const navigate = useNavigate({ from: "/" });

  // ─── State ───
  const [files, setFiles] = useState<File[]>([]);
  const [sensor, setSensor] = useState<string>(SENSORS[0]);
  const [query, setQuery] = useState<string>(QUESTION_CHIPS[0].query);
  const [jobId, setJobId] = useState<string | null>(null);
  const [ingestNote, setIngestNote] = useState<string | null>(null);
  const [ingestMeta, setIngestMeta] = useState<IngestResponse | null>(null);
  const [footprintOn, setFootprintOn] = useState(true);
  const [rasterOn, setRasterOn] = useState(true);
  const [rasterOpacity, setRasterOpacity] = useState(0.82);
  const [cursor, setCursor] = useState<{ lng: number; lat: number } | null>(null);
  const [zoom, setZoom] = useState(4.2);

  const [helpOpen, setHelpOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [inspectOpen, setInspectOpen] = useState(false);
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [now, setNow] = useState(() => Date.now());
  const [runOrigin, setRunOrigin] = useState<number | null>(null);

  // ─── Refs ───
  const inputRef = useRef<HTMLInputElement | null>(null);
  const queryRef = useRef<HTMLTextAreaElement | null>(null);
  const mapRef = useRef<EvidenceMapHandle | null>(null);
  const toastId = useRef(0);

  // ─── Helpers ───
  const toast = (kind: Toast["kind"], text: string) => {
    const id = ++toastId.current;
    setToasts((t) => [...t.slice(-3), { id, kind, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  };



  const doCopy = async (label: string, value: string | null | undefined) => {
    if (!value) return;
    await copyText(value);
    toast("ok", `Copied ${label}`);
  };

  const closeOverlays = () => {
    setHelpOpen(false);
    setPaletteOpen(false);
    setInspectOpen(false);
    setLightbox(null);
  };

  // ─── URL / localStorage sync ───
  useEffect(() => {
    if (urlJob) {
      setJobId(urlJob);
      return;
    }
    const saved = localStorage.getItem(LS_JOB);
    if (saved) {
      setJobId(saved);
      void navigate({ search: { job: saved }, replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!jobId) return;
    localStorage.setItem(LS_JOB, jobId);
    if (urlJob !== jobId) void navigate({ search: { job: jobId }, replace: true });
  }, [jobId, urlJob, navigate]);

  // ─── Queries ───
  const healthQuery = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 12_000 });
  const modelsQuery = useQuery({ queryKey: ["models"], queryFn: fetchModels, refetchInterval: 30_000 });

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (!status || TERMINAL_STATUSES.has(status)) return false;
      return 2500;
    },
  });

  const job: JobView | null = jobQuery.data ?? null;
  const apiOk = healthQuery.isSuccess;
  const ollamaOk = healthQuery.data?.ollama === "ok";
  const pgOk = healthQuery.data?.postgres?.status === "connected";

  // ─── Mutations ───
  const ingestMut = useMutation({
    mutationFn: () => ingestRasters(files, sensor, query),
    onSuccess: (data) => {
      setJobId(data.job_id);
      setIngestMeta(data);
      setIngestNote(
        data.valid
          ? `${data.input_class ?? "CLASSIFIED"} · ${data.assets.length} scene(s)`
          : data.refusal_reason ?? "Classification refused",
      );
      toast(data.valid ? "ok" : "bad", data.valid ? `Ingested ${data.job_id.slice(0, 8)}` : "Ingest refused");
    },
    onError: (err) => toast("bad", (err as Error).message),
  });

  const runMut = useMutation({
    mutationFn: () => runJob(jobId!, query),
    onSuccess: () => {
      setRunOrigin(Date.now());
      void jobQuery.refetch();
      toast("info", "LangGraph started");
    },
    onError: (err) => toast("bad", (err as Error).message),
  });

  const canRun =
    Boolean(jobId) &&
    ingestMut.data?.valid !== false &&
    Boolean(query.trim()) &&
    (job?.status === "ingested" ||
      job?.status === "completed" ||
      job?.status === "failed" ||
      job?.status === "refused" ||
      !job);
  const running = job?.status === "running" || runMut.isPending;

  // ─── Timer for elapsed ───
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setNow(Date.now()), 200);
    return () => window.clearInterval(id);
  }, [running]);

  // ─── Status change toasts ───
  const prevStatus = useRef<string | undefined>(undefined);
  useEffect(() => {
    const status = job?.status;
    const prev = prevStatus.current;
    prevStatus.current = status;
    if (prev === "running" && status === "completed") toast("ok", "Job completed");
    if (prev === "running" && status === "failed") toast("bad", "Job failed");
    if (prev === "running" && status === "refused") toast("bad", job?.refusal_reason ?? "Refused");
  }, [job?.status, job?.refusal_reason]);

  // ─── Document title ───
  useEffect(() => {
    const status = job?.status ?? "idle";
    document.title = jobId ? `SatQuery · ${status}` : "SatQuery · SAC / ISRO";
  }, [job?.status, jobId]);

  // ─── Derived data ───
  const previewSrc = useMemo(() => {
    const url = job?.assets[0]?.preview_url;
    if (!url) return null;
    if (job.status === "completed" || job.tile_count > 0) return apiUrl(url);
    return null;
  }, [job]);

  const bounds = job?.assets.find((a) => a.bounds_wgs84 && a.bounds_wgs84.length === 4)?.bounds_wgs84 ?? null;

  const elapsedMs = useMemo(() => {
    if (!running && !runOrigin) {
      if (job?.traces.length && job.traces[0]?.timestamp && job.traces.at(-1)?.timestamp) {
        const a = Date.parse(job.traces[0].timestamp!);
        const b = Date.parse(job.traces.at(-1)!.timestamp!);
        if (!Number.isNaN(a) && !Number.isNaN(b)) return Math.max(0, b - a);
      }
      return null;
    }
    const startIso = job?.traces[0]?.timestamp;
    const start = startIso ? Date.parse(startIso) : runOrigin;
    if (!start || Number.isNaN(start)) return runOrigin ? now - runOrigin : null;
    return Math.max(0, now - start);
  }, [job, running, runOrigin, now]);

  // ─── Keyboard shortcuts ───
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = Boolean(target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
      const meta = e.metaKey || e.ctrlKey;

      if (e.key === "Escape") {
        closeOverlays();
        return;
      }
      if (meta && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
        setHelpOpen(false);
        return;
      }
      if (meta && e.key === "Enter") {
        e.preventDefault();
        if (canRun && !running && jobId) runMut.mutate();
        return;
      }
      if (meta && e.key.toLowerCase() === "o") {
        e.preventDefault();
        inputRef.current?.click();
        return;
      }
      if (typing || meta) return;
      if (e.key === "?") {
        e.preventDefault();
        setHelpOpen((v) => !v);
        return;
      }
      if (e.key === "/" || e.key.toLowerCase() === "q") {
        e.preventDefault();
        queryRef.current?.focus();
        return;
      }
      if (e.key.toLowerCase() === "f") {
        e.preventDefault();
        mapRef.current?.fit();
        return;
      }
      if (e.key.toLowerCase() === "l") {
        e.preventDefault();
        setFootprintOn((v) => !v);
        return;
      }
      if (e.key.toLowerCase() === "r") {
        e.preventDefault();
        setRasterOn((v) => !v);
        return;
      }
      if (e.key.toLowerCase() === "j" && jobId) {
        e.preventDefault();
        void doCopy("job id", jobId);
        return;
      }
      if (e.key.toLowerCase() === "c" && cursor) {
        e.preventDefault();
        void doCopy("coords", `${cursor.lng.toFixed(6)}, ${cursor.lat.toFixed(6)}`);
        return;
      }
      if (e.key.toLowerCase() === "i") {
        e.preventDefault();
        setInspectOpen((v) => !v);
        return;
      }
      const digit = Number(e.key);
      if (digit >= 1 && digit <= QUESTION_CHIPS.length) {
        e.preventDefault();
        setQuery(QUESTION_CHIPS[digit - 1].query);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canRun, running, jobId, runMut, cursor]);

  // ─── Command palette commands ───
  const commands: PaletteCommand[] = [
    { id: "open", label: "Open GeoTIFF", kbd: "⌘O", run: () => inputRef.current?.click() },
    { id: "ingest", label: "Ingest scenes", hint: "Classify + persist", disabled: !files.length || ingestMut.isPending, run: () => ingestMut.mutate() },
    { id: "run", label: "Run analysis", kbd: "⌘↵", disabled: !canRun || running, run: () => runMut.mutate() },
    { id: "query", label: "Focus query", kbd: "Q", run: () => queryRef.current?.focus() },
    { id: "fit", label: "Fit AOI", kbd: "F", disabled: !bounds, run: () => mapRef.current?.fit() },
    { id: "foot", label: footprintOn ? "Hide footprint" : "Show footprint", kbd: "L", run: () => setFootprintOn((v) => !v) },
    { id: "raster", label: rasterOn ? "Hide raster" : "Show raster", kbd: "R", disabled: !previewSrc, run: () => setRasterOn((v) => !v) },
    { id: "copy-job", label: "Copy job id", kbd: "J", disabled: !jobId, run: () => void doCopy("job id", jobId) },
    {
      id: "copy-coords",
      label: "Copy cursor coordinates",
      kbd: "C",
      disabled: !cursor,
      run: () => cursor && void doCopy("coords", `${cursor.lng.toFixed(6)}, ${cursor.lat.toFixed(6)}`),
    },
    { id: "copy-bbox", label: "Copy bounding box", disabled: !bounds, run: () => void doCopy("bbox", formatBbox(bounds!)) },
    { id: "copy-answer", label: "Copy answer", disabled: !job?.answer?.text, run: () => void doCopy("answer", job?.answer?.text) },
    { id: "geojson", label: "Export GeoJSON", disabled: !jobId, run: () => jobId && downloadExport(jobId, "geojson") },
    { id: "kml", label: "Export KML", disabled: !jobId, run: () => jobId && downloadExport(jobId, "kml") },
    { id: "inspect", label: "Inspect JobView JSON", kbd: "I", disabled: !job, run: () => setInspectOpen(true) },
    ...QUESTION_CHIPS.map((chip, i) => ({
      id: `chip-${chip.id}`,
      label: `Chip · ${chip.label}`,
      kbd: String(i + 1),
      hint: chip.query,
      run: () => setQuery(chip.query),
    })),
  ];

  // ─── Render ───
  return (
    <div className="flex h-full flex-col gap-2.5 p-2.5">
      {/* ── Top Bar ── */}
      <TopBar
        apiOk={apiOk}
        ollamaOk={ollamaOk ?? false}
        pgOk={pgOk ?? false}
        vlmBackend={modelsQuery.data?.talking_vlm_backend ?? "vlm"}
        job={job}
        onPaletteOpen={() => setPaletteOpen(true)}
        onHelpOpen={() => setHelpOpen(true)}
      />

      {/* ── Main Content: Drawer + Map ── */}
      <main className="flex min-h-0 flex-1 gap-2.5">
        {/* Left Drawer */}
        <LeftDrawer>
          <IngestPanel
            files={files}
            sensor={sensor}
            ingestMeta={ingestMeta}
            ingestNote={ingestNote}
            isPending={ingestMut.isPending}
            isError={ingestMut.isError}
            errorMessage={ingestMut.isError ? (ingestMut.error as Error).message : ""}
            inputRef={inputRef}
            onFilesChange={setFiles}
            onSensorChange={setSensor}
            onIngest={() => ingestMut.mutate()}
          />
          <ChatPanel
            query={query}
            job={job}
            running={running}
            canRun={canRun}
            elapsedMs={elapsedMs}
            queryRef={queryRef}
            onQueryChange={setQuery}
            onRun={() => runMut.mutate()}
            onLightbox={setLightbox}
            apiUrl={apiUrl}
            runError={runMut.isError ? (runMut.error as Error).message : null}
          />
        </LeftDrawer>

        {/* Map Area */}
        <section className="rise relative min-h-[360px] flex-1 overflow-hidden rounded-xl ring-1 ring-white/8" style={{ animationDelay: "50ms" }}>
          {/* Inner shadow */}
          <div className="pointer-events-none absolute inset-0 z-[1] shadow-[inset_0_0_60px_rgba(0,0,0,0.35)]" />
          <div className="sq-crosshair" aria-hidden />

          {/* Layer controls */}
          <div className="absolute left-3 top-3 z-10 flex flex-col gap-2">
            <div className="rounded-full border border-white/8 bg-black/50 px-3 py-1.5 font-mono text-[10px] tracking-[0.14em] text-muted/80 uppercase backdrop-blur-md">
              Evidence · EPSG:4326
            </div>
            <div className="pointer-events-auto w-[160px] rounded-xl border border-white/8 bg-black/55 p-2.5 font-mono text-[10px] backdrop-blur-md">
              <div className="mb-2 flex items-center gap-1.5 text-muted/80 uppercase tracking-[0.12em]">
                <Layers className="h-3 w-3" /> Layers
              </div>
              <label className="flex items-center justify-between gap-2 text-ink/90">
                <span>Raster</span>
                <input
                  type="checkbox"
                  checked={rasterOn}
                  disabled={!previewSrc}
                  onChange={(e) => setRasterOn(e.target.checked)}
                />
              </label>
              <input
                type="range"
                min={0.15}
                max={1}
                step={0.05}
                value={rasterOpacity}
                disabled={!rasterOn || !previewSrc}
                onChange={(e) => setRasterOpacity(Number(e.target.value))}
                className="mt-1.5 w-full accent-saffron"
              />
              <label className="mt-2 flex items-center justify-between gap-2 text-ink/90">
                <span>Footprint</span>
                <input type="checkbox" checked={footprintOn} onChange={(e) => setFootprintOn(e.target.checked)} />
              </label>
              <div className="mt-2 flex gap-1">
                <button
                  type="button"
                  disabled={!bounds}
                  onClick={() => mapRef.current?.fit()}
                  className="flex flex-1 items-center justify-center gap-1 rounded-md border border-white/8 py-1 text-muted/80 transition hover:border-cyan/30 hover:text-ink disabled:opacity-30"
                >
                  <Focus className="h-3 w-3" /> Fit
                </button>
                <button
                  type="button"
                  disabled={!bounds}
                  onClick={() => void doCopy("bbox", formatBbox(bounds!))}
                  className="flex flex-1 items-center justify-center gap-1 rounded-md border border-white/8 py-1 text-muted/80 transition hover:border-cyan/30 hover:text-ink disabled:opacity-30"
                >
                  <Copy className="h-3 w-3" /> BBOX
                </button>
              </div>
            </div>
          </div>

          {/* Empty state */}
          {!job && (
            <div className="pointer-events-none absolute inset-0 z-10 grid place-items-center">
              <ol className="glass max-w-sm space-y-2.5 rounded-xl px-6 py-5 font-mono text-[11px] tracking-[0.06em] text-muted/80">
                <li><span className="mr-2 text-saffron">01</span> Drop a GeoTIFF · classify</li>
                <li><span className="mr-2 text-saffron">02</span> Ask — or hit 1–5 for a chip</li>
                <li><span className="mr-2 text-saffron">03</span> Ctrl/⌘ Enter · read the receipt</li>
              </ol>
            </div>
          )}

          {/* Scan animation while running */}
          {running && (
            <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-px overflow-hidden">
              <div className="h-24 w-full bg-gradient-to-b from-cyan/30 to-transparent opacity-60" style={{ animation: "scan 2.4s linear infinite" }} />
            </div>
          )}

          {/* Map */}
          <EvidenceMap
            ref={mapRef}
            job={job}
            footprintOn={footprintOn}
            rasterOn={rasterOn}
            rasterOpacity={rasterOpacity}
            rasterUrl={previewSrc}
            onCursor={setCursor}
            onZoom={setZoom}
          />

          {/* Running indicator on map */}
          {job?.status === "running" && (
            <div className="pointer-events-none absolute bottom-10 left-3 z-10 flex items-center gap-2 rounded-full border border-cyan/25 bg-black/55 px-3 py-1.5 font-mono text-[10px] text-cyan/90 backdrop-blur-md">
              <Activity className="h-3 w-3 animate-pulse" />
              LangGraph in flight
              {elapsedMs != null ? ` · ${formatElapsed(elapsedMs)}` : ""}
            </div>
          )}

          {/* Warnings / errors badge */}
          {(job?.warnings?.length || job?.errors?.length) ? (
            <div className="absolute bottom-9 left-3 right-24 z-10 rounded-lg border border-gold/25 bg-black/60 px-3 py-1.5 font-mono text-[10px] text-gold/90 backdrop-blur-md">
              {[...(job.errors ?? []), ...(job.warnings ?? [])].join(" · ")}
            </div>
          ) : null}

          {/* Result Card — floating bottom-right */}
          <ResultCard
            key={job?.job_id ?? "none"}
            job={job}
            onInspect={() => setInspectOpen(true)}
            onDismiss={() => {}}
          />
        </section>
      </main>

      {/* ── Footer ── */}
      <FooterBar
        cursor={cursor}
        zoom={zoom}
        jobId={jobId}
        routerModel={modelsQuery.data?.router_model ?? "qwen"}
        vlmBackend={modelsQuery.data?.talking_vlm_backend ?? "mock"}
      />

      {/* ── Toasts ── */}
      <div className="pointer-events-none fixed bottom-16 right-4 z-[70] flex w-72 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "pointer-events-auto slide-up rounded-xl border px-3 py-2 font-mono text-[11px] shadow-lg backdrop-blur-md",
              t.kind === "ok" && "border-ok/30 bg-black/70 text-ok",
              t.kind === "bad" && "border-bad/30 bg-black/70 text-bad",
              t.kind === "info" && "border-cyan/30 bg-black/70 text-cyan",
            )}
          >
            {t.text}
          </div>
        ))}
      </div>

      {/* ── Command Palette ── */}
      <CommandPalette open={paletteOpen} commands={commands} onClose={() => setPaletteOpen(false)} />

      {/* ── Help Modal ── */}
      {helpOpen && (
        <button type="button" className="fixed inset-0 z-50 grid place-items-center bg-black/50 backdrop-blur-sm" onClick={() => setHelpOpen(false)}>
          <div className="glass-strong w-[min(440px,92vw)] rounded-xl p-6 text-left" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-mono text-[11px] tracking-[0.2em] text-saffron uppercase">Shortcuts</h3>
            <dl className="mt-4 space-y-2 font-mono text-[12px] text-ink">
              {[
                ["Command palette", "Ctrl K"],
                ["Run analysis", "Ctrl Enter"],
                ["Open GeoTIFF", "Ctrl O"],
                ["Focus query", "Q / /"],
                ["Fit AOI", "F"],
                ["Toggle footprint", "L"],
                ["Toggle raster", "R"],
                ["Copy job id", "J"],
                ["Copy cursor", "C"],
                ["Inspect JSON", "I"],
                ["Question chips", "1 – 5"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4">
                  <dt className="text-muted">{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-[11px] text-muted/70">Esc closes sheets. Map cursor is WGS84. Job id lives in the URL.</p>
          </div>
        </button>
      )}

      {/* ── Inspect Modal ── */}
      {inspectOpen && job && (
        <button type="button" className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4 backdrop-blur-sm" onClick={() => setInspectOpen(false)}>
          <div className="glass-strong flex max-h-[80vh] w-[min(640px,94vw)] flex-col rounded-xl p-5 text-left" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-mono text-[11px] tracking-[0.2em] text-saffron uppercase">JobView</h3>
              <button
                type="button"
                onClick={() => void doCopy("json", JSON.stringify(job, null, 2))}
                className="font-mono text-[10px] text-muted hover:text-ink"
              >
                Copy JSON
              </button>
            </div>
            <pre className="sq-scroll min-h-0 flex-1 overflow-auto rounded-lg bg-black/30 p-3 font-mono text-[11px] leading-relaxed text-ink/85">
              {JSON.stringify(job, null, 2)}
            </pre>
          </div>
        </button>
      )}

      {/* ── Lightbox ── */}
      {lightbox && (
        <button type="button" className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-6 backdrop-blur-sm" onClick={() => setLightbox(null)}>
          <img src={lightbox} alt="Scene inspect" className="max-h-[85vh] max-w-[90vw] rounded-xl ring-1 ring-white/15" />
        </button>
      )}
    </div>
  );
}
