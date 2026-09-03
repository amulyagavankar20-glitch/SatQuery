import { useState } from "react";
import { Download, Globe2, Radio, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { bboxSpanKm } from "@/lib/format";
import { downloadExport } from "@/lib/api";
import type { JobView } from "@/lib/schema";

function confidenceClass(value: string | null | undefined) {
  const v = (value ?? "").toUpperCase();
  if (v === "HIGH") return "text-ok";
  if (v === "LOW") return "text-bad";
  if (v === "MEDIUM") return "text-gold";
  return "text-muted";
}

export function ResultCard({
  job,
  onInspect,
  onDismiss,
}: {
  job: JobView | null;
  onInspect: () => void;
  onDismiss: () => void;
}) {
  const [dismissed, setDismissed] = useState(false);

  // Only show for terminal states
  if (!job || !["completed", "failed", "refused"].includes(job.status)) return null;
  if (dismissed) return null;

  const answer = job.answer;
  const bounds = job.assets.find((a) => a.bounds_wgs84 && a.bounds_wgs84.length === 4)?.bounds_wgs84 ?? null;
  const span = bounds ? bboxSpanKm(bounds) : null;

  const handleDismiss = () => {
    setDismissed(true);
    onDismiss();
  };

  // Reset dismiss when job changes
  // This is handled by parent re-keying the component

  return (
    <div className="result-card-enter absolute bottom-4 right-4 z-20 w-[320px]">
      <div className="glass-strong overflow-hidden rounded-xl shadow-[0_20px_60px_rgba(0,0,0,0.5)]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/8 px-3.5 py-2">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                job.status === "completed" && "bg-ok shadow-[0_0_8px_#3dba7a]",
                job.status === "failed" && "bg-bad shadow-[0_0_8px_#e05b56]",
                job.status === "refused" && "bg-bad shadow-[0_0_8px_#e05b56]",
              )}
            />
            <span className="font-mono text-[10px] tracking-[0.16em] text-ink/80 uppercase">
              {job.status}
            </span>
            {answer?.confidence && (
              <span className={cn("font-mono text-[10px]", confidenceClass(answer.confidence))}>
                · {answer.confidence}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={handleDismiss}
            className="text-muted/60 transition hover:text-ink"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Body */}
        <div className="px-3.5 py-3">
          {/* Answer snippet */}
          <p className="line-clamp-3 text-[13px] leading-relaxed text-ink/85">
            {answer?.text ?? job.refusal_reason ?? "—"}
          </p>

          {/* AOI info */}
          {span && bounds && (
            <p className="mt-2 font-mono text-[9px] text-muted/60">
              AOI {span.w.toFixed(1)} × {span.h.toFixed(1)} km
            </p>
          )}

          {/* Model info */}
          {answer && (
            <p className="mt-1 font-mono text-[9px] text-muted/50">
              {answer.model} · {answer.backend === "mock" ? "mock" : answer.backend}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1.5 border-t border-white/5 px-3.5 py-2.5">
          <button
            type="button"
            disabled={!job.job_id}
            onClick={() => downloadExport(job.job_id, "geojson")}
            className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-white/8 bg-white/[0.03] py-1.5 font-mono text-[9px] tracking-[0.12em] text-ink/80 uppercase transition hover:border-saffron/40 hover:bg-saffron/5 disabled:opacity-30"
          >
            <Download className="h-3 w-3" /> GeoJSON
          </button>
          <button
            type="button"
            disabled={!job.job_id}
            onClick={() => downloadExport(job.job_id, "kml")}
            className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-white/8 bg-white/[0.03] py-1.5 font-mono text-[9px] tracking-[0.12em] text-ink/80 uppercase transition hover:border-saffron/40 hover:bg-saffron/5 disabled:opacity-30"
          >
            <Globe2 className="h-3 w-3" /> KML
          </button>
          <button
            type="button"
            disabled
            title="PDF not implemented (501)"
            className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-white/8 py-1.5 font-mono text-[9px] tracking-[0.12em] text-muted/40 uppercase opacity-40"
          >
            <Radio className="h-3 w-3" /> PDF
          </button>
        </div>

        {/* Inspect */}
        <button
          type="button"
          onClick={onInspect}
          className="w-full border-t border-white/5 py-1.5 font-mono text-[9px] tracking-[0.12em] text-muted/50 uppercase transition hover:bg-white/[0.02] hover:text-muted"
        >
          Inspect JobView
        </button>
      </div>
    </div>
  );
}
