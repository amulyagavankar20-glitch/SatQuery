import { useEffect, useState } from "react";

import { routingSteps } from "@/lib/thinking";
import { cn } from "@/lib/utils";

export function RoutingLine({
  query,
  sar,
  className,
}: {
  query: string;
  sar: boolean;
  className?: string;
}) {
  const steps = routingSteps(query, sar);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    setIndex(0);
    const id = window.setInterval(() => setIndex((i) => Math.min(steps.length - 1, i + 1)), 900);
    return () => window.clearInterval(id);
  }, [query, sar, steps.length]);

  return (
    <div className={cn("flex flex-col gap-2 py-1", className)}>
      <div className="flex items-center gap-2 font-mono text-[11px] tracking-wide text-mute">
        <span className="relative flex size-2 items-center justify-center">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-60" />
          <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
        </span>
        <span className="text-ink/80">routing execution</span>
        <span className="text-mute/40">·</span>
        <span className="font-medium text-primary">[{steps[index]}]</span>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
        {steps.slice(0, index + 1).map((step, i) => {
          const isCurrent = i === index;
          return (
            <span key={step} className="inline-flex items-center gap-1.5">
              {i > 0 ? <span className="text-mute/40">→</span> : null}
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 transition-all duration-200",
                  isCurrent
                    ? "border border-primary/40 bg-primary/15 font-medium text-primary shadow-[0_0_8px_-2px_rgba(94,143,138,0.4)]"
                    : "border border-white/5 bg-surface/40 text-mute/80",
                )}
              >
                {step}
              </span>
            </span>
          );
        })}
      </div>

      <div className="sq-reasoning-buffer mt-1 h-1.5 w-full max-w-xs" />
    </div>
  );
}
