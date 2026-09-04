import { Upload } from "lucide-react";
import type { ReactNode } from "react";

import { AppHeader } from "@/components/AppHeader";
import { Footer } from "@/components/Footer";
import { SceneRail } from "@/components/SceneRail";
import { useModLabel } from "@/hooks/use-mod-label";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useConsole } from "@/state/console";

export function AppShell({ children }: { children: ReactNode }) {
  const { dragging, onDragEnter, onDragLeave, onDrop, sceneSheetOpen, setSceneSheetOpen } = useConsole();
  const mod = useModLabel();

  return (
    <div
      className="relative flex h-dvh flex-col bg-background"
      onDragEnter={(e) => {
        e.preventDefault();
        onDragEnter();
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => onDragLeave()}
      onDrop={(e) => {
        e.preventDefault();
        onDrop(Array.from(e.dataTransfer.files));
      }}
    >
      <AppHeader />
      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-[280px] shrink-0 border-r border-hairline lg:block">
          <SceneRail idPrefix="rail" />
        </aside>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">{children}</div>
      </div>
      <Footer hint={`${mod}+Enter send · ${mod}+K commands`} />
      <Sheet open={sceneSheetOpen} onOpenChange={setSceneSheetOpen}>
        <SheetContent side="top" className="bg-background">
          <SheetHeader>
            <SheetTitle>Scene</SheetTitle>
          </SheetHeader>
          <SceneRail idPrefix="sheet" className="max-h-[70vh]" />
        </SheetContent>
      </Sheet>
      {dragging ? (
        <div className="sq-enter pointer-events-none absolute inset-0 z-50 grid place-items-center bg-background/80">
          <div className="flex items-center gap-3 rounded-xl border border-primary px-8 py-6 text-[15px] text-primary">
            <Upload className="size-5" />
            Drop a GeoTIFF
          </div>
        </div>
      ) : null}
    </div>
  );
}
