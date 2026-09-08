import { Upload, X } from "lucide-react";
import { useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";
import type { SceneSlot } from "@/lib/types";

function SlotCard({
  label,
  hint,
  slot,
  onRemove,
  onPreview,
}: {
  label: string;
  hint: string;
  slot: SceneSlot | undefined;
  onRemove: () => void;
  onPreview: (url: string) => void;
}) {
  if (!slot) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-dashed border-hairline px-3 py-3 transition-all duration-200 hover:border-primary/30 hover:bg-white/[0.02]">
        <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-background text-mute">
          <Upload className="size-4" />
        </div>
        <div className="min-w-0">
          <div className="text-[12px] font-medium text-mute">{label}</div>
          <div className="mt-0.5 text-[12px] text-mute/80">{hint}</div>
        </div>
      </div>
    );
  }

  return (
      <div className="sq-glass-card rounded-xl p-3">
      <div className="flex items-start gap-2.5">
        {slot.previewUrl ? (
          <button type="button" onClick={() => onPreview(slot.previewUrl)} className="shrink-0">
            <img
              src={slot.previewUrl}
              alt=""
              className="size-10 rounded-lg object-cover"
              style={slot.objectPos ? { objectPosition: slot.objectPos } : undefined}
            />
          </button>
        ) : (
          <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-background font-mono text-[10px] text-mute">
            {slot.slot}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="text-[11px] tracking-wide text-mute uppercase">{label}</div>
          <div className="mt-0.5 truncate text-[13px] text-ink" title={slot.filename}>
            {slot.filename}
          </div>
        </div>
        <button
          type="button"
          onClick={onRemove}
          className="text-mute hover:text-ink rounded-lg p-1"
          aria-label={`Remove ${label}`}
        >
          <X className="size-3.5" />
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <Chip>{slot.crs}</Chip>
        {slot.date ? <Chip>{slot.date}</Chip> : null}
        {slot.bands != null ? <Chip>{slot.bands} bands</Chip> : null}
        <Chip tone={slot.modality === "SAR" ? "sar" : "optical"}>{slot.modality === "SAR" ? "SAR" : "Optical"}</Chip>
        {slot.sensor ? <Chip>{slot.sensor}</Chip> : null}
      </div>
    </div>
  );
}

function Chip({ children, tone }: { children: ReactNode; tone?: "sar" | "optical" }) {
  return (
    <span
      className={cn(
        "font-mono rounded-md px-1.5 py-0.5 text-[10px] tracking-wide uppercase",
        tone === "sar" && "border border-primary/45 text-primary",
        tone === "optical" && "border border-hairline text-mute",
        !tone && "bg-background text-mute",
      )}
    >
      {children}
    </span>
  );
}

export function SceneRail({ className }: { className?: string; idPrefix?: string }) {
  const { slots, pairFitness, removeSlot, openFilePicker } = useConsole();
  const [preview, setPreview] = useState<string | null>(null);
  const t1 = slots.find((s) => s.slot === "T1");
  const t2 = slots.find((s) => s.slot === "T2");

  return (
    <div className={cn("sq-scroll flex h-full flex-col overflow-y-auto p-4", className)}>
      <div className="text-[12px] tracking-wide text-mute uppercase">Scene</div>

      <div className="mt-3 flex flex-col gap-3">
        <SlotCard
          label="T1"
          hint="Drop a GeoTIFF"
          slot={t1}
          onRemove={() => removeSlot("T1")}
          onPreview={setPreview}
        />
        <SlotCard
          label="T2 / SAR"
          hint="Second date or SAR"
          slot={t2}
          onRemove={() => removeSlot("T2")}
          onPreview={setPreview}
        />
      </div>

      {pairFitness != null ? (
        <div className="mt-6">
          <div className="flex items-baseline justify-between text-[12px] text-mute">
            <span>Pair fitness</span>
            <span className="font-mono text-ink">{pairFitness.toFixed(2)}</span>
          </div>
          <div className="mt-2 h-1 overflow-hidden rounded-full bg-hairline">
            <div
              className="sq-bar-fill h-full rounded-full bg-primary"
              style={{ width: `${Math.round(pairFitness * 100)}%` }}
            />
          </div>
        </div>
      ) : null}

      <button
        type="button"
        onClick={openFilePicker}
        className="text-mute hover:text-primary mt-8 inline-flex items-center gap-2 text-left text-[13px]"
      >
        <Upload className="size-3.5" />
        Attach a GeoTIFF
      </button>

      {preview ? (
        <button
          type="button"
          className="sq-lightbox fixed inset-0 z-50 grid place-items-center bg-black/50 p-8"
          onClick={() => setPreview(null)}
        >
          <img src={preview} alt="Scene preview" className="max-h-[80vh] max-w-[90vw] rounded-xl border border-hairline" />
        </button>
      ) : null}
    </div>
  );
}
