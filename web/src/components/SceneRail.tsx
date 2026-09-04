import { Aperture, CircleDashed, GitCompare, Radio, Upload, X } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Checkbox } from "@/components/ui/checkbox";
import { LAYER_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";
import type { LayerId, SceneSlot } from "@/lib/types";

const LAYER_ICONS: Record<LayerId, ReactNode> = {
  optical: <Aperture className="size-3.5" />,
  sar: <Radio className="size-3.5" />,
  change: <GitCompare className="size-3.5" />,
  uncertain: <CircleDashed className="size-3.5" />,
};

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
      <div className="flex items-center gap-3 rounded-xl border border-dashed border-hairline px-3 py-3">
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
    <div className="rounded-xl border border-hairline bg-raised/40 p-3">
      <div className="flex items-start gap-2.5">
        {slot.previewUrl ? (
          <button type="button" onClick={() => onPreview(slot.previewUrl)} className="shrink-0">
            <img src={slot.previewUrl} alt="" className="size-10 rounded-lg object-cover" />
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
        <Chip>{slot.modality === "SAR" ? "SAR" : "Optical"}</Chip>
        {slot.sensor ? <Chip>{slot.sensor}</Chip> : null}
      </div>
    </div>
  );
}

function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="font-mono rounded-md bg-background px-1.5 py-0.5 text-[11px] text-mute">{children}</span>
  );
}

export function SceneRail({ className, idPrefix = "rail" }: { className?: string; idPrefix?: string }) {
  const { slots, pairFitness, layers, setLayer, hasSar, hasOptical, removeSlot, openFilePicker } = useConsole();
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
              className="h-full rounded-full bg-primary transition-[width] duration-500"
              style={{ width: `${Math.round(pairFitness * 100)}%` }}
            />
          </div>
        </div>
      ) : null}

      <div className="mt-8">
        <div className="text-[12px] tracking-wide text-mute uppercase">Layers</div>
        <ul className="mt-3 flex flex-col gap-2">
          {LAYER_LABELS.map((layer) => {
            const disabled =
              (layer.id === "sar" && !hasSar) || (layer.id === "optical" && !hasOptical && slots.length === 0);
            return (
              <li key={layer.id}>
                <label
                  htmlFor={`${idPrefix}-${layer.id}`}
                  className={cn(
                    "flex cursor-pointer items-center gap-2.5 rounded-lg px-1 py-1 hover:bg-raised/60",
                    disabled && "cursor-not-allowed",
                  )}
                >
                  <Checkbox
                    checked={layers[layer.id]}
                    disabled={disabled}
                    onCheckedChange={(v) => setLayer(layer.id, v === true)}
                    id={`${idPrefix}-${layer.id}`}
                  />
                  <span className={cn("text-mute", disabled && "opacity-40")}>{LAYER_ICONS[layer.id]}</span>
                  <span className={cn("text-[13px]", disabled ? "text-mute/60" : "text-ink")}>{layer.label}</span>
                </label>
              </li>
            );
          })}
        </ul>
      </div>

      <button
        type="button"
        onClick={openFilePicker}
        className="text-mute hover:text-ink mt-8 inline-flex items-center gap-2 text-left text-[13px]"
      >
        <Upload className="size-3.5" />
        Attach a GeoTIFF
      </button>

      {preview ? (
        <button
          type="button"
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-8"
          onClick={() => setPreview(null)}
        >
          <img src={preview} alt="Scene preview" className="max-h-[80vh] max-w-[90vw] rounded-xl border border-hairline" />
        </button>
      ) : null}
    </div>
  );
}
