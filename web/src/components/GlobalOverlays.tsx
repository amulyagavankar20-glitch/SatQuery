import { CommandPalette } from "@/components/CommandPalette";
import { InspectDialog } from "@/components/InspectDialog";
import { JobsDrawer } from "@/components/JobsDrawer";
import { ShortcutsDialog } from "@/components/ShortcutsDialog";
import { Toasts } from "@/components/Toasts";
import { useShortcuts } from "@/hooks/use-shortcuts";

export function GlobalOverlays() {
  useShortcuts();
  return (
    <>
      <JobsDrawer />
      <CommandPalette />
      <ShortcutsDialog />
      <InspectDialog />
      <Toasts />
    </>
  );
}
