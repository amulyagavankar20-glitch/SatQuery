import { Link } from "@tanstack/react-router";
import { Map } from "lucide-react";

import { DemoThumb } from "@/components/DemoThumb";
import { DEMOS } from "@/lib/demos";
import { useConsole } from "@/state/console";

export function EmptyState() {
  const { loadDemo } = useConsole();

  return (
    <div className="mx-auto flex h-full w-full max-w-4xl flex-col px-6 py-8">
      <p className="sq-title text-[17px] leading-relaxed">Attach a GeoTIFF — or load a demo scene.</p>
      <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-mute">
        <span>Official questions sit in the composer.</span>
        <Link to="/explore" className="text-primary inline-flex items-center gap-1.5 hover:underline">
          <Map className="size-3.5" />
          Explore scenes
        </Link>
      </p>
      <div className="sq-gradient-divider mt-6" />

      <div className="mt-8 grid gap-3 sm:grid-cols-3">
        {DEMOS.map((demo, i) => (
          <button
            key={demo.id}
            type="button"
            onClick={() => loadDemo(demo.id)}
            aria-label={`Load demo: ${demo.title}`}
            className="sq-glass group overflow-hidden rounded-xl text-left"
          >
            <div className="aspect-[4/3] overflow-hidden">
              <DemoThumb demo={demo} className="h-full w-full" />
            </div>
            <div className="p-3">
              <div className="font-mono text-[11px] tracking-wide text-mute transition-colors duration-150 group-hover:text-primary">
                {String(i + 1).padStart(2, "0")} // {demo.title}
              </div>
              <div className="mt-1 text-[12px] leading-snug text-mute">{demo.blurb}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
