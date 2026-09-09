import { useState } from "react";
import { cn } from "@/lib/utils";

export function StillEarth() {
  const [isLoaded, setIsLoaded] = useState(false);

  return (
    <div className="sq-earth pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden>
      {/* Subtle circular atmospheric glow behind the earth */}
      <div
        className="pointer-events-none absolute top-1/2 right-0 aspect-square h-[min(92vh,760px)] -translate-y-1/2 opacity-35 blur-xl lg:h-[min(98vh,880px)]"
        style={{
          background: "radial-gradient(circle at 60% 48%, rgb(94 143 138 / 0.16) 0%, rgb(94 143 138 / 0.04) 34%, transparent 48%)",
        }}
      />
      <img
        src="/earth.jpg"
        alt=""
        width={1024}
        height={1024}
        loading="eager"
        decoding="async"
        // @ts-expect-error - fetchPriority supported in modern browsers
        fetchpriority="high"
        draggable={false}
        onLoad={() => setIsLoaded(true)}
        className={cn(
          "sq-earth-img absolute top-1/2 right-0 h-[min(92vh,760px)] w-auto max-w-none -translate-y-1/2 object-contain transition-opacity duration-700 ease-out",
          isLoaded ? "opacity-[0.72] sm:opacity-[0.84] lg:opacity-[0.94]" : "opacity-0",
        )}
      />
    </div>
  );
}
