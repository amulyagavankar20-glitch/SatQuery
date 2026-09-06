import { Link, useRouterState } from "@tanstack/react-router";
import { Command, History, Layers } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/Kbd";
import { Wordmark } from "@/components/Wordmark";
import { useModLabel } from "@/hooks/use-mod-label";
import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";

export function AppHeader() {
  const { openJobs, setSceneSheetOpen, setPaletteOpen, hasScene, slots, sending, apiUp } = useConsole();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const onAbout = pathname === "/about";
  const onExplore = pathname === "/explore";
  const onConsole = pathname === "/console";
  const mod = useModLabel();

  return (
    <header className="sq-header-glass relative flex h-12 shrink-0 items-center gap-3 border-b border-hairline px-3 sm:px-4">
      <Wordmark />

      <div className="ml-auto flex items-center gap-0.5 sm:gap-1">
        {onConsole ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-mute lg:hidden"
            onClick={() => setSceneSheetOpen(true)}
          >
            <Layers className="size-3.5" />
            Scene{hasScene ? ` · ${slots.length}` : ""}
          </Button>
        ) : null}
        <Link to="/explore" className={cn("sq-nav", onExplore && "sq-nav-on")}>
          Explore
        </Link>
        <Link to="/about" className={cn("sq-nav", onAbout && "sq-nav-on")}>
          About
        </Link>
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
          title={apiUp ? "Local · API connected" : "Local · mock"}
        >
          <span className={cn("size-1.5 rounded-full", apiUp ? "bg-primary" : "bg-mute")} />
          {apiUp ? "local" : "mock"}
        </span>
      </div>
      {sending ? <div className="sq-progress absolute inset-x-0 bottom-0" /> : null}
    </header>
  );
}
