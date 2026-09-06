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
    <p className={cn("sq-pending font-mono text-[12px] tracking-wide text-mute", className)}>
      {steps.slice(0, index + 1).map((step, i) => (
        <span key={step}>
          {i > 0 ? " → " : null}
          <span className={i === index ? "text-primary" : undefined}>[{step}]</span>
        </span>
      ))}
    </p>
  );
}
