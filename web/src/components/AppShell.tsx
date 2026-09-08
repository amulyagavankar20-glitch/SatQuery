import { Upload } from "lucide-react";
import type { ReactNode } from "react";

import { AppHeader } from "@/components/AppHeader";
import { Footer } from "@/components/Footer";
import { Grain } from "@/components/Grain";
import { ScenePills } from "@/components/ScenePills";
import { SceneRail } from "@/components/SceneRail";
import { Viewport } from "@/components/Viewport";
import { useModLabel } from "@/hooks/use-mod-label";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useConsole } from "@/state/console";

export function AppShell({ children }: { children: ReactNode }) {
  const { dragging, onDragEnter, onDragLeave, onDrop, sceneSheetOpen, setSceneSheetOpen } = useConsole();
  const mod = useModLabel();

  return (
    <div
      className="sq-console-wash relative flex h-dvh flex-col"
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
      <Grain />
      <AppHeader />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="order-2 flex min-h-0 min-w-0 flex-1 flex-col border-hairline lg:order-1 lg:w-[42%] lg:flex-none lg:border-r">
          <ScenePills />
          {children}
        </div>
        <div className="relative order-1 min-h-[42vh] min-w-0 lg:order-2 lg:min-h-0 lg:flex-1">
          <Viewport />
        </div>
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
        <div className="sq-enter pointer-events-none absolute inset-0 z-50 grid place-items-center bg-background/70">
          <div className="sq-drop-zone flex items-center gap-3 rounded-xl border-2 border-primary px-8 py-6 text-[15px] text-primary">
            <Upload className="size-5" />
            Drop a GeoTIFF
          </div>
        </div>
      ) : null}
    </div>
  );
}
