import { Plus, RefreshCw, Upload } from "lucide-react";

import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";

export function ScenePills() {
  const { slots, hasScene, openFilePicker, activeSlot, setActiveSlot, toggleSlotModality, resetScene } = useConsole();
  const t1 = slots.find((s) => s.slot === "T1") ?? slots[0];
  const t2 = slots.find((s) => s.slot === "T2");
  const active = (activeSlot === "T2" && t2) ? t2 : t1;

  if (!hasScene || !active) {
    return (
      <div className="shrink-0 border-b border-hairline px-4 py-2">
        <button
          type="button"
          onClick={openFilePicker}
          className="text-mute hover:text-ink inline-flex items-center gap-2 font-mono text-[12px]"
        >
          <Upload className="size-3.5" />
          Attach GeoTIFF
        </button>
      </div>
    );
  }

  return (
    <div className="sq-chips shrink-0 overflow-x-auto border-b border-hairline px-3 py-2">
      <div className="flex min-w-max items-center gap-2">
        {/* Active Slot Asset Pill */}
        <div className="flex items-center gap-2 rounded-full px-2.5 py-1" style={{ background: "linear-gradient(135deg, rgb(22 26 31 / 0.78), rgb(26 30 34 / 0.6))", border: "1px solid rgb(255 255 255 / 0.08)", backdropFilter: "blur(12px) saturate(1.2)", boxShadow: "inset 0 1px 0 0 rgb(255 255 255 / 0.04)" }}>
          {active.previewUrl ? (
            <img
              src={active.previewUrl}
              alt=""
              className="size-6 rounded-md object-cover"
              style={active.objectPos ? { objectPosition: active.objectPos } : undefined}
            />
          ) : null}
          <span className="max-w-[7rem] truncate font-mono text-[11px] text-ink sm:max-w-[10rem]">{active.filename}</span>
          <button
            type="button"
            onClick={() => toggleSlotModality(active.slot)}
            title="Click to toggle modality (SAR / OPTICAL)"
            className={cn(
              "cursor-pointer rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-wide uppercase transition-colors",
              active.modality === "SAR"
                ? "bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/30"
                : "bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30"
            )}
          >
            {active.modality}
          </button>
          {active.date ? <span className="font-mono text-[10px] text-mute">{active.date}</span> : null}
        </div>

        {/* T1 / T2 Slot Switcher */}
        <div className="flex rounded-full border border-white/10 p-0.5 bg-black/20">
          {(["T1", "T2"] as const).map((slot) => {
            const present = slots.some((s) => s.slot === slot);
            const isSelected = activeSlot === slot;
            return (
              <button
                key={slot}
                type="button"
                onClick={() => setActiveSlot(slot)}
                title={present ? `Switch to ${slot} asset` : `${slot} not loaded (click to view)`}
                className={cn(
                  "rounded-full px-2.5 py-0.5 font-mono text-[10px] tracking-wide transition-all",
                  isSelected
                    ? "bg-primary/20 text-primary font-semibold border border-primary/30 shadow-sm"
                    : "text-mute hover:text-ink hover:bg-white/5",
                  !present && "opacity-60",
                )}
              >
                {slot}
                {!present ? " (empty)" : ""}
              </button>
            );
          })}
        </div>

        {/* Pair T2 / New Scene Actions */}
        {!t2 ? (
          <button
            type="button"
            onClick={() => {
              setActiveSlot("T2");
              openFilePicker();
            }}
            title="Upload T2 image to establish a temporal pair"
            className="inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 font-mono text-[10px] text-mute hover:border-primary/40 hover:text-ink transition-colors"
          >
            <Plus className="size-3" />
            Add T2 Pair
          </button>
        ) : null}

        <button
          type="button"
          onClick={resetScene}
          title="Clear current scene and start a new session"
          className="inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 font-mono text-[10px] text-mute hover:text-ink hover:border-white/20 transition-colors ml-auto"
        >
          <RefreshCw className="size-2.5" />
          New Scene
        </button>
      </div>
    </div>
  );
}
