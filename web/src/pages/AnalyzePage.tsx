import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  Check,
  Copy,
  Crosshair,
  Download,
  Focus,
  Globe2,
  Layers,
  Radio,
  Upload,
  X,
} from "lucide-react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { BrandMark } from "@/components/BrandMark";
import { CommandPalette, type PaletteCommand } from "@/components/CommandPalette";
import { EvidenceMap, type EvidenceMapHandle } from "@/components/EvidenceMap";
import { PipelineStrip } from "@/components/PipelineStrip";
import { apiUrl, downloadExport, fetchHealth, fetchJob, fetchModels, ingestRasters, runJob } from "@/lib/api";
import { QUESTION_CHIPS, SENSORS } from "@/lib/chips";
import { cn } from "@/lib/cn";
import {
  bboxSpanKm,
  copyText,
  formatBbox,
  formatBytes,
  formatClock,
  formatElapsed,
  formatLngLat,
} from "@/lib/format";
import { traceTone } from "@/lib/pipeline";
import { TERMINAL_STATUSES, type IngestResponse, type JobView } from "@/lib/schema";

const LS_JOB = "satquery.lastJobId";

type Toast = { id: number; kind: "ok" | "bad" | "info"; text: string };

function StatusLed({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/5 bg-white/5 px-2 py-1 font-mono text-[9px] tracking-[0.14em] text-muted uppercase">
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full transition-all duration-500",
          ok ? "bg-ok shadow-[0_0_10px_#3dba7a]" : "bg-bad shadow-[0_0_10px_#e05b56]",
        )}
      />
      {label}
    </span>
  );
}

function Panel({
  title,
  kicker,
  children,
  className,
  delay = "0ms",
}: {
  title: string;
  kicker?: string;
  children: ReactNode;
  className?: string;
  delay?: string;
}) {
  return (
    <section
      className={cn("glass rise flex min-h-0 flex-col overflow-hidden rounded-2xl", className)}
      style={{ animationDelay: delay }}
    >
      <header className="flex items-baseline justify-between border-b border-white/10 px-4 py-2">
        <h2 className="bg-gradient-to-r from-saffron to-gold bg-clip-text font-mono text-[11px] font-medium tracking-[0.26em] text-transparent uppercase">
          {title}
        </h2>
        {kicker ? <span className="font-mono text-[10px] tracking-wider text-muted/90">{kicker}</span> : null}
      </header>
      <div className="min-h-0 flex-1 p-3.5">{children}</div>
    </section>
  );
}

function sceneTag(index: number, total: number) {
  if (total < 2) return "SCN";
  return index === 0 ? "T1" : "T2";
}

function confidenceClass(value: string | null | undefined) {
  const v = (value ?? "").toUpperCase();
  if (v === "HIGH") return "text-ok";
  if (v === "LOW") return "text-bad";
  if (v === "MEDIUM") return "text-gold";
  return "text-muted";
}

export function AnalyzePage() {
  const { job: urlJob } = useSearch({ from: "/" });
  const navigate = useNavigate({ from: "/" });

  const [files, setFiles] = useState<File[]>([]);
  const [sensor, setSensor] = useState<string>(SENSORS[0]);
  const [query, setQuery] = useState<string>(QUESTION_CHIPS[0].query);
  const [jobId, setJobId] = useState<string | null>(null);
  const [ingestNote, setIngestNote] = useState<string | null>(null);
  const [ingestMeta, setIngestMeta] = useState<IngestResponse | null>(null);
  const [dragging, setDragging] = useState(false);
  const [footprintOn, setFootprintOn] = useState(true);
  const [rasterOn, setRasterOn] = useState(true);
  const [rasterOpacity, setRasterOpacity] = useState(0.82);
  const [cursor, setCursor] = useState<{ lng: number; lat: number } | null>(null);
  const [zoom, setZoom] = useState(4.2);
  const [copied, setCopied] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [inspectOpen, setInspectOpen] = useState(false);
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [now, setNow] = useState(() => Date.now());
  const [runOrigin, setRunOrigin] = useState<number | null>(null);

  const inputRef = useRef<HTMLInputElement | null>(null);
  const queryRef = useRef<HTMLTextAreaElement | null>(null);
  const mapRef = useRef<EvidenceMapHandle | null>(null);
  const toastId = useRef(0);
  const traceEndRef = useRef<HTMLLIElement | null>(null);

  const toast = (kind: Toast["kind"], text: string) => {
    const id = ++toastId.current;
    setToasts((t) => [...t.slice(-3), { id, kind, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  };

  const flashCopied = (label: string) => {
    setCopied(label);
    window.setTimeout(() => setCopied(null), 1400);
  };

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
    // hydrate once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!jobId) return;
    localStorage.setItem(LS_JOB, jobId);
    if (urlJob !== jobId) void navigate({ search: { job: jobId }, replace: true });
  }, [jobId, urlJob, navigate]);

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

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setNow(Date.now()), 200);
    return () => window.clearInterval(id);
  }, [running]);

  const prevStatus = useRef<string | undefined>(undefined);
  useEffect(() => {
    const status = job?.status;
    const prev = prevStatus.current;
    prevStatus.current = status;
    if (prev === "running" && status === "completed") toast("ok", "Job completed");
    if (prev === "running" && status === "failed") toast("bad", "Job failed");
    if (prev === "running" && status === "refused") toast("bad", job?.refusal_reason ?? "Refused");
  }, [job?.status, job?.refusal_reason]);

  useEffect(() => {
    const status = job?.status ?? "idle";
    document.title = jobId ? `SatQuery · ${status}` : "SatQuery · SAC / ISRO";
  }, [job?.status, jobId]);

  useEffect(() => {
    traceEndRef.current?.scrollIntoView({ block: "nearest" });
  }, [job?.traces.length]);

  const previewSrc = useMemo(() => {
    const url = job?.assets[0]?.preview_url;
    if (!url) return null;
    if (job.status === "completed" || job.tile_count > 0) return apiUrl(url);
    return null;
  }, [job]);

  const bounds = job?.assets.find((a) => a.bounds_wgs84 && a.bounds_wgs84.length === 4)?.bounds_wgs84 ?? null;
  const span = bounds ? bboxSpanKm(bounds) : null;

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

  const takeFiles = (list: File[]) => {
    const dropped = list.filter((f) => /\.tiff?$/i.test(f.name));
    if (dropped.length) setFiles(dropped.slice(0, 2));
  };

  const doCopy = async (label: string, value: string | null | undefined) => {
    if (!value) return;
    await copyText(value);
    flashCopied(label);
    toast("ok", `Copied ${label}`);
  };

  const closeOverlays = () => {
    setHelpOpen(false);
    setPaletteOpen(false);
    setInspectOpen(false);
    setLightbox(null);
  };

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

  const tools = job?.route && Array.isArray((job.route as { tools?: string[] }).tools)
    ? ((job.route as { tools?: string[] }).tools ?? [])
    : [];

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

  const ingestAssets = ingestMeta?.assets ?? [];

  return (
    <div className="flex h-full flex-col gap-2.5 p-2.5">
      <header className="glass-strong rise flex items-center justify-between gap-3 rounded-2xl px-4 py-2">
        <div className="flex min-w-0 items-center gap-4">
          <div className="flex items-center gap-3">
            <BrandMark className="h-9 w-9 drop-shadow-[0_0_16px_rgba(240,132,42,0.35)]" />
            <div>
              <div className="text-[14px] font-semibold tracking-[0.32em] text-ink">SATQUERY</div>
              <div className="font-mono text-[10px] tracking-[0.18em] text-muted">SAC / ISRO</div>
            </div>
          </div>
          <nav className="hidden items-center gap-1 rounded-full border border-white/10 bg-black/20 p-0.5 text-[11px] tracking-[0.16em] uppercase md:flex">
            <span className="rounded-full bg-gradient-to-r from-saffron to-gold px-3 py-1 font-medium text-navy">
              Analyze
            </span>
            <Link to="/explore" className="rounded-full px-3 py-1 text-muted transition hover:bg-white/5 hover:text-ink">
              Explore
            </Link>
          </nav>
          <PipelineStrip job={job} />
        </div>
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          <StatusLed ok={apiOk} label="API" />
          <StatusLed ok={ollamaOk} label="Ollama" />
          <StatusLed ok={pgOk} label="PostGIS" />
          <span className="hidden rounded-full border border-white/10 bg-black/20 px-2 py-1 font-mono text-[9px] tracking-[0.12em] text-muted uppercase sm:inline">
            {modelsQuery.data?.talking_vlm_backend ?? "vlm"}
          </span>
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1 font-mono text-[10px] text-muted transition hover:border-cyan/40 hover:text-ink"
            title="Command palette"
          >
            ⌘K
          </button>
          <button
            type="button"
            onClick={() => setHelpOpen(true)}
            className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1 font-mono text-[10px] text-muted transition hover:border-cyan/40 hover:text-ink"
            title="Keyboard shortcuts"
          >
            ?
          </button>
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-2.5 lg:grid-cols-[272px_minmax(0,1fr)_300px]">
        <aside className="flex min-h-0 flex-col gap-2.5">
          <Panel title="Ingest" kicker="≤2 scenes" delay="40ms">
            <div
              className={cn(
                "group flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-3 py-5 text-center transition-all duration-300 active:scale-[0.99]",
                dragging
                  ? "scale-[1.01] border-saffron bg-saffron/10 shadow-[0_0_40px_rgba(240,132,42,0.15)]"
                  : "border-white/15 bg-white/5 hover:border-saffron/70 hover:bg-saffron/10",
              )}
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                takeFiles(Array.from(e.dataTransfer.files));
              }}
            >
              <span className="mb-2 grid h-10 w-10 place-items-center rounded-full bg-saffron/15 text-saffron ring-1 ring-saffron/30 transition duration-300 group-hover:scale-110">
                <Upload className="h-4 w-4" />
              </span>
              <p className="text-sm text-ink">Drop GeoTIFF</p>
              <p className="mt-1 font-mono text-[10px] text-muted">Cartosat · RISAT · Sentinel · ⌘O</p>
              <input
                ref={inputRef}
                type="file"
                accept=".tif,.tiff"
                multiple
                className="hidden"
                onChange={(e) => takeFiles(e.target.files ? Array.from(e.target.files) : [])}
              />
            </div>
            {files.length > 0 ? (
              <ul className="mt-2 space-y-1">
                {files.map((file, i) => (
                  <li
                    key={`${file.name}-${i}`}
                    className="flex items-center gap-2 rounded-lg bg-black/25 px-2 py-1.5 font-mono text-[10px]"
                  >
                    <span className="rounded bg-saffron/20 px-1.5 py-0.5 text-saffron">{sceneTag(i, files.length)}</span>
                    <span className="min-w-0 flex-1 truncate text-ink">{file.name}</span>
                    <span className="text-muted">{formatBytes(file.size)}</span>
                    <button
                      type="button"
                      className="text-muted transition hover:text-bad"
                      onClick={(e) => {
                        e.stopPropagation();
                        setFiles(files.filter((_, j) => j !== i));
                      }}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            {ingestAssets.length ? (
              <ul className="mt-2 space-y-1 border-t border-white/5 pt-2">
                {ingestAssets.map((asset, i) => (
                  <li key={`${asset.filename}-${i}`} className="font-mono text-[10px] text-muted">
                    <span className="text-cyan">{asset.modality ?? "—"}</span>
                    {asset.width && asset.height ? ` · ${asset.width}×${asset.height}` : ""}
                    {asset.crs ? ` · ${asset.crs}` : ""}
                  </li>
                ))}
              </ul>
            ) : null}
            <label className="mt-3 block font-mono text-[10px] tracking-[0.16em] text-muted uppercase">Sensor</label>
            <select
              value={sensor}
              onChange={(e) => setSensor(e.target.value)}
              className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs text-ink outline-none transition focus:border-saffron/70"
            >
              {SENSORS.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <button
              type="button"
              disabled={!files.length || ingestMut.isPending}
              onClick={() => ingestMut.mutate()}
              className="btn-shine mt-3 w-full rounded-lg bg-gradient-to-r from-saffron to-[#ffb056] px-3 py-2 font-mono text-[11px] font-semibold tracking-[0.18em] text-navy uppercase shadow-[0_8px_24px_rgba(240,132,42,0.25)] transition hover:brightness-110 active:scale-[0.98] disabled:opacity-40 disabled:shadow-none"
            >
              {ingestMut.isPending ? "Classifying…" : "Ingest"}
            </button>
            {ingestNote ? <p className="mt-2 font-mono text-[11px] text-cyan">{ingestNote}</p> : null}
            {ingestMut.isError ? (
              <p className="mt-2 font-mono text-[11px] text-bad">{(ingestMut.error as Error).message}</p>
            ) : null}
          </Panel>

          <Panel title="Query" kicker="Intent" className="flex-1" delay="80ms">
            <div className="mb-2 flex flex-wrap gap-1.5">
              {QUESTION_CHIPS.map((chip, i) => (
                <button
                  key={chip.id}
                  type="button"
                  onClick={() => setQuery(chip.query)}
                  title={`${i + 1} · ${chip.query}`}
                  className={cn(
                    "rounded-full border px-2.5 py-1 font-mono text-[10px] tracking-[0.14em] uppercase transition duration-200 active:scale-95",
                    query === chip.query
                      ? "border-saffron/80 bg-saffron/20 text-saffron shadow-[0_0_18px_rgba(240,132,42,0.2)]"
                      : "border-white/10 text-muted hover:-translate-y-0.5 hover:border-cyan/50 hover:text-ink",
                  )}
                >
                  <span className="mr-1 text-muted/70">{i + 1}</span>
                  {chip.label}
                </button>
              ))}
            </div>
            <textarea
              ref={queryRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={4}
              className="w-full resize-none rounded-xl border border-white/10 bg-black/30 px-3 py-2.5 text-sm leading-relaxed text-ink outline-none transition focus:border-cyan/60"
            />
            <button
              type="button"
              disabled={!canRun || running}
              onClick={() => runMut.mutate()}
              className={cn(
                "btn-shine mt-3 w-full rounded-lg border border-cyan/40 bg-cyan/10 px-3 py-2 font-mono text-[11px] font-semibold tracking-[0.18em] text-cyan uppercase transition hover:border-cyan hover:bg-cyan/20 active:scale-[0.98] disabled:opacity-40",
                running && "animate-[pulse-glow_1.8s_ease-in-out_infinite]",
              )}
            >
              {running ? `Graph · ${elapsedMs != null ? formatElapsed(elapsedMs) : "…"}` : "Run  ⌘/Ctrl ↵"}
            </button>
            {runMut.isError ? (
              <p className="mt-2 font-mono text-[11px] text-bad">{(runMut.error as Error).message}</p>
            ) : null}
          </Panel>
        </aside>

        <section className="rise relative min-h-[360px] overflow-hidden rounded-2xl ring-1 ring-white/10" style={{ animationDelay: "50ms" }}>
          <div className="pointer-events-none absolute inset-0 z-[1] shadow-[inset_0_0_80px_rgba(0,0,0,0.45)]" />
          <div className="sq-crosshair" aria-hidden />
          <div className="absolute left-3 top-3 z-10 flex flex-col gap-2">
            <div className="rounded-full border border-white/10 bg-black/50 px-3 py-1.5 font-mono text-[10px] tracking-[0.16em] text-muted uppercase backdrop-blur-md">
              Evidence · EPSG:4326
            </div>
            <div className="pointer-events-auto w-[168px] rounded-xl border border-white/10 bg-black/55 p-2.5 font-mono text-[10px] backdrop-blur-md">
              <div className="mb-2 flex items-center gap-1.5 text-muted uppercase tracking-[0.14em]">
                <Layers className="h-3 w-3" /> Layers
              </div>
              <label className="flex items-center justify-between gap-2 text-ink">
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
              <label className="mt-2 flex items-center justify-between gap-2 text-ink">
                <span>Footprint</span>
                <input type="checkbox" checked={footprintOn} onChange={(e) => setFootprintOn(e.target.checked)} />
              </label>
              <div className="mt-2 flex gap-1">
                <button
                  type="button"
                  disabled={!bounds}
                  onClick={() => mapRef.current?.fit()}
                  className="flex flex-1 items-center justify-center gap-1 rounded-md border border-white/10 py-1 text-muted transition hover:border-cyan/40 hover:text-ink disabled:opacity-30"
                >
                  <Focus className="h-3 w-3" /> Fit
                </button>
                <button
                  type="button"
                  disabled={!bounds}
                  onClick={() => void doCopy("bbox", formatBbox(bounds!))}
                  className="flex flex-1 items-center justify-center gap-1 rounded-md border border-white/10 py-1 text-muted transition hover:border-cyan/40 hover:text-ink disabled:opacity-30"
                >
                  <Copy className="h-3 w-3" /> BBOX
                </button>
              </div>
            </div>
          </div>
          {!job ? (
            <div className="pointer-events-none absolute inset-0 z-10 grid place-items-center">
              <ol className="glass max-w-sm space-y-2 rounded-2xl px-6 py-5 font-mono text-[11px] tracking-[0.08em] text-muted">
                <li><span className="mr-2 text-saffron">01</span> Drop a GeoTIFF · classify</li>
                <li><span className="mr-2 text-saffron">02</span> Ask — or hit 1–5 for a chip</li>
                <li><span className="mr-2 text-saffron">03</span> Ctrl/⌘ Enter · read the receipt</li>
              </ol>
            </div>
          ) : null}
          {running ? (
            <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-px overflow-hidden">
              <div className="h-24 w-full bg-gradient-to-b from-cyan/40 to-transparent opacity-70" style={{ animation: "scan 2.4s linear infinite" }} />
            </div>
          ) : null}
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
          {job?.status === "running" ? (
            <div className="pointer-events-none absolute bottom-10 left-3 z-10 flex items-center gap-2 rounded-full border border-cyan/30 bg-black/55 px-3 py-1.5 font-mono text-[10px] text-cyan backdrop-blur-md">
              <Activity className="h-3 w-3 animate-pulse" />
              LangGraph in flight
              {elapsedMs != null ? ` · ${formatElapsed(elapsedMs)}` : ""}
            </div>
          ) : null}
          {job?.warnings?.length || job?.errors?.length ? (
            <div className="absolute bottom-9 left-3 right-24 z-10 rounded-lg border border-gold/30 bg-black/60 px-3 py-1.5 font-mono text-[10px] text-gold backdrop-blur-md">
              {[...(job.errors ?? []), ...(job.warnings ?? [])].join(" · ")}
            </div>
          ) : null}
        </section>

        <aside className="flex min-h-0 flex-col gap-2.5">
          <Panel title="Answer" kicker={job?.answer?.confidence ?? job?.status ?? "idle"} delay="90ms">
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <span className="rounded-md bg-white/5 px-2 py-0.5 font-mono text-[10px] text-muted">
                {job?.task ?? "UNROUTED"}
              </span>
              <span className="rounded-md bg-white/5 px-2 py-0.5 font-mono text-[10px] text-muted">
                {job?.input_class || "—"}
              </span>
              <span className="rounded-md bg-white/5 px-2 py-0.5 font-mono text-[10px] text-muted">
                {job?.tile_count ?? 0} tiles
              </span>
              {job?.answer?.confidence ? (
                <span className={cn("rounded-md bg-white/5 px-2 py-0.5 font-mono text-[10px]", confidenceClass(job.answer.confidence))}>
                  {job.answer.confidence}
                </span>
              ) : null}
              {tools.length ? (
                <span className="rounded-md bg-cyan/10 px-2 py-0.5 font-mono text-[10px] text-cyan">
                  {tools.join(" → ")}
                </span>
              ) : null}
              {job?.answer?.text ? (
                <button
                  type="button"
                  onClick={() => void doCopy("answer", job.answer?.text)}
                  className="ml-auto text-muted transition hover:text-saffron"
                  title="Copy answer"
                >
                  <Copy className="h-3 w-3" />
                </button>
              ) : null}
            </div>
            <p className="text-[15px] leading-relaxed text-ink/95">
              {job?.answer?.text ??
                (job?.refusal_reason
                  ? job.refusal_reason
                  : "Ingest a scene, then Ctrl/⌘ Enter to run. The receipt appears here.")}
            </p>
            {job?.answer ? (
              <p className="mt-2 font-mono text-[10px] text-muted">
                {job.answer.model}
                {job.answer.backend === "mock" ? <span className="ml-2 text-gold">mock · InternVL not loaded</span> : ` · ${job.answer.backend}`}
                {elapsedMs != null && job.status !== "running" ? ` · ${formatElapsed(elapsedMs)}` : ""}
              </p>
            ) : null}
            {previewSrc ? (
              <button type="button" className="mt-3 block w-full" onClick={() => setLightbox(previewSrc)}>
                <img
                  src={previewSrc}
                  alt="Processed composite"
                  className="max-h-32 w-full rounded-xl border border-white/10 bg-black/40 object-contain transition duration-500 hover:border-saffron/40"
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).style.display = "none";
                  }}
                />
              </button>
            ) : null}
            {job && job.tile_count > 0 ? (
              <div className="sq-scroll mt-2 flex gap-1.5 overflow-x-auto pb-1">
                {Array.from({ length: Math.min(job.tile_count, 12) }, (_, i) => {
                  const src = apiUrl(`/jobs/${job.job_id}/artifacts/tiles/${i}`);
                  return (
                    <button
                      key={i}
                      type="button"
                      onClick={() => setLightbox(src)}
                      className="h-14 w-14 shrink-0 overflow-hidden rounded-md border border-white/10 bg-black/40 transition hover:border-saffron/50"
                    >
                      <img src={src} alt={`Tile ${i}`} className="h-full w-full object-cover" />
                    </button>
                  );
                })}
              </div>
            ) : null}
            {span && bounds ? (
              <p className="mt-2 font-mono text-[10px] text-muted">
                AOI {span.w.toFixed(1)} × {span.h.toFixed(1)} km
              </p>
            ) : null}
          </Panel>

          <Panel title="Trace" kicker="Observable" className="min-h-0 flex-1" delay="120ms">
            <ol className="sq-scroll h-full max-h-[220px] overflow-y-auto pr-1">
              {(job?.traces ?? []).length === 0 ? (
                <li className="font-mono text-[11px] text-muted">No node events yet.</li>
              ) : (
                job!.traces.map((trace, i) => {
                  const tone = traceTone(trace.event_type);
                  const last = i === job!.traces.length - 1;
                  return (
                    <li
                      key={`${trace.timestamp}-${i}`}
                      ref={last ? traceEndRef : undefined}
                      className="group relative mb-1 grid grid-cols-[16px_1fr] gap-2 rounded-lg px-1 py-1.5 pl-1 transition hover:bg-cyan/10 last:mb-0"
                    >
                      {i < job!.traces.length - 1 ? (
                        <span className="absolute left-[7px] top-6 h-[calc(100%-8px)] w-px bg-gradient-to-b from-cyan/40 to-transparent" />
                      ) : null}
                      <span
                        className={cn(
                          "mt-1 h-2 w-2 rounded-full transition group-hover:scale-125",
                          tone === "ok" && "bg-ok shadow-[0_0_10px_#3dba7a]",
                          tone === "bad" && "bg-bad shadow-[0_0_10px_#e05b56]",
                          tone === "warn" && "bg-gold shadow-[0_0_10px_#e0b84a]",
                          tone === "cyan" && "bg-cyan shadow-[0_0_10px_#4ad4d4]",
                          tone === "muted" && "bg-muted",
                          last && running && "animate-pulse",
                        )}
                      />
                      <div>
                        <div className="flex items-baseline justify-between gap-2">
                          <div className="text-[12px] text-ink">{trace.node_name ?? trace.event_type}</div>
                          <div className="font-mono text-[9px] text-muted">{formatClock(trace.timestamp)}</div>
                        </div>
                        <div className="font-mono text-[10px] text-muted">
                          {trace.event_type}
                          {trace.tool_id ? ` · ${trace.tool_id}` : ""}
                        </div>
                        {trace.message ? <div className="mt-0.5 text-[11px] text-ink/70">{trace.message}</div> : null}
                      </div>
                    </li>
                  );
                })
              )}
            </ol>
          </Panel>

          <Panel title="Export" kicker="Receipt" delay="150ms">
            <div className="flex gap-2">
              {(
                [
                  { label: "GeoJSON", icon: Download, run: () => jobId && downloadExport(jobId, "geojson"), on: Boolean(jobId) },
                  { label: "KML", icon: Globe2, run: () => jobId && downloadExport(jobId, "kml"), on: Boolean(jobId) },
                ] as const
              ).map((btn) => (
                <button
                  key={btn.label}
                  type="button"
                  disabled={!btn.on}
                  onClick={btn.run}
                  className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2 py-2 font-mono text-[10px] tracking-[0.14em] text-ink uppercase transition hover:-translate-y-0.5 hover:border-saffron/60 hover:bg-saffron/10 active:scale-[0.98] disabled:opacity-35"
                >
                  <btn.icon className="h-3 w-3" /> {btn.label}
                </button>
              ))}
              <button
                type="button"
                disabled
                title="PDF not implemented (501)"
                className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/10 px-2 py-2 font-mono text-[10px] tracking-[0.14em] text-muted uppercase opacity-40"
              >
                <Radio className="h-3 w-3" /> PDF
              </button>
            </div>
            <button
              type="button"
              disabled={!job}
              onClick={() => setInspectOpen(true)}
              className="mt-2 w-full rounded-lg border border-white/10 py-1.5 font-mono text-[10px] tracking-[0.14em] text-muted uppercase transition hover:border-cyan/40 hover:text-ink disabled:opacity-35"
            >
              Inspect JobView
            </button>
          </Panel>
        </aside>
      </main>

      <footer className="glass rise flex flex-wrap items-center justify-between gap-2 rounded-xl px-3 py-1.5 font-mono text-[10px] text-muted">
        <div className="flex flex-wrap items-center gap-3">
          <span>
            <kbd>⌘K</kbd> palette
          </span>
          <span>
            <kbd>⌘</kbd>
            <kbd>↵</kbd> run
          </span>
          <span>
            <kbd>F</kbd> fit
          </span>
          <span>
            <kbd>?</kbd> keys
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="inline-flex items-center gap-1 tabular-nums text-ink/80 transition hover:text-saffron"
            disabled={!cursor}
            onClick={() => cursor && void doCopy("coords", `${cursor.lng.toFixed(6)}, ${cursor.lat.toFixed(6)}`)}
            title="Copy coordinates"
          >
            <Crosshair className="h-3 w-3" />
            {cursor ? formatLngLat(cursor.lng, cursor.lat) : "—"}
          </button>
          <span>z {zoom.toFixed(1)}</span>
          {jobId ? (
            <button
              type="button"
              onClick={() => void doCopy("job id", jobId)}
              className="inline-flex items-center gap-1 text-ink/80 transition hover:text-saffron"
            >
              {copied === "job id" ? <Check className="h-3 w-3 text-ok" /> : <Copy className="h-3 w-3" />}
              {copied === "job id" ? "copied" : jobId.slice(0, 8)}
            </button>
          ) : (
            <span>no job</span>
          )}
          <span className="hidden sm:inline">
            {modelsQuery.data?.router_model ?? "qwen"} · {modelsQuery.data?.talking_vlm_backend ?? "mock"}
          </span>
        </div>
      </footer>

      <div className="pointer-events-none fixed bottom-16 right-4 z-[70] flex w-72 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "pointer-events-auto rounded-xl border px-3 py-2 font-mono text-[11px] shadow-lg backdrop-blur-md",
              t.kind === "ok" && "border-ok/40 bg-black/70 text-ok",
              t.kind === "bad" && "border-bad/40 bg-black/70 text-bad",
              t.kind === "info" && "border-cyan/40 bg-black/70 text-cyan",
            )}
          >
            {t.text}
          </div>
        ))}
      </div>

      <CommandPalette open={paletteOpen} commands={commands} onClose={() => setPaletteOpen(false)} />

      {helpOpen ? (
        <button type="button" className="fixed inset-0 z-50 grid place-items-center bg-black/50 backdrop-blur-sm" onClick={() => setHelpOpen(false)}>
          <div className="glass-strong w-[min(440px,92vw)] rounded-2xl p-6 text-left" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-mono text-[11px] tracking-[0.24em] text-saffron uppercase">Shortcuts</h3>
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
            <p className="mt-4 text-[11px] text-muted">Esc closes sheets. Map cursor is WGS84. Job id lives in the URL.</p>
          </div>
        </button>
      ) : null}

      {inspectOpen && job ? (
        <button type="button" className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4 backdrop-blur-sm" onClick={() => setInspectOpen(false)}>
          <div className="glass-strong flex max-h-[80vh] w-[min(640px,94vw)] flex-col rounded-2xl p-5 text-left" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-mono text-[11px] tracking-[0.24em] text-saffron uppercase">JobView</h3>
              <button
                type="button"
                onClick={() => void doCopy("json", JSON.stringify(job, null, 2))}
                className="font-mono text-[10px] text-muted hover:text-ink"
              >
                Copy JSON
              </button>
            </div>
            <pre className="sq-scroll min-h-0 flex-1 overflow-auto rounded-xl bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-ink/90">
              {JSON.stringify(job, null, 2)}
            </pre>
          </div>
        </button>
      ) : null}

      {lightbox ? (
        <button type="button" className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-6 backdrop-blur-sm" onClick={() => setLightbox(null)}>
          <img src={lightbox} alt="Scene inspect" className="max-h-[85vh] max-w-[90vw] rounded-xl ring-1 ring-white/20" />
        </button>
      ) : null}
    </div>
  );
}
