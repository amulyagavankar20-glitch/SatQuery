import { cn } from "@/lib/cn";
import { pipelineFromJob } from "@/lib/pipeline";
import type { JobView } from "@/lib/schema";

export function PipelineStrip({ job }: { job: JobView | null }) {
  const steps = pipelineFromJob(job);
  return (
    <ol className="hidden items-center gap-0 xl:flex" aria-label="Analysis pipeline">
      {steps.map((step, i) => (
        <li key={step.id} className="flex items-center">
          {i > 0 ? (
            <span
              className={cn(
                "mx-1 h-px w-3",
                step.status === "wait" ? "bg-white/10" : "bg-cyan/50",
              )}
            />
          ) : null}
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 font-mono text-[9px] tracking-[0.16em] uppercase transition",
              step.status === "done" && "border-ok/40 bg-ok/15 text-ok",
              step.status === "live" && "border-cyan/50 bg-cyan/15 text-cyan shadow-[0_0_12px_rgba(74,212,212,0.35)]",
              step.status === "fail" && "border-bad/50 bg-bad/15 text-bad",
              step.status === "wait" && "border-white/10 text-muted/70",
            )}
          >
            {step.label}
          </span>
        </li>
      ))}
    </ol>
  );
}
