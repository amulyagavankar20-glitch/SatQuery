import { Link } from "@tanstack/react-router";
import { Map, Upload } from "lucide-react";

import { DEMOS } from "@/lib/demos";
import { useConsole } from "@/state/console";

export function EmptyState() {
  const { loadDemo, openFilePicker } = useConsole();

  return (
    <div className="mx-auto flex h-full w-full max-w-4xl flex-col px-6 py-8">
      <p className="text-[17px] leading-relaxed text-ink">Attach a GeoTIFF — or load a demo scene.</p>
      <p className="mt-2 text-[13px] text-mute">
        Official questions sit in the composer.{" "}
        <Link to="/explore" className="text-primary inline-flex items-center gap-1 hover:underline">
          <Map className="size-3.5" />
          Explore on the map
        </Link>
      </p>

      <div className="mt-8 grid gap-3 sm:grid-cols-3">
        {DEMOS.map((demo, i) => (
          <button
            key={demo.id}
            type="button"
            onClick={() => loadDemo(demo.id)}
            aria-label={`Load demo: ${demo.title}`}
            className="sq-enter group overflow-hidden rounded-xl border border-hairline bg-surface text-left hover:border-primary/50"
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <div className="overflow-hidden">
              <img
                src={demo.thumb}
                alt=""
                className="h-32 w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
              />
            </div>
            <div className="p-3">
              <div className="text-[13px] font-medium text-ink">{demo.title}</div>
              <div className="mt-1 text-[12px] leading-snug text-mute">{demo.blurb}</div>
            </div>
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={openFilePicker}
        className="mt-6 flex min-h-[160px] flex-1 flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-hairline bg-surface/40 text-[14px] text-mute hover:border-primary/40 hover:text-ink"
      >
        <Upload className="size-5" />
        Drop a GeoTIFF here
      </button>
    </div>
  );
}
