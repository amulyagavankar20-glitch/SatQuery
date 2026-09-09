import { useQuery } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";

import { apiUrl, fetchHealth, fetchJob, ingestRasters, runJob } from "@/lib/api";
import { DEFAULT_LAYERS } from "@/lib/constants";
import { demoById } from "@/lib/demos";
import { loadJobs, saveJobs } from "@/lib/jobs-store";
import { mockAssistantTurn } from "@/lib/mock";
import { TERMINAL_STATUSES, type JobView } from "@/lib/schema";
import type { AssistantTurn, BBox, DemoId, JobRecord, LayerId, OverlayCollection, SceneSlot, Turn } from "@/lib/types";
import { copyText, sleep } from "@/lib/utils";

export type Toast = { id: number; text: string; kind: "ok" | "bad" };

type ConsoleContextValue = {
  slots: SceneSlot[];
  pairFitness: number | null;
  turns: Turn[];
  draft: string;
  layers: Record<LayerId, boolean>;
  jobs: JobRecord[];
  jobsOpen: boolean;
  sceneSheetOpen: boolean;
  paletteOpen: boolean;
  helpOpen: boolean;
  inspectOpen: boolean;
  dragging: boolean;
  sending: boolean;
  hasScene: boolean;
  hasSar: boolean;
  hasOptical: boolean;
  apiUp: boolean;
  toasts: Toast[];
  latestJobId: string | null;
  latestAnswer: string | null;
  inspectJson: string | null;
  setDraft: (value: string) => void;
  insertChip: (query: string) => void;
  loadDemo: (id: DemoId) => void;
  attachFiles: (files: File[], bounds?: BBox) => void;
  removeSlot: (slot: "T1" | "T2") => void;
  setLayer: (id: LayerId, on: boolean) => void;
  toggleLayer: (id: LayerId) => void;
  send: (override?: string) => void;
  openJobs: () => void;
  closeJobs: () => void;
  restoreJob: (id: string) => void;
  setSceneSheetOpen: (open: boolean) => void;
  setPaletteOpen: (open: boolean) => void;
  setHelpOpen: (open: boolean) => void;
  setInspectOpen: (open: boolean) => void;
  openFilePicker: () => void;
  clearThread: () => void;
  resetScene: () => void;
  toast: (text: string, kind?: Toast["kind"]) => void;
  copyJobId: () => void;
  copyAnswer: () => void;
  closeOverlays: () => void;
  onDragEnter: () => void;
  onDragLeave: () => void;
  onDrop: (files: File[]) => void;
  composerRef: RefObject<HTMLTextAreaElement | null>;
  fileInputRef: RefObject<HTMLInputElement | null>;
  evidencePulse: boolean;
  setEvidencePulse: (on: boolean) => void;
  answerFocus: boolean;
  setAnswerFocus: (on: boolean) => void;
  activeSlot: "T1" | "T2";
  setActiveSlot: (slot: "T1" | "T2") => void;
  toggleSlotModality: (slot?: "T1" | "T2") => void;
};

const ConsoleContext = createContext<ConsoleContextValue | null>(null);

const DEFAULT_BOUNDS: BBox = [72.5, 23.0, 72.7, 23.2];

function isRaster(file: File) {
  const name = file.name.toLowerCase();
  return name.endsWith(".tif") || name.endsWith(".tiff") || name.endsWith(".jpg") || name.endsWith(".jpeg") || name.endsWith(".png");
}

function isTiff(file: File) {
  const name = file.name.toLowerCase();
  return name.endsWith(".tif") || name.endsWith(".tiff");
}

function guessModality(file: File, index: number): SceneSlot["modality"] {
  const n = file.name.toLowerCase();
  if (n.includes("sar") || n.includes("risat") || n.includes("s1") || n.includes("sentinel-1") || n.includes("vv") || n.includes("vh")) return "SAR";
  if (index === 1 && n.includes("t2")) return "OPTICAL";
  return "OPTICAL";
}

function slotFromFile(file: File, slot: "T1" | "T2", index: number, bounds?: BBox): SceneSlot {
  const previewUrl = isTiff(file) ? "" : URL.createObjectURL(file);
  const mod = guessModality(file, index);
  return {
    id: crypto.randomUUID(),
    slot,
    filename: file.name,
    modality: mod,
    sensor: mod === "SAR" ? "Sentinel-1" : "Cartosat-2S",
    crs: "EPSG:4326",
    date: new Date(file.lastModified).toISOString().slice(0, 10),
    bands: mod === "SAR" ? 2 : 4,
    bounds: bounds ?? DEFAULT_BOUNDS,
    previewUrl,
    file,
  };
}

function prettyConfidence(raw?: string | null): AssistantTurn["confidence"] {
  if (!raw) return "Medium";
  const u = raw.toUpperCase();
  if (u === "LOW") return "Low";
  if (u === "HIGH") return "High";
  return "Medium";
}

function mapLiveJob(job: JobView, slots: SceneSlot[], overlays?: OverlayCollection): Omit<AssistantTurn, "id"> {
  const asset = job.assets.find((a) => a.bounds_wgs84 && a.bounds_wgs84.length === 4);
  const bounds = (asset?.bounds_wgs84 as BBox | undefined) ?? slots[0]?.bounds ?? DEFAULT_BOUNDS;
  const optical = job.assets.find((a) => a.modality === "OPTICAL") ?? job.assets[0];
  const sar = job.assets.find((a) => a.modality === "SAR");
  const failed = job.status === "failed" || job.status === "refused";
  return {
    role: "assistant",
    status: failed ? "failed" : "completed",
    answer: job.answer?.text || undefined,
    confidence: prettyConfidence(job.answer?.confidence),
    jobId: job.job_id,
    bounds,
    opticalUrl: optical?.preview_url ? apiUrl(optical.preview_url) : (slots.find((s) => s.modality === "OPTICAL")?.previewUrl ?? null),
    sarUrl: sar?.preview_url ? apiUrl(sar.preview_url) : (slots.find((s) => s.modality === "SAR")?.previewUrl ?? null),
    vvUrl: sar ? apiUrl(`/jobs/${job.job_id}/artifacts/vv`) : null,
    vhUrl: sar ? apiUrl(`/jobs/${job.job_id}/artifacts/vh`) : null,
    overlayUrl: sar ? apiUrl(`/jobs/${job.job_id}/artifacts/overlay`) : null,
    compareUrl: slots.find((s) => s.slot === "T2" && s.modality === "OPTICAL")?.previewUrl ?? null,
    overlays: overlays ?? mockAssistantTurn(job.query, slots).overlays,
    trace:
      job.traces.length > 0
        ? job.traces.map((t) => ({
            tool: t.tool_id ?? t.node_name ?? t.event_type,
            params: {
              event: t.event_type,
              ...(t.message ? { message: t.message } : {}),
            },
          }))
        : mockAssistantTurn(job.query, slots).trace,
    error: failed ? (job.refusal_reason ?? job.errors[0] ?? "Run failed") : undefined,
  };
}

export function ConsoleProvider({ children }: { children: ReactNode }) {
  const [slots, setSlots] = useState<SceneSlot[]>([]);
  const [pairFitness, setPairFitness] = useState<number | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [layers, setLayers] = useState<Record<LayerId, boolean>>({ ...DEFAULT_LAYERS });
  const [jobs, setJobs] = useState<JobRecord[]>(() => loadJobs());
  const [jobsOpen, setJobsOpen] = useState(false);
  const [sceneSheetOpen, setSceneSheetOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [inspectOpen, setInspectOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [sending, setSending] = useState(false);
  const [evidencePulse, setEvidencePulse] = useState(false);
  const [answerFocus, setAnswerFocus] = useState(false);
  const [activeSlot, setActiveSlot] = useState<"T1" | "T2">("T1");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dragCount = useRef(0);
  const toastId = useRef(0);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: false,
    refetchInterval: 30_000,
  });
  const apiUp = healthQuery.isSuccess;

  const persistJobs = useCallback((next: JobRecord[]) => {
    setJobs(next);
    saveJobs(next);
  }, []);

  const toast = useCallback((text: string, kind: Toast["kind"] = "ok") => {
    const id = ++toastId.current;
    setToasts((t) => [...t.slice(-2), { id, text, kind }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 2800);
  }, []);

  const applySlots = useCallback((next: SceneSlot[]) => {
    setSlots(next);
    setPairFitness(next.length >= 2 ? 0.91 : null);
  }, []);

  const loadDemo = useCallback(
    (id: DemoId) => {
      const demo = demoById(id);
      applySlots(demo.slots.map((s) => ({ ...s, id: crypto.randomUUID() })));
      setPairFitness(demo.pairFitness);
      setTurns([]);
      setActiveSlot("T1");
      setSceneSheetOpen(false);
      toast(`Loaded ${demo.title}`);
    },
    [applySlots, toast],
  );

  const attachFiles = useCallback(
    (incoming: File[], bounds?: BBox) => {
      const files = incoming.filter(isRaster).slice(0, 2);
      if (!files.length) {
        toast("Drop a GeoTIFF or PNG", "bad");
        return;
      }
      setSlots((prev) => {
        let next = [...prev];
        if (files.length === 2 || prev.length === 0) {
          next = files.map((file, i) => slotFromFile(file, i === 0 ? "T1" : "T2", i, bounds));
          setActiveSlot("T1");
        } else {
          const slot: "T1" | "T2" = prev.some((s) => s.slot === "T1") ? "T2" : "T1";
          const created = slotFromFile(files[0], slot, slot === "T2" ? 1 : 0, bounds);
          next = [...prev.filter((s) => s.slot !== slot), created].sort((a, b) => a.slot.localeCompare(b.slot));
        }
        setPairFitness(next.length >= 2 ? 0.91 : null);
        return next;
      });
      toast("Scene attached");
    },
    [toast],
  );

  const removeSlot = useCallback((slot: "T1" | "T2") => {
    setSlots((prev) => {
      const next = prev.filter((s) => s.slot !== slot);
      setPairFitness(next.length >= 2 ? 0.91 : null);
      if (slot === "T2") setActiveSlot("T1");
      return next;
    });
  }, []);

  const toggleSlotModality = useCallback((targetSlot?: "T1" | "T2") => {
    const slotToToggle = targetSlot ?? activeSlot;
    setSlots((prev) =>
      prev.map((s) => {
        if (s.slot !== slotToToggle) return s;
        const nextMod: "OPTICAL" | "SAR" = s.modality === "SAR" ? "OPTICAL" : "SAR";
        return {
          ...s,
          modality: nextMod,
          sensor: nextMod === "SAR" ? "Sentinel-1" : "Cartosat-2S",
        };
      }),
    );
    toast(`Switched ${slotToToggle} to SAR modality`);
  }, [activeSlot, toast]);

  const setLayer = useCallback((id: LayerId, on: boolean) => {
    setLayers((prev) => ({ ...prev, [id]: on }));
  }, []);

  const toggleLayer = useCallback((id: LayerId) => {
    setLayers((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const insertChip = useCallback((query: string) => {
    setDraft(query);
    requestAnimationFrame(() => composerRef.current?.focus());
  }, []);

  const send = useCallback((override?: string) => {
    const query = (override ?? draft).trim();
    if (!query || slots.length === 0 || sending) return;

    const userTurn: Turn = { id: crypto.randomUUID(), role: "user", query };
    const pendingId = crypto.randomUUID();
    const pending: AssistantTurn = {
      id: pendingId,
      role: "assistant",
      status: "pending",
      pendingLabel: "Reading the pair…",
      jobId: pendingId,
      bounds: slots[0]!.bounds,
      opticalUrl: slots.find((s) => s.modality === "OPTICAL")?.previewUrl ?? slots[0]!.previewUrl,
      sarUrl: slots.find((s) => s.modality === "SAR")?.previewUrl ?? null,
      compareUrl: slots.find((s) => s.slot === "T2" && s.modality === "OPTICAL")?.previewUrl ?? null,
    };

    setDraft("");
    setSending(true);
    setTurns((prev) => [...prev, userTurn, pending]);

    const files = slots.map((s) => s.file).filter((f): f is File => Boolean(f));
    const snapshot = slots;

    void (async () => {
      let result: Omit<AssistantTurn, "id"> | null = null;

      if (apiUp && files.length) {
        try {
          const ingest = await ingestRasters(files, snapshot[0]?.sensor ?? "Cartosat-2S", query);
          if (ingest.valid) {
            applySlots(
              snapshot.map((s, i) => {
                const asset = ingest.assets[i];
                if (!asset) return s;
                return {
                  ...s,
                  crs: asset.crs ?? s.crs,
                  bands: asset.width && asset.height ? s.bands : s.bands,
                  bounds: (asset.bounds_wgs84 as BBox | undefined) ?? s.bounds,
                  filename: asset.filename ?? s.filename,
                  modality: (asset.modality as SceneSlot["modality"]) ?? s.modality,
                  sensor: asset.sensor ?? s.sensor,
                };
              }),
            );
            await runJob(ingest.job_id, query);
            for (let i = 0; i < 48; i++) {
              await sleep(2500);
              const job = await fetchJob(ingest.job_id);
              if (TERMINAL_STATUSES.has(job.status)) {
                let overlays: OverlayCollection | undefined;
                const geo = job.overlays[0]?.geojson_url;
                if (geo) {
                  try {
                    const res = await fetch(apiUrl(geo));
                    if (res.ok) overlays = (await res.json()) as OverlayCollection;
                  } catch {
                    /* mock overlays instead */
                  }
                }
                result = mapLiveJob(job, snapshot, overlays);
                break;
              }
            }
          }
        } catch {
          result = null;
        }
      }

      if (!result) {
        await sleep(3200);
        result = mockAssistantTurn(query, snapshot);
      }

      const completed: AssistantTurn = { ...result, id: pendingId };
      setTurns((prev) => {
        const next = prev.map((t) => (t.id === pendingId ? completed : t));
        const record: JobRecord = {
          id: completed.jobId,
          query,
          createdAt: Date.now(),
          summary: snapshot.map((s) => s.filename).join(" · "),
          slots: snapshot.map(({ file: _file, ...rest }) => rest),
          pairFitness: snapshot.length >= 2 ? 0.91 : null,
          turns: next,
        };
        persistJobs([record, ...jobs.filter((j) => j.id !== record.id)].slice(0, 16));
        return next;
      });
      setSending(false);
    })();
  }, [apiUp, applySlots, draft, jobs, persistJobs, sending, slots]);

  const closeOverlays = useCallback(() => {
    setPaletteOpen(false);
    setHelpOpen(false);
    setInspectOpen(false);
    setJobsOpen(false);
    setSceneSheetOpen(false);
  }, []);

  const clearThread = useCallback(() => {
    setTurns([]);
    setDraft("");
  }, []);

  const resetScene = useCallback(() => {
    setSlots([]);
    setPairFitness(null);
    setTurns([]);
    setDraft("");
    setActiveSlot("T1");
  }, []);

  const latestCompleted = [...turns].reverse().find((t) => t.role === "assistant" && t.status === "completed");
  const latestJobId = latestCompleted && latestCompleted.role === "assistant" ? latestCompleted.jobId : null;
  const latestAnswer = latestCompleted && latestCompleted.role === "assistant" ? (latestCompleted.answer ?? null) : null;
  const inspectJson = latestCompleted ? JSON.stringify(latestCompleted, null, 2) : null;

  const copyJobId = useCallback(() => {
    if (!latestJobId) {
      toast("No job yet", "bad");
      return;
    }
    void copyText(latestJobId).then(() => toast("Copied job id"));
  }, [latestJobId, toast]);

  const copyAnswer = useCallback(() => {
    if (!latestAnswer) {
      toast("No answer yet", "bad");
      return;
    }
    void copyText(latestAnswer).then(() => toast("Copied answer"));
  }, [latestAnswer, toast]);

  const restoreJob = useCallback(
    (id: string) => {
      const job = jobs.find((j) => j.id === id);
      if (!job) return;
      applySlots(job.slots);
      setPairFitness(job.pairFitness);
      setTurns(job.turns);
      setActiveSlot("T1");
      setJobsOpen(false);
    },
    [applySlots, jobs],
  );

  const onDragEnter = useCallback(() => {
    dragCount.current += 1;
    setDragging(true);
  }, []);

  const onDragLeave = useCallback(() => {
    dragCount.current = Math.max(0, dragCount.current - 1);
    if (dragCount.current === 0) setDragging(false);
  }, []);

  const onDrop = useCallback(
    (files: File[]) => {
      dragCount.current = 0;
      setDragging(false);
      attachFiles(files);
    },
    [attachFiles],
  );

  const value = useMemo<ConsoleContextValue>(
    () => ({
      slots,
      pairFitness,
      turns,
      draft,
      layers,
      jobs,
      jobsOpen,
      sceneSheetOpen,
      paletteOpen,
      helpOpen,
      inspectOpen,
      dragging,
      sending,
      hasScene: slots.length > 0,
      hasSar: slots.some((s) => s.modality === "SAR"),
      hasOptical: slots.some((s) => s.modality === "OPTICAL"),
      apiUp,
      toasts,
      latestJobId,
      latestAnswer,
      inspectJson,
      setDraft,
      insertChip,
      loadDemo,
      attachFiles,
      removeSlot,
      toggleSlotModality,
      setLayer,
      toggleLayer,
      send,
      openJobs: () => setJobsOpen(true),
      closeJobs: () => setJobsOpen(false),
      restoreJob,
      setSceneSheetOpen,
      setPaletteOpen,
      setHelpOpen,
      setInspectOpen,
      openFilePicker: () => fileInputRef.current?.click(),
      clearThread,
      resetScene,
      toast,
      copyJobId,
      copyAnswer,
      closeOverlays,
      onDragEnter,
      onDragLeave,
      onDrop,
      composerRef,
      fileInputRef,
      evidencePulse,
      setEvidencePulse,
      answerFocus,
      setAnswerFocus,
      activeSlot,
      setActiveSlot,
    }),
    [
      apiUp,
      attachFiles,
      clearThread,
      closeOverlays,
      copyAnswer,
      copyJobId,
      dragging,
      draft,
      evidencePulse,
      answerFocus,
      activeSlot,
      helpOpen,
      insertChip,
      inspectJson,
      inspectOpen,
      jobs,
      jobsOpen,
      latestAnswer,
      latestJobId,
      layers,
      loadDemo,
      onDragEnter,
      onDragLeave,
      onDrop,
      pairFitness,
      paletteOpen,
      removeSlot,
      toggleSlotModality,
      resetScene,
      restoreJob,
      sceneSheetOpen,
      send,
      sending,
      setLayer,
      slots,
      toast,
      toasts,
      toggleLayer,
      turns,
    ],
  );

  return (
    <ConsoleContext.Provider value={value}>
      {children}
      <input
        ref={fileInputRef}
        type="file"
        accept=".tif,.tiff,image/tiff"
        multiple
        className="hidden"
        onChange={(e) => {
          const list = e.target.files;
          if (list?.length) attachFiles(Array.from(list));
          e.target.value = "";
        }}
      />
    </ConsoleContext.Provider>
  );
}

export function useConsole() {
  const ctx = useContext(ConsoleContext);
  if (!ctx) throw new Error("useConsole must be used within ConsoleProvider");
  return ctx;
}
