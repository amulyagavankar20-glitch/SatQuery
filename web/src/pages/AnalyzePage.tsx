import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  Check,
  Copy,
  Download,
  Globe2,
  Radio,
  Upload,
  X,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { BrandMark } from "@/components/BrandMark";
import { EvidenceMap } from "@/components/EvidenceMap";
import { apiUrl, downloadExport, fetchHealth, fetchJob, fetchModels, ingestRasters, runJob } from "@/lib/api";
import { QUESTION_CHIPS, SENSORS } from "@/lib/chips";
import { TERMINAL_STATUSES, type JobView } from "@/lib/schema";
import { cn } from "@/lib/cn";

function StatusLed({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-white/5 bg-white/5 px-2.5 py-1 font-mono text-[10px] tracking-[0.16em] text-muted uppercase">
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

export function AnalyzePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [sensor, setSensor] = useState<string>(SENSORS[0]);
  const [query, setQuery] = useState<string>(QUESTION_CHIPS[0].query);
  const [jobId, setJobId] = useState<string | null>(null);
  const [ingestNote, setIngestNote] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [footprintOn, setFootprintOn] = useState(true);
  const [cursor, setCursor] = useState<{ lng: number; lat: number } | null>(null);
  const [zoom, setZoom] = useState(4.2);
  const [copied, setCopied] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const queryRef = useRef<HTMLTextAreaElement | null>(null);

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
  const online =
    healthQuery.data?.ollama === "ok" && healthQuery.data?.postgres?.status === "connected";

  const ingestMut = useMutation({
    mutationFn: () => ingestRasters(files, sensor, query),
    onSuccess: (data) => {
      setJobId(data.job_id);
      setIngestNote(
        data.valid
          ? `${data.input_class ?? "CLASSIFIED"} · ${data.assets.length} scene(s)`
          : data.refusal_reason ?? "Classification refused",
      );
    },
  });

  const runMut = useMutation({
    mutationFn: () => runJob(jobId!, query),
    onSuccess: () => {
      void jobQuery.refetch();
    },
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

  const previewSrc = useMemo(() => {
    const url = job?.assets[0]?.preview_url;
    if (!url) return null;
    if (job.status === "completed" || job.tile_count > 0) return apiUrl(url);
    return null;
  }, [job]);

  const takeFiles = (list: File[]) => {
    const dropped = list.filter((f) => /\.tiff?$/i.test(f.name));
    if (dropped.length) setFiles(dropped.slice(0, 2));
  };

  const copyJob = async () => {
    if (!jobId) return;
    await navigator.clipboard.writeText(jobId);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = Boolean(target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
      const meta = e.metaKey || e.ctrlKey;

      if (e.key === "Escape") {
        setHelpOpen(false);
        return;
      }
      if (e.key === "?" && !typing) {
        e.preventDefault();
        setHelpOpen((v) => !v);
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
      if (meta && e.key.toLowerCase() === "k" && !typing) {
        e.preventDefault();
        queryRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canRun, running, jobId, runMut]);

  const tools = job?.route && Array.isArray((job.route as { tools?: string[] }).tools)
    ? ((job.route as { tools?: string[] }).tools ?? [])
    : [];

  return (
    <div className="flex h-full flex-col gap-2.5 p-2.5">
      <header className="glass-strong rise flex items-center justify-between rounded-2xl px-4 py-2">
        <div className="flex items-center gap-4">
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
        </div>
        <div className="flex items-center gap-2">
          <StatusLed ok={online} label={online ? "Online" : "Offline"} />
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

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-2.5 lg:grid-cols-[272px_minmax(0,1fr)_292px]">
        <aside className="flex min-h-0 flex-col gap-2.5">
          <Panel title="Ingest" kicker="≤2 scenes" delay="40ms">
            <div
              className={cn(
                "group flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-3 py-6 text-center transition-all duration-300 active:scale-[0.99]",
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
              <p className="mt-1 font-mono text-[10px] text-muted">Cartosat · RISAT · Sentinel · open with ⌘/Ctrl O</p>
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
              {QUESTION_CHIPS.map((chip) => (
                <button
                  key={chip.id}
                  type="button"
                  onClick={() => setQuery(chip.query)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 font-mono text-[10px] tracking-[0.14em] uppercase transition duration-200 active:scale-95",
                    query === chip.query
                      ? "border-saffron/80 bg-saffron/20 text-saffron shadow-[0_0_18px_rgba(240,132,42,0.2)]"
                      : "border-white/10 text-muted hover:-translate-y-0.5 hover:border-cyan/50 hover:text-ink",
                  )}
                >
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
              {running ? "Graph running…" : "Run  ⌘/Ctrl ↵"}
            </button>
            {runMut.isError ? (
              <p className="mt-2 font-mono text-[11px] text-bad">{(runMut.error as Error).message}</p>
            ) : null}
          </Panel>
        </aside>

        <section className="rise relative min-h-[360px] overflow-hidden rounded-2xl ring-1 ring-white/10" style={{ animationDelay: "50ms" }}>
          <div className="pointer-events-none absolute inset-0 z-[1] shadow-[inset_0_0_80px_rgba(0,0,0,0.45)]" />
          <div className="absolute left-3 top-3 z-10 flex flex-col gap-2">
            <div className="rounded-full border border-white/10 bg-black/50 px-3 py-1.5 font-mono text-[10px] tracking-[0.16em] text-muted uppercase backdrop-blur-md">
              Evidence · EPSG:4326
            </div>
            <button
              type="button"
              onClick={() => setFootprintOn((v) => !v)}
              className={cn(
                "pointer-events-auto w-fit rounded-full border px-3 py-1 font-mono text-[10px] tracking-[0.14em] uppercase backdrop-blur-md transition",
                footprintOn
                  ? "border-saffron/50 bg-saffron/15 text-saffron"
                  : "border-white/10 bg-black/50 text-muted",
              )}
            >
              Footprint {footprintOn ? "on" : "off"}
            </button>
          </div>
          {running ? (
            <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-px overflow-hidden">
              <div className="h-24 w-full bg-gradient-to-b from-cyan/40 to-transparent opacity-70" style={{ animation: "scan 2.4s linear infinite" }} />
            </div>
          ) : null}
          <EvidenceMap job={job} footprintOn={footprintOn} onCursor={setCursor} onZoom={setZoom} />
          {job?.status === "running" ? (
            <div className="pointer-events-none absolute bottom-10 left-3 z-10 flex items-center gap-2 rounded-full border border-cyan/30 bg-black/55 px-3 py-1.5 font-mono text-[10px] text-cyan backdrop-blur-md">
              <Activity className="h-3 w-3 animate-pulse" />
              LangGraph in flight
            </div>
          ) : null}
        </section>

        <aside className="flex min-h-0 flex-col gap-2.5">
          <Panel title="Answer" kicker={job?.answer?.confidence ?? job?.status ?? "idle"} delay="90ms">
            <div className="mb-2 flex flex-wrap gap-1.5">
              <span className="rounded-md bg-white/5 px-2 py-0.5 font-mono text-[10px] text-muted">
                {job?.task ?? "UNROUTED"}
              </span>
              <span className="rounded-md bg-white/5 px-2 py-0.5 font-mono text-[10px] text-muted">
                {job?.tile_count ?? 0} tiles
              </span>
              {tools.length ? (
                <span className="rounded-md bg-cyan/10 px-2 py-0.5 font-mono text-[10px] text-cyan">
                  {tools.join(" → ")}
                </span>
              ) : null}
            </div>
            <p className="text-[15px] leading-relaxed text-ink/95">
              {job?.answer?.text ??
                (job?.refusal_reason
                  ? job.refusal_reason
                  : "Ingest a scene, then Ctrl/⌘ Enter to run. The receipt appears here.")}
            </p>
            {job?.answer?.backend === "mock" && job.answer.text ? (
              <p className="mt-2 font-mono text-[10px] text-gold">Specialist is mock · InternVL3-1B not loaded</p>
            ) : null}
            {previewSrc ? (
              <img
                src={previewSrc}
                alt="Processed composite"
                className="mt-3 max-h-40 w-full rounded-xl border border-white/10 object-contain bg-black/40 transition duration-500 hover:border-saffron/40"
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).style.display = "none";
                }}
              />
            ) : null}
          </Panel>

          <Panel title="Trace" kicker="Observable" className="min-h-0 flex-1" delay="120ms">
            <ol className="sq-scroll h-full max-h-[240px] overflow-y-auto pr-1">
              {(job?.traces ?? []).length === 0 ? (
                <li className="font-mono text-[11px] text-muted">No node events yet.</li>
              ) : (
                job!.traces.map((trace, i) => (
                  <li
                    key={`${trace.timestamp}-${i}`}
                    className="group relative mb-1 grid grid-cols-[16px_1fr] gap-2 rounded-lg px-1 py-1.5 pl-1 transition hover:bg-cyan/10 last:mb-0"
                  >
                    {i < job!.traces.length - 1 ? (
                      <span className="absolute left-[7px] top-6 h-[calc(100%-8px)] w-px bg-gradient-to-b from-cyan/40 to-transparent" />
                    ) : null}
                    <span className="mt-1 h-2 w-2 rounded-full bg-cyan shadow-[0_0_10px_#4ad4d4] transition group-hover:scale-125" />
                    <div>
                      <div className="text-[12px] text-ink">{trace.node_name ?? trace.event_type}</div>
                      <div className="font-mono text-[10px] text-muted">
                        {trace.event_type}
                        {trace.tool_id ? ` · ${trace.tool_id}` : ""}
                      </div>
                    </div>
                  </li>
                ))
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
            {job?.warnings?.length ? (
              <p className="mt-2 font-mono text-[10px] text-gold">{job.warnings.join(" · ")}</p>
            ) : null}
          </Panel>
        </aside>
      </main>

      <footer className="glass rise flex flex-wrap items-center justify-between gap-2 rounded-xl px-3 py-1.5 font-mono text-[10px] text-muted">
        <div className="flex flex-wrap items-center gap-3">
          <span>
            <kbd>Ctrl</kbd>
            <kbd>↵</kbd> run
          </span>
          <span>
            <kbd>Ctrl</kbd>
            <kbd>O</kbd> open
          </span>
          <span>
            <kbd>?</kbd> keys
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="tabular-nums text-ink/80">
            {cursor
              ? `${cursor.lng >= 0 ? cursor.lng.toFixed(4) + "°E" : Math.abs(cursor.lng).toFixed(4) + "°W"}  ${cursor.lat >= 0 ? cursor.lat.toFixed(4) + "°N" : Math.abs(cursor.lat).toFixed(4) + "°S"}`
              : "—"}
          </span>
          <span>z {zoom.toFixed(1)}</span>
          {jobId ? (
            <button
              type="button"
              onClick={() => void copyJob()}
              className="inline-flex items-center gap-1 text-ink/80 transition hover:text-saffron"
            >
              {copied ? <Check className="h-3 w-3 text-ok" /> : <Copy className="h-3 w-3" />}
              {copied ? "copied" : jobId.slice(0, 8)}
            </button>
          ) : (
            <span>no job</span>
          )}
          <span className="hidden sm:inline">
            {modelsQuery.data?.router_model ?? "qwen"} · {modelsQuery.data?.talking_vlm_backend ?? "mock"}
          </span>
        </div>
      </footer>

      {helpOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-50 grid place-items-center bg-black/50 backdrop-blur-sm"
          onClick={() => setHelpOpen(false)}
        >
          <div
            className="glass-strong w-[min(420px,92vw)] rounded-2xl p-6 text-left"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="font-mono text-[11px] tracking-[0.24em] text-saffron uppercase">Shortcuts</h3>
            <dl className="mt-4 space-y-2 font-mono text-[12px] text-ink">
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Run analysis</dt>
                <dd>
                  <kbd>Ctrl</kbd> <kbd>Enter</kbd>
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Open GeoTIFF</dt>
                <dd>
                  <kbd>Ctrl</kbd> <kbd>O</kbd>
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Focus query</dt>
                <dd>
                  <kbd>Ctrl</kbd> <kbd>K</kbd>
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted">This sheet</dt>
                <dd>
                  <kbd>?</kbd>
                </dd>
              </div>
            </dl>
            <p className="mt-4 text-[11px] text-muted">Esc to close. Map cursor is WGS84.</p>
          </div>
        </button>
      ) : null}
    </div>
  );
}
