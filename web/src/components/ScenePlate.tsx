import { useState } from "react";
import { cn } from "@/lib/utils";

export function ScenePlate() {
  const [isLoaded, setIsLoaded] = useState(false);

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      {/* Atmospheric ambient glow buffer */}
      <div className="sq-plate-bloom transition-opacity duration-500" />
      <img
        src="/about-plate.jpg"
        alt=""
        loading="eager"
        decoding="async"
        // @ts-expect-error - fetchPriority supported in modern browsers
        fetchpriority="high"
        onLoad={() => setIsLoaded(true)}
        className={cn(
          "sq-plate-img absolute top-1/2 right-0 h-[min(130vh,980px)] w-[min(78vw,980px)] -translate-y-1/2 object-cover transition-opacity duration-700 ease-out",
          isLoaded ? "opacity-[0.28] sm:opacity-[0.36] lg:opacity-[0.42]" : "opacity-0",
        )}
      />
    </div>
  );
}