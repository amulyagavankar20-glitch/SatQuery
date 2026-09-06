import { ArrowUp, Paperclip } from "lucide-react";
import type { KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { OFFICIAL_CHIPS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";

export function Composer() {
  const { draft, setDraft, insertChip, send, sending, hasScene, openFilePicker, composerRef } = useConsole();
  const canSend = hasScene && draft.trim().length > 0 && !sending;

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="shrink-0 border-t border-hairline bg-background/80 px-4 py-3 backdrop-blur-md md:px-6">
      <div className="mx-auto w-full max-w-4xl">
        <div className="sq-chips flex gap-2 overflow-x-auto pb-1">
          {OFFICIAL_CHIPS.map((chip, i) => {
            const selected = draft === chip;
            return (
              <button
                key={chip}
                type="button"
                disabled={!hasScene}
                onClick={() => insertChip(chip)}
                title={`${i + 1}`}
                className={cn(
                  "shrink-0 rounded-lg border px-2.5 py-1 text-[12px] leading-snug disabled:opacity-40",
                  selected
                    ? "border-primary text-primary"
                    : "border-hairline text-mute hover:border-primary/40 hover:text-ink",
                )}
              >
                {chip}
              </button>
            );
          })}
        </div>

        <div className="mt-3 flex items-end gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="text-mute mb-0.5 shrink-0"
            onClick={openFilePicker}
            aria-label="Attach GeoTIFF"
          >
            <Paperclip />
          </Button>
          <Textarea
            ref={composerRef}
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              const el = e.target;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
            }}
            onKeyDown={onKeyDown}
            placeholder={hasScene ? "Ask this scene…" : "Load a scene to ask…"}
            rows={2}
            disabled={!hasScene}
            className="min-h-[44px] flex-1"
          />
          <Button type="button" onClick={() => send()} disabled={!canSend} className="mb-0.5 min-w-11" aria-label="Send">
            <ArrowUp className="size-4" />
            <span className="hidden sm:inline">Send</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
