import { useState } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { Command, Cpu, History, Layers } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/Kbd";
import { Wordmark } from "@/components/Wordmark";
import { ModelSlotsDialog } from "@/components/ModelSlotsDialog";
import { useModLabel } from "@/hooks/use-mod-label";
import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";

export function AppHeader() {
  const [modelsOpen, setModelsOpen] = useState(false);
  const { openJobs, setSceneSheetOpen, setPaletteOpen, hasScene, slots, sending, apiUp } = useConsole();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const onAbout = pathname === "/about";
  const onExplore = pathname === "/explore";
  const onConsole = pathname === "/console";
  const mod = useModLabel();

  const prefetchAbout = () => {
    const img = new Image();
    img.src = "/about-plate.jpg";
  };

  return (
    <header className="sq-header-glass relative z-20 flex h-12 shrink-0 items-center gap-3 border-b border-hairline px-3 sm:px-4">
      <Wordmark />

      <div className="ml-auto flex items-center gap-0.5 sm:gap-1">
        {onConsole ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-mute lg:hidden transition-transform active:scale-95"
            onClick={() => setSceneSheetOpen(true)}
          >
            <Layers className="size-3.5" />
            Scene{hasScene ? ` · ${slots.length}` : ""}
          </Button>
        ) : null}
        <Link to="/explore" className={cn("sq-nav transition-all active:scale-95", onExplore && "sq-nav-on")}>
          Explore
        </Link>
        <Link
          to="/about"
          onMouseEnter={prefetchAbout}
          onFocus={prefetchAbout}
          className={cn("sq-nav transition-all active:scale-95", onAbout && "sq-nav-on")}
        >
          About
        </Link>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-mute hover:text-ink"
          onClick={() => setModelsOpen(true)}
          title="Inspect 3-model slotting status"
        >
          <Cpu className="size-3.5" />
          Models
        </Button>
        <Button type="button" variant="ghost" size="sm" className="text-mute hover:text-ink" onClick={openJobs}>
          <History className="size-3.5" />
          Jobs
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-mute hover:text-ink hidden sm:inline-flex"
          onClick={() => setPaletteOpen(true)}
          aria-label="Command palette"
        >
          <Command className="size-3.5" />
          <Kbd className="ml-1">{mod}+K</Kbd>
        </Button>
        <span
          className="ml-2 hidden items-center gap-2 text-[12px] text-mute sm:inline-flex"
          title={apiUp ? "Local · API connected" : "Offline · Disconnected"}
        >
          <span className={cn("size-1.5 rounded-full", apiUp ? "sq-live bg-primary" : "bg-mute")} />
          {apiUp ? "connected" : "offline"}
        </span>
      </div>
      <ModelSlotsDialog open={modelsOpen} onOpenChange={setModelsOpen} />
      {sending ? <div className="sq-progress absolute inset-x-0 bottom-0" /> : null}
    </header>
  );
}
