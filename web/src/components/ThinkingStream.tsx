import { Check } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

export function ThinkingStream({ steps }: { steps: string[] }) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    setIndex(0);
    const id = window.setInterval(() => {
      setIndex((i) => Math.min(steps.length - 1, i + 1));
    }, 700);
    return () => window.clearInterval(id);
  }, [steps]);

  return (
    <ol className="flex flex-col gap-2.5">
      {steps.map((step, i) => {
        if (i > index) return null;
        const live = i === index;
        return (
          <li
            key={step}
            className={cn("sq-enter flex items-center gap-2.5 text-[14px]", live ? "text-ink" : "text-mute")}
          >
            {live ? (
              <span className="sq-orbit shrink-0" />
            ) : (
              <Check className="size-3.5 shrink-0 text-primary" strokeWidth={2.2} />
            )}
            {step}
          </li>
        );
      })}
    </ol>
  );
}
