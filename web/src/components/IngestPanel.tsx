import { useState, type RefObject } from "react";
import { ChevronDown, ChevronUp, Upload, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { SENSORS } from "@/lib/chips";
import { formatBytes } from "@/lib/format";
import type { IngestResponse } from "@/lib/schema";

function sceneTag(index: number, total: number) {
  if (total < 2) return "SCN";
  return index === 0 ? "T1" : "T2";
}

export function IngestPanel({
  files,
  sensor,
  ingestMeta,
  ingestNote,
  isPending,
  isError,
  errorMessage,
  inputRef,
  onFilesChange,
  onSensorChange,
  onIngest,
}: {
  files: File[];
  sensor: string;
  ingestMeta: IngestResponse | null;
  ingestNote: string | null;
  isPending: boolean;
  isError: boolean;
  errorMessage: string;
  inputRef: RefObject<HTMLInputElement | null>;
  onFilesChange: (files: File[]) => void;
  onSensorChange: (sensor: string) => void;
  onIngest: () => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const [dragging, setDragging] = useState(false);

  const hasIngest = Boolean(ingestMeta);
  const ingestAssets = ingestMeta?.assets ?? [];

  // Auto-collapse after successful ingest
  const isCollapsible = hasIngest;

  const takeFiles = (list: File[]) => {
    const dropped = list.filter((f) => /\.tiff?$/i.test(f.name));
    if (dropped.length) onFilesChange(dropped.slice(0, 2));
  };

  return (
    <section className="glass rise overflow-hidden rounded-xl" style={{ animationDelay: "40ms" }}>
      {/* Header — clickable to toggle */}
      <button
        type="button"
        onClick={() => isCollapsible && setExpanded((v) => !v)}
        className={cn(
          "flex w-full items-center justify-between border-b border-white/8 px-4 py-2.5 text-left",
          isCollapsible && "cursor-pointer hover:bg-white/[0.02]",
        )}
      >
        <div className="flex items-center gap-2">
          <Upload className="h-3.5 w-3.5 text-saffron" />
          <span className="font-mono text-[11px] font-medium tracking-[0.2em] text-ink/90 uppercase">
            Ingest
          </span>
          {ingestNote && (
            <span className="rounded-md bg-cyan/10 px-2 py-0.5 font-mono text-[10px] text-cyan">
              {ingestNote}
            </span>
          )}
        </div>
        {isCollapsible && (
          <span className="text-muted">
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </span>
        )}
      </button>

      {/* Collapsible body */}
      <div
        className={cn(
          "transition-all duration-300 ease-out overflow-hidden",
          expanded ? "max-h-[600px] opacity-100" : "max-h-0 opacity-0",
        )}
      >
        <div className="p-3.5">
          {/* Drop zone */}
          <div
            className={cn(
              "group flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-3 py-4 text-center transition-all duration-300 active:scale-[0.99]",
              dragging
                ? "scale-[1.01] border-saffron bg-saffron/8 shadow-[0_0_30px_rgba(240,132,42,0.1)]"
                : "border-white/12 bg-white/[0.03] hover:border-saffron/50 hover:bg-saffron/5",
            )}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              takeFiles(Array.from(e.dataTransfer.files));
            }}
          >
            <span className="mb-1.5 grid h-9 w-9 place-items-center rounded-full bg-saffron/10 text-saffron ring-1 ring-saffron/25 transition duration-300 group-hover:scale-105">
              <Upload className="h-3.5 w-3.5" />
            </span>
            <p className="text-[13px] text-ink/90">Drop GeoTIFF</p>
            <p className="mt-0.5 font-mono text-[10px] text-muted/80">Cartosat · RISAT · Sentinel · ⌘O</p>
            <input
              ref={inputRef}
              type="file"
              accept=".tif,.tiff"
              multiple
              className="hidden"
              onChange={(e) => takeFiles(e.target.files ? Array.from(e.target.files) : [])}
            />
          </div>

          {/* File list */}
          {files.length > 0 && (
            <ul className="mt-2.5 space-y-1">
              {files.map((file, i) => (
                <li
                  key={`${file.name}-${i}`}
                  className="flex items-center gap-2 rounded-lg bg-black/20 px-2.5 py-1.5 font-mono text-[10px]"
                >
                  <span className="rounded bg-saffron/15 px-1.5 py-0.5 text-saffron">{sceneTag(i, files.length)}</span>
                  <span className="min-w-0 flex-1 truncate text-ink/90">{file.name}</span>
                  <span className="text-muted/80">{formatBytes(file.size)}</span>
                  <button
                    type="button"
                    className="text-muted transition hover:text-bad"
                    onClick={(e) => {
                      e.stopPropagation();
                      onFilesChange(files.filter((_, j) => j !== i));
                    }}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </li>
              ))}
            </ul>
          )}

          {/* Ingest asset info */}
          {ingestAssets.length > 0 && (
            <ul className="mt-2 space-y-1 border-t border-white/5 pt-2">
              {ingestAssets.map((asset, i) => (
                <li key={`${asset.filename}-${i}`} className="font-mono text-[10px] text-muted">
                  <span className="text-cyan">{asset.modality ?? "—"}</span>
                  {asset.width && asset.height ? ` · ${asset.width}×${asset.height}` : ""}
                  {asset.crs ? ` · ${asset.crs}` : ""}
                </li>
              ))}
            </ul>
          )}

          {/* Sensor select */}
          <label className="mt-3 block font-mono text-[10px] tracking-[0.14em] text-muted/80 uppercase">Sensor</label>
          <select
            value={sensor}
            onChange={(e) => onSensorChange(e.target.value)}
            className="mt-1 w-full rounded-lg border border-white/8 bg-black/25 px-3 py-2 font-mono text-xs text-ink outline-none transition focus:border-saffron/50"
          >
            {SENSORS.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>

          {/* Ingest button */}
          <button
            type="button"
            disabled={!files.length || isPending}
            onClick={onIngest}
            className="btn-shine mt-3 w-full rounded-lg bg-gradient-to-r from-saffron to-[#ffb056] px-3 py-2 font-mono text-[11px] font-semibold tracking-[0.16em] text-navy uppercase shadow-[0_6px_20px_rgba(240,132,42,0.2)] transition hover:brightness-110 active:scale-[0.98] disabled:opacity-40 disabled:shadow-none"
          >
            {isPending ? "Classifying…" : "Ingest"}
          </button>

          {isError && (
            <p className="mt-2 font-mono text-[11px] text-bad">{errorMessage}</p>
          )}
        </div>
      </div>
    </section>
  );
}
