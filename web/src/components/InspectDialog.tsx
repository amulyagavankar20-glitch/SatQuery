import { Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { useConsole } from "@/state/console";

export function InspectDialog() {
  const { inspectOpen, setInspectOpen, inspectJson, toast } = useConsole();

  return (
    <Dialog open={inspectOpen} onOpenChange={setInspectOpen}>
      <DialogContent className="flex max-h-[80vh] w-[min(640px,calc(100%-2rem))] flex-col">
        <div className="flex items-center justify-between pr-8">
          <div>
            <DialogTitle>Inspect</DialogTitle>
            <DialogDescription>Latest assistant turn as JSON.</DialogDescription>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-mute"
            disabled={!inspectJson}
            onClick={() => {
              if (!inspectJson) return;
              void navigator.clipboard.writeText(inspectJson).then(() => toast("Copied JSON"));
            }}
          >
            <Copy className="size-3.5" />
            Copy
          </Button>
        </div>
        <pre className="sq-scroll min-h-0 flex-1 overflow-auto rounded-lg bg-background p-3 font-mono text-[11px] leading-relaxed text-mute">
          {inspectJson ?? "No completed turn yet."}
        </pre>
      </DialogContent>
    </Dialog>
  );
}
