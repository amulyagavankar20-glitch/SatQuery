import { useState } from "react";
import { cn } from "@/lib/utils";

export function StillEarth() {
  const [isLoaded, setIsLoaded] = useState(false);

  return (
    <div className="sq-earth pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden>
      <div className="sq-earth-limb" />
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
          isLoaded ? "opacity-[0.78] sm:opacity-[0.88] lg:opacity-[0.96]" : "opacity-0",
        )}
      />
    </div>
  );
}
