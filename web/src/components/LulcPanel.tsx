import type { LulcReport } from "@/lib/types";
import { cn } from "@/lib/utils";

const ORDER = [
  "water",
  "flooded_vegetation",
  "trees",
  "grass",
  "crops",
  "shrub_and_scrub",
  "built",
  "bare",
  "snow_and_ice",
] as const;

function label(id: string) {
  return id.replaceAll("_", " ");
}

export function LulcPanel({ report }: { report: LulcReport }) {
  const rows = ORDER.map((id) => [id, report.fractions[id] ?? 0] as const).filter(([, v]) => v >= 0.03);
  const isFallback = !report.backend.startsWith("dynamic_world") && !report.backend.startsWith("prithvi");
  const backend = report.backend.startsWith("dynamic_world")
    ? "Dynamic World · 9-class pixels (Sentinel-2)"
    : report.backend.startsWith("prithvi")
      ? "Prithvi flood + land cover"
      : "Optical spectral fallback (coarse pixel-class estimate, not Dynamic World)";

  return (
    <div className="mt-3 max-w-3xl">
      <p className="font-mono text-[10px] tracking-wide text-mute">Land-Cover Classification · {backend}</p>
      <ul className="mt-2 flex flex-col gap-1">
        {rows.map(([id, v]) => (
          <li key={id} className="flex items-center gap-2">
            <span className="w-36 shrink-0 font-mono text-[11px] text-mute">{label(id)}</span>
            <span className="bg-hairline h-1.5 min-w-0 flex-1 overflow-hidden rounded-full">
              <span
                className={cn(
                  "block h-full rounded-full",
                  id === "water" || id === "flooded_vegetation" ? "bg-primary" : "bg-ink/35",
                )}
                style={{ width: `${Math.min(100, v * 100)}%` }}
              />
            </span>
            <span className="w-8 text-right font-mono text-[11px] tabular-nums text-mute">{Math.round(v * 100)}</span>
          </li>
        ))}
      </ul>
      {report.sceneTags.length ? (
        <div className="mt-3">
          <p className="font-mono text-[10px] tracking-wide text-mute">
            {isFallback ? "Estimated Class Labels · Coarse Taxonomy Mapping" : "Scene Tags · BigEarthNet-19"}
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {report.sceneTags.map((t) => (
              <span
                key={t.name}
                className="rounded-lg border border-hairline px-2 py-0.5 font-mono text-[11px] text-mute"
              >
                {t.name}
                <span className="ml-1.5 tabular-nums text-mute/70">{Math.round(t.score * 100)}</span>
              </span>
            ))}
          </div>
          <p className="mt-2 max-w-md text-[11px] leading-relaxed text-mute/80">
            {isFallback
              ? "Coarse estimates mapped from 9-class spectral heuristics. Not a trained BigEarthNet model or object detection."
              : "Derived from 9-class pixel fractions. Dynamic World is not trained directly on BigEarthNet."}
          </p>
        </div>
      ) : null}
    </div>
  );
}
