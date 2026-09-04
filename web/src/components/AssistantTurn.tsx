import { Braces, Copy, FileText, Hexagon, MapPinned } from "lucide-react";
import { lazy, Suspense, type ReactNode } from "react";

import { ThinkingStream } from "@/components/ThinkingStream";
import { TraceAccordion } from "@/components/TraceAccordion";
import { downloadExport } from "@/lib/api";
import { downloadGeoJSON, downloadKml, downloadReportPdf } from "@/lib/exports";
import { followUpQuestions, thinkingSteps } from "@/lib/thinking";
import type { AssistantTurn as AssistantTurnModel, LayerId } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";

const MapEvidence = lazy(() => import("@/components/MapEvidence").then((m) => ({ default: m.MapEvidence })));

export function AssistantTurn({
  turn,
  query,
  layers,
  onLayer,
  hasSar,
}: {
  turn: AssistantTurnModel;
  query: string;
  layers: Record<LayerId, boolean>;
  onLayer: (id: LayerId, on: boolean) => void;
  hasSar: boolean;
}) {
  const { copyJobId, copyAnswer, setInspectOpen, apiUp, toast, slots, insertChip } = useConsole();

  if (turn.status === "pending") {
    return (
      <div>
        <ThinkingStream steps={thinkingSteps(query, slots.length > 1, hasSar)} />
        <div className="sq-shimmer mt-5 h-[440px] rounded-xl border border-hairline bg-surface" />
      </div>
    );
  }

  if (turn.status === "failed") {
    return (
      <div>
        <p className="text-[15px] leading-relaxed text-destructive">{turn.error ?? "The run did not complete."}</p>
      </div>
    );
  }

  const exportVector = async (format: "geojson" | "kml") => {
    if (apiUp && turn.jobId) {
      try {
        await downloadExport(turn.jobId, format);
        return;
      } catch {
        /* fall through to local */
      }
    }
    if (!turn.overlays) {
      toast("Nothing to export", "bad");
      return;
    }
    if (format === "geojson") downloadGeoJSON(turn.jobId, turn.overlays);
    else downloadKml(turn.jobId, turn.overlays);
  };

  return (
    <div>
      {turn.answer ? <p className="max-w-3xl text-[15px] leading-7 text-ink">{turn.answer}</p> : null}
      {turn.confidence ? (
        <p className="mt-3 text-[12px] text-mute">
          {turn.confidence} confidence{slots.length > 1 ? " · pair" : ""}
        </p>
      ) : null}

      <Suspense fallback={<div className="sq-shimmer mt-4 h-[440px] rounded-xl border border-hairline bg-surface" />}>
        <MapEvidence
          bounds={turn.bounds}
          opticalUrl={turn.opticalUrl}
          sarUrl={turn.sarUrl}
          compareUrl={turn.compareUrl}
          overlays={turn.overlays}
          layers={layers}
          onLayer={onLayer}
          hasSar={hasSar}
          instanceId={turn.id}
        />
      </Suspense>

      {turn.trace?.length ? <TraceAccordion steps={turn.trace} /> : null}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-[13px]">
        <ExportButton
          icon={<FileText className="size-3.5" />}
          onClick={() => turn.answer && downloadReportPdf(turn.jobId, query, turn.answer)}
          disabled={!turn.answer}
        >
          PDF
        </ExportButton>
        <ExportButton
          icon={<Hexagon className="size-3.5" />}
          onClick={() => void exportVector("geojson")}
          disabled={!turn.overlays && !apiUp}
        >
          GeoJSON
        </ExportButton>
        <ExportButton
          icon={<MapPinned className="size-3.5" />}
          onClick={() => void exportVector("kml")}
          disabled={!turn.overlays && !apiUp}
        >
          KML
        </ExportButton>
        <span className="text-hairline">·</span>
        <ExportButton icon={<Copy className="size-3.5" />} onClick={copyJobId}>
          Job id
        </ExportButton>
        <ExportButton icon={<Copy className="size-3.5" />} onClick={copyAnswer} disabled={!turn.answer}>
          Answer
        </ExportButton>
        <ExportButton icon={<Braces className="size-3.5" />} onClick={() => setInspectOpen(true)}>
          JSON
        </ExportButton>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {followUpQuestions(query).map((chip) => (
          <button
            key={chip}
            type="button"
            onClick={() => insertChip(chip)}
            className="rounded-lg border border-hairline px-2.5 py-1 text-[12px] text-mute hover:border-primary/40 hover:text-ink"
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}

function ExportButton({
  children,
  icon,
  onClick,
  disabled,
}: {
  children: string;
  icon: ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "text-mute hover:text-primary inline-flex items-center gap-1.5 disabled:pointer-events-none disabled:opacity-40",
      )}
    >
      {icon}
      {children}
    </button>
  );
}
