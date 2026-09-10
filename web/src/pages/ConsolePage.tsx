import { useSearch } from "@tanstack/react-router";
import { useEffect, useRef } from "react";

import { AppShell } from "@/components/AppShell";
import { Composer } from "@/components/Composer";
import { Thread } from "@/components/Thread";
import { isDemoId } from "@/lib/demos";
import { useConsole } from "@/state/console";

export function ConsolePage() {
  const search = useSearch({ strict: false });
  const scene = isDemoId(search.scene) ? search.scene : undefined;
  const { loadDemo } = useConsole();
  const applied = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!scene || applied.current === scene) return;
    applied.current = scene;
    loadDemo(scene);
  }, [scene, loadDemo]);

  return (
    <AppShell>
      <Thread />
      <Composer />
    </AppShell>
  );
}
