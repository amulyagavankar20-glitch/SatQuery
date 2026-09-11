import { Layers, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { useConsole } from "@/state/console";

export function UploadChoiceDialog() {
  const { pendingUpload, confirmNewScene, confirmT2Pair, cancelUploadChoice, slots } = useConsole();
  const open = Boolean(pendingUpload);
  const currentT1 = slots.find((s) => s.slot === "T1") ?? slots[0];
  const incomingFile = pendingUpload?.files[0];

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && cancelUploadChoice()}>
      <DialogContent className="w-[min(480px,calc(100%-2rem))] border-white/10 bg-surface/95 p-6 shadow-2xl backdrop-blur-xl">
        <div className="flex items-start justify-between">
          <div>
            <DialogTitle className="font-mono text-[16px] font-semibold text-ink">
              Choose Scene Action
            </DialogTitle>
            <DialogDescription className="mt-1 text-[13px] text-mute">
              You already have an active scene loaded. How would you like to attach{" "}
              <span className="font-mono font-medium text-ink">{incomingFile?.name}</span>?
            </DialogDescription>
          </div>
          <button
            type="button"
            onClick={cancelUploadChoice}
            className="text-mute hover:text-ink hover:bg-white/5 rounded-lg p-1 transition-all"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={confirmT2Pair}
            className="group flex flex-col items-start rounded-xl border border-primary/30 bg-primary/5 p-4 text-left transition-all duration-200 hover:border-primary/60 hover:bg-primary/10 hover:shadow-lg active:scale-[0.98]"
          >
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary/20 text-primary border border-primary/30">
              <Layers className="size-4" />
            </div>
            <div className="mt-3 font-mono text-[13px] font-semibold text-ink group-hover:text-primary transition-colors">
              Add as T2 Pair
            </div>
            <div className="mt-1 text-[11.5px] leading-relaxed text-mute">
              Pair alongside <span className="font-mono text-ink/90">{currentT1?.filename ?? "T1"}</span> for bi-temporal change detection (BIT-LEVIR).
            </div>
          </button>

          <button
            type="button"
            onClick={confirmNewScene}
            className="group flex flex-col items-start rounded-xl border border-white/10 bg-raised/40 p-4 text-left transition-all duration-200 hover:border-white/20 hover:bg-raised/80 hover:shadow-lg active:scale-[0.98]"
          >
            <div className="flex size-9 items-center justify-center rounded-lg bg-white/5 text-ink border border-white/10">
              <Sparkles className="size-4" />
            </div>
            <div className="mt-3 font-mono text-[13px] font-semibold text-ink group-hover:text-primary transition-colors">
              Start New Scene
            </div>
            <div className="mt-1 text-[11.5px] leading-relaxed text-mute">
              Reset active session, clear old overlays and traces, and analyze this image independently as T1.
            </div>
          </button>
        </div>

        <div className="mt-4 flex justify-end">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={cancelUploadChoice}
            className="text-mute hover:text-ink font-mono text-[11px]"
          >
            Cancel
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
