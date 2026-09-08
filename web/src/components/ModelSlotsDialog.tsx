import { useState, useEffect } from "react";
import { Cpu, CheckCircle2, AlertCircle, HardDrive, RefreshCw } from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { fetchModels } from "@/lib/api";
import type { ModelSlot } from "@/lib/schema";

interface ModelSlotsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ModelSlotsDialog({ open, onOpenChange }: ModelSlotsDialogProps) {
  const [slots, setSlots] = useState<ModelSlot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSlots = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchModels();
      setSlots(data.model_slots || []);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadSlots();
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px] max-h-[85vh] overflow-y-auto bg-surface border-hairline text-ink">
        <div className="space-y-1">
          <div className="flex items-center justify-between pr-6">
            <div className="flex items-center gap-2">
              <Cpu className="size-5 text-primary" />
              <DialogTitle className="text-lg font-medium text-ink">
                3-Model Slotting Architecture
              </DialogTitle>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={loadSlots}
              disabled={loading}
              className="text-mute hover:text-ink h-8 px-2"
            >
              <RefreshCw className={`size-3.5 mr-1 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
          <DialogDescription className="text-xs text-mute mt-1">
            SatQuery orchestrates 3 distinct model families: Qwen Agent Router, Talking VLM, and Spatial Specialists.
            Weights can be slotted directly into the designated local weights directory or connected via Ollama.
          </DialogDescription>
        </div>

        {error && (
          <div className="p-3 bg-red-950/40 border border-red-800/50 rounded text-xs text-red-300">
            Failed to fetch model slot status: {error}
          </div>
        )}

        <div className="space-y-3 mt-2">
          {slots.map((slot) => {
            const isReady = slot.status === "ready";
            return (
              <div
                key={slot.slot_id}
                className="p-3.5 rounded-lg border border-hairline bg-surface-2/60 space-y-2 hover:border-hairline-bright transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-ink">
                        {slot.name}
                      </span>
                      <span
                        className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded ${
                          isReady
                            ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/60"
                            : "bg-amber-950/80 text-amber-400 border border-amber-800/60"
                        }`}
                      >
                        {isReady ? "Weights Slotted" : "Standby Mock"}
                      </span>
                    </div>
                    <p className="text-[11px] text-ink/80 mt-0.5">{slot.description}</p>
                  </div>
                  {isReady ? (
                    <CheckCircle2 className="size-4 text-emerald-400 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="size-4 text-amber-400 shrink-0 mt-0.5" />
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] pt-1 border-t border-hairline/60 font-mono">
                  <div>
                    <span className="text-mute block text-[10px]">Target Model:</span>
                    <span className="text-ink truncate block">{slot.target_model}</span>
                  </div>
                  <div>
                    <span className="text-mute block text-[10px]">Active Backend:</span>
                    <span className="text-ink capitalize">{slot.backend_type}</span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-[10px] text-mute font-mono bg-surface-3/50 px-2 py-1 rounded">
                  <HardDrive className="size-3 shrink-0 text-primary" />
                  <span className="truncate" title={slot.weights_expected_at}>
                    Path: {slot.weights_expected_at}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
