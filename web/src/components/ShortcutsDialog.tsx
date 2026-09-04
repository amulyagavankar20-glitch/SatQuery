import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Kbd } from "@/components/Kbd";
import { SHORTCUTS } from "@/lib/shortcuts";
import { useConsole } from "@/state/console";
import { useModLabel } from "@/hooks/use-mod-label";

export function ShortcutsDialog() {
  const { helpOpen, setHelpOpen } = useConsole();
  const mod = useModLabel();

  return (
    <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
      <DialogContent>
        <DialogTitle>Shortcuts</DialogTitle>
        <DialogDescription>Keys work when you are not typing in a field.</DialogDescription>
        <dl className="mt-1 flex flex-col gap-2">
          {SHORTCUTS.map((row) => (
            <div key={row.label} className="flex items-center justify-between gap-4">
              <dt className="text-[13px] text-mute">{row.label}</dt>
              <dd>
                <Kbd>{mod === "⌘" ? (row.mac ?? row.keys) : row.keys}</Kbd>
              </dd>
            </div>
          ))}
        </dl>
      </DialogContent>
    </Dialog>
  );
}
