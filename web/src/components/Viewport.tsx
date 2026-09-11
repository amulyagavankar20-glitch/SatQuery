import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from "react";

import { Kbd } from "@/components/Kbd";
import { downloadExport } from "@/lib/api";
import { LAYER_LABELS } from "@/lib/constants";
import { downloadGeoJSON, downloadSceneRasters } from "@/lib/exports";
import { fitLatestMap } from "@/lib/map-registry";
import type { AssistantTurn, BBox, LayerId } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";

const DEFAULT_BOUNDS: BBox = [72.5, 23.0, 72.7, 23.2];

const MapEvidence = lazy(() => import("@/components/MapEvidence").then((m) => ({ default: m.MapEvidence })));

const LAYER_GROUPS: { title: string; ids: LayerId[] }[] = [
  { title: "Base", ids: ["optical", "sar"] },
  { title: "Overlays", ids: ["change"] },
  { title: "Confidence", ids: ["uncertain"] },
];

export function Viewport() {
  const {
    hasScene,
    hasSar,
    slots,
    turns,
    layers,
    setLayer,
    openFilePicker,
    apiUp,
    toast,
    activeSlot,
  } = useConsole();

  const latest = [...turns].reverse().find((t): t is AssistantTurn => t.role === "assistant");
  const completed = latest?.status === "completed" ? latest : null;
  const t1 = slots.find((s) => s.slot === "T1") ?? slots[0];
  const t2 = slots.find((s) => s.slot === "T2");
  const pair = Boolean(t2);
  const base = (activeSlot === "T2" && t2) || t1;
  const [wipe, setWipe] = useState(false);
  const [sarMode, setSarMode] = useState<"composite" | "vv" | "vh" | "overlay">("composite");
  const [panel, setPanel] = useState<null | "layers" | "export">(null);
  const chromeRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!pair) setWipe(false);
  }, [pair]);

  useEffect(() => {
    if (!panel) return;
    const onDoc = (e: MouseEvent) => {
      if (chromeRef.current && !chromeRef.current.contains(e.target as Node)) setPanel(null);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [panel]);

  if (!hasScene || !t1) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <button
          type="button"
          onClick={openFilePicker}
          className="flex max-w-sm flex-col items-center gap-3 rounded-xl border border-dashed border-hairline px-8 py-10 text-center text-[13px] text-mute hover:border-primary/40 hover:text-ink"
        >
          Drop single GeoTIFF or temporal pair (T1, T2)
        </button>
      </div>
    );
  }

  // If T2 tab selected but no T2 image is loaded yet
  if (activeSlot === "T2" && !t2) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <div className="sq-glass flex max-w-md flex-col items-center gap-3 rounded-2xl border border-white/10 p-8 shadow-2xl backdrop-blur-xl bg-surface/60">
          <div className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary border border-primary/20">
            <span className="font-mono font-bold text-base">T2</span>
          </div>
          <h3 className="font-mono text-base font-semibold text-ink">T2 Not Loaded</h3>
          <p className="text-[13px] text-mute leading-relaxed">
            Upload or attach a second GeoTIFF image to establish a temporal pair and enable bi-temporal change detection analysis.
          </p>
          <button
            type="button"
            onClick={openFilePicker}
            className="mt-2 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-mono text-[12px] font-semibold text-black transition-all hover:bg-primary/90 shadow-md active:scale-95"
          >
            Upload T2 Image
          </button>
        </div>
      </div>
    );
  }

  const opticalUrl =
    base.modality === "OPTICAL"
      ? (base.previewUrl || latest?.opticalUrl || null)
      : (layers.optical ? (base.previewUrl || latest?.opticalUrl || slots.find((s) => s.modality === "OPTICAL")?.previewUrl || null) : null);

  let sarUrl =
    base.modality === "SAR"
      ? (base.previewUrl || (latest?.sarUrl ?? null))
      : (layers.sar && hasSar ? (slots.find((s) => s.modality === "SAR")?.previewUrl ?? latest?.sarUrl ?? null) : null);

  if (hasSar && latest && base.modality === "SAR") {
    if (sarMode === "vv" && latest.vvUrl) sarUrl = latest.vvUrl;
    else if (sarMode === "vh" && latest.vhUrl) sarUrl = latest.vhUrl;
    else if (sarMode === "overlay" && latest.overlayUrl) sarUrl = latest.overlayUrl;
    else if (sarMode === "composite" && latest.sarUrl) sarUrl = latest.sarUrl;
  }

  const wipeUrl = wipe && t2 ? t2.previewUrl : null;

  const exportGeoJSON = async () => {
    if (!completed?.overlays) {
      toast("Nothing to export", "bad");
      return;
    }
    if (apiUp && completed.jobId) {
      try {
        await downloadExport(completed.jobId, "geojson");
        return;
      } catch {
        /* local */
      }
    }
    downloadGeoJSON(completed.jobId, completed.overlays);
  };

  const exportGeoTIFF = () => {
    if (downloadSceneRasters(slots)) return;
    toast("Upload a GeoTIFF to export the raster", "bad");
  };

  const sceneBounds = base.bounds ?? completed?.bounds ?? DEFAULT_BOUNDS;

  return (
    <div className="relative h-full min-h-0">
      <Suspense fallback={<ViewportLoader />}>
        <MapEvidence
          bounds={sceneBounds}
          opticalUrl={opticalUrl}
          sarUrl={sarUrl}
          wipeUrl={wipeUrl}
          overlays={completed?.overlays}
          layers={layers}
          hasSar={hasSar}
          t1Date={t1?.date}
          t2Date={t2?.date}
          fill
        />
      </Suspense>

      {hasSar && completed?.jobId ? (
        <div className="absolute top-3 left-3 z-20">
          <div className="sq-glass flex items-center gap-0.5 rounded-lg p-1 border border-white/10 bg-surface/85 shadow-lg backdrop-blur-md">
            {(
              [
                { id: "composite", label: "Composite" },
                { id: "vv", label: "VV Amplitude" },
                { id: "vh", label: "VH Amplitude" },
                { id: "overlay", label: "Overlay Detections" },
              ] as const
            ).map((mode) => (
              <button
                key={mode.id}
                type="button"
                onClick={() => setSarMode(mode.id)}
                className={cn(
                  "rounded-md px-2 py-1 font-mono text-[10.5px] font-medium transition-all",
                  sarMode === mode.id
                    ? "bg-primary text-black font-semibold shadow"
                    : "text-mute hover:text-ink hover:bg-white/5",
                )}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div ref={chromeRef} className="absolute top-3 right-3 z-20 w-max max-w-[calc(100%-1.25rem)]">
        <div className="sq-glass flex flex-wrap justify-end rounded-lg px-0.5 py-1">
          <ChromeButton onClick={() => fitLatestMap()}>
            Fit
            <Kbd className="ml-1">F</Kbd>
          </ChromeButton>
          <ChromeButton
            on={panel === "layers"}
            onClick={() => setPanel((p) => (p === "layers" ? null : "layers"))}
          >
            Layers
          </ChromeButton>
          {pair ? (
            <ChromeButton
              on={wipe}
              onClick={() => {
                setWipe((w) => !w);
                setPanel(null);
              }}
            >
              <span className="hidden sm:inline">T1/T2 </span>Wipe
            </ChromeButton>
          ) : null}
          <ChromeButton
            on={panel === "export"}
            onClick={() => setPanel((p) => (p === "export" ? null : "export"))}
          >
            Export
          </ChromeButton>
        </div>

        {panel === "layers" ? (
          <div className="sq-glass sq-palette mt-2 min-w-[11rem] rounded-lg p-3">
            {LAYER_GROUPS.map((group) => (
              <div key={group.title} className="mb-3 last:mb-0">
                <p className="font-mono text-[10px] tracking-wide text-mute uppercase">{group.title}</p>
                <ul className="mt-1.5 flex flex-col gap-1">
                  {group.ids.map((id) => {
                    const layer = LAYER_LABELS.find((l) => l.id === id);
                    if (!layer) return null;
                    const hasOptical = slots.some((s) => s.modality === "OPTICAL");
                    const hasSarSlot = slots.some((s) => s.modality === "SAR");
                    const isSarActive = base.modality === "SAR";

                    let disabled = false;
                    let on = false;

                    if (id === "optical") {
                      disabled = !hasOptical;
                      on = layers.optical && !disabled && (!isSarActive || hasOptical);
                    } else if (id === "sar") {
                      disabled = !hasSarSlot && !hasSar;
                      on = layers.sar && !disabled && (isSarActive || hasSarSlot);
                    } else {
                      on = layers[id];
                    }

                    return (
                      <li key={id}>
                        <button
                          type="button"
                          disabled={disabled}
                          aria-pressed={on}
                          onClick={() => setLayer(id, !layers[id])}
                          className={cn(
                            "flex w-full items-center justify-between rounded-md px-1.5 py-1 font-mono text-[11px] transition-colors duration-150 disabled:opacity-40",
                            on ? "text-primary bg-primary/10" : "text-mute hover:text-ink hover:bg-white/[0.04]",
                          )}
                        >
                          {layer.label}
                          <span className={cn("size-1.5 rounded-full transition-all duration-200", on ? "bg-primary shadow-[0_0_6px_rgba(94,143,138,0.7)] scale-110" : "bg-hairline")} />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        ) : null}

        {panel === "export" ? (
          <div className="sq-glass sq-palette mt-2 min-w-[10rem] rounded-lg p-2">
            <button
              type="button"
              className="flex w-full rounded-md px-2 py-1.5 text-left font-mono text-[11px] text-mute hover:text-primary hover:bg-white/[0.04] transition-colors duration-150 active:scale-[0.98]"
              onClick={() => {
                void exportGeoJSON();
                setPanel(null);
              }}
            >
              GeoJSON
            </button>
            <button
              type="button"
              className="flex w-full rounded-md px-2 py-1.5 text-left font-mono text-[11px] text-mute hover:text-primary hover:bg-white/[0.04] transition-colors duration-150 active:scale-[0.98]"
              onClick={() => {
                exportGeoTIFF();
                setPanel(null);
              }}
            >
              GeoTIFF
            </button>
          </div>
        ) : null}
      </div>

    </div>
  );
}

function ChromeButton({
  children,
  on,
  onClick,
}: {
  children: ReactNode;
  on?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center rounded-md px-2 py-1 font-mono text-[11px] tracking-wide transition-all duration-150 active:scale-95",
        on ? "bg-primary/15 text-primary shadow-sm font-medium" : "text-mute hover:text-ink hover:bg-white/[0.04]",
      )}
    >
      {children}
    </button>
  );
}

function ViewportLoader() {
  return (
    <div className="sq-viewport-loader relative flex h-full w-full flex-col items-center justify-center overflow-hidden">
      {/* Subtle reticle crosshair */}
      <div className="pointer-events-none relative flex size-16 items-center justify-center">
        <div className="absolute size-12 rounded-full border border-primary/20 animate-pulse" />
        <div className="size-2 rounded-full bg-primary/70" />
        <div className="absolute h-14 w-px bg-primary/25" />
        <div className="absolute w-14 h-px bg-primary/25" />
      </div>
      <div className="mt-4 flex items-center gap-2 font-mono text-[10.5px] tracking-wider text-mute/80 uppercase">
        <span className="size-1 rounded-full bg-primary animate-ping" />
        <span>INITIALIZING GEOSPATIAL VIEWPORT…</span>
      </div>
    </div>
  );
}
