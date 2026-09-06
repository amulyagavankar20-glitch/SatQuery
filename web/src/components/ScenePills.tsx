import { Upload } from "lucide-react";

import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";

export function ScenePills() {
  const { slots, hasScene, openFilePicker, activeSlot, setActiveSlot } = useConsole();
  const active = slots.find((s) => s.slot === activeSlot) ?? slots[0];
  const pair = slots.length > 1;

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
          <span className="font-mono text-[10px] tracking-wide text-primary uppercase">{active.modality}</span>
          {active.date ? <span className="font-mono text-[10px] text-mute">{active.date}</span> : null}
        </div>
        {pair ? (
          <div className="flex rounded-full border border-white/10 p-0.5">
            {(["T1", "T2"] as const).map((slot) => {
              const present = slots.some((s) => s.slot === slot);
              return (
                <button
                  key={slot}
                  type="button"
                  disabled={!present}
                  onClick={() => setActiveSlot(slot)}
                  className={cn(
                    "rounded-full px-2 py-0.5 font-mono text-[10px] tracking-wide",
                    activeSlot === slot ? "bg-primary/15 text-primary" : "text-mute hover:text-ink",
                    !present && "opacity-40",
                  )}
                >
                  {slot}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
}
