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
        <Link to="/explore" className="group text-primary inline-flex items-center gap-1.5 hover:underline transition-transform active:scale-95">
          <Map className="size-3.5 transition-transform duration-200 group-hover:rotate-12 group-hover:scale-110" />
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
            className="sq-glass sq-enter group overflow-hidden rounded-xl text-left transition-all duration-300 hover:-translate-y-1 hover:border-primary/50 hover:shadow-[0_8px_24px_-8px_rgba(94,143,138,0.25)] active:scale-[0.98]"
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <div className="aspect-[4/3] overflow-hidden">
              <DemoThumb demo={demo} className="h-full w-full transition-transform duration-300 group-hover:scale-[1.04]" />
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
