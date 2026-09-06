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
      <p className="mt-2 text-[13px] text-mute">
        Official questions sit in the composer.{" "}
        <Link to="/explore" className="text-primary inline-flex items-center gap-1 hover:underline">
          <Map className="size-3.5" />
          Explore scenes
        </Link>
      </p>

      <div className="mt-8 grid gap-3 sm:grid-cols-3">
        {DEMOS.map((demo, i) => (
          <button
            key={demo.id}
            type="button"
            onClick={() => loadDemo(demo.id)}
            aria-label={`Load demo: ${demo.title}`}
            className="sq-glass sq-enter group overflow-hidden rounded-xl text-left hover:border-primary/50"
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <div className="aspect-[4/3] overflow-hidden">
              <DemoThumb demo={demo} className="h-full w-full transition-transform duration-300 group-hover:scale-[1.03]" />
            </div>
            <div className="p-3">
              <div className="font-mono text-[11px] tracking-wide text-mute">
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
