import { Check, Copy, Crosshair } from "lucide-react";
import { useState } from "react";
import { copyText, formatLngLat } from "@/lib/format";

export function FooterBar({
  cursor,
  zoom,
  jobId,
  routerModel,
  vlmBackend,
}: {
  cursor: { lng: number; lat: number } | null;
  zoom: number;
  jobId: string | null;
  routerModel: string;
  vlmBackend: string;
}) {
  const [copied, setCopied] = useState<string | null>(null);

  const flashCopy = async (label: string, value: string) => {
    await copyText(value);
    setCopied(label);
    window.setTimeout(() => setCopied(null), 1400);
  };

  return (
    <footer className="glass rise flex flex-wrap items-center justify-between gap-2 rounded-lg px-3 py-1.5 font-mono text-[10px] text-muted">
      <div className="flex flex-wrap items-center gap-3">
        <span><kbd>⌘K</kbd> palette</span>
        <span><kbd>⌘</kbd><kbd>↵</kbd> run</span>
        <span><kbd>F</kbd> fit</span>
        <span><kbd>?</kbd> keys</span>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="inline-flex items-center gap-1 tabular-nums text-ink/80 transition hover:text-saffron"
          disabled={!cursor}
          onClick={() =>
            cursor && void flashCopy("coords", `${cursor.lng.toFixed(6)}, ${cursor.lat.toFixed(6)}`)
          }
          title="Copy coordinates"
        >
          <Crosshair className="h-3 w-3" />
          {cursor ? formatLngLat(cursor.lng, cursor.lat) : "—"}
        </button>
        <span>z {zoom.toFixed(1)}</span>
        {jobId ? (
          <button
            type="button"
            onClick={() => void flashCopy("job id", jobId)}
            className="inline-flex items-center gap-1 text-ink/80 transition hover:text-saffron"
          >
            {copied === "job id" ? (
              <Check className="h-3 w-3 text-ok" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
            {copied === "job id" ? "copied" : jobId.slice(0, 8)}
          </button>
        ) : (
          <span>no job</span>
        )}
        <span className="hidden sm:inline">
          {routerModel} · {vlmBackend}
        </span>
      </div>
    </footer>
  );
}
