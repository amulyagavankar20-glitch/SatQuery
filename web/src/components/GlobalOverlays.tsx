import { useRouterState } from "@tanstack/react-router";

import { CommandPalette } from "@/components/CommandPalette";
import { InspectDialog } from "@/components/InspectDialog";
import { JobsDrawer } from "@/components/JobsDrawer";
import { ShortcutsDialog } from "@/components/ShortcutsDialog";
import { Toasts } from "@/components/Toasts";
import { UploadChoiceDialog } from "@/components/UploadChoiceDialog";
import { useShortcuts } from "@/hooks/use-shortcuts";

export function GlobalOverlays() {
  useShortcuts();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const onDoor = pathname === "/" || pathname === "/about";

  if (onDoor) return <Toasts />;

  return (
    <>
      <JobsDrawer />
      <CommandPalette />
      <ShortcutsDialog />
      <InspectDialog />
      <UploadChoiceDialog />
      <Toasts />
    </>
  );
}
