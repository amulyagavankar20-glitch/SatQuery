import { useEffect } from "react";

import { OFFICIAL_CHIPS } from "@/lib/constants";
import { fitLatestMap } from "@/lib/map-registry";
import { isTypingTarget } from "@/lib/utils";
import { useConsole } from "@/state/console";

export function useShortcuts() {
  const ctx = useConsole();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = isTypingTarget(e.target);
      const meta = e.metaKey || e.ctrlKey;

      if (e.key === "Escape") {
        ctx.closeOverlays();
        return;
      }
      if (meta && e.key.toLowerCase() === "k") {
        e.preventDefault();
        ctx.setPaletteOpen(!ctx.paletteOpen);
        ctx.setHelpOpen(false);
        ctx.setInspectOpen(false);
        return;
      }
      if (meta && e.key === "Enter") {
        e.preventDefault();
        ctx.send();
        return;
      }
      if (meta && e.key.toLowerCase() === "o") {
        e.preventDefault();
        ctx.openFilePicker();
        return;
      }
      if (ctx.paletteOpen || ctx.helpOpen || ctx.inspectOpen) return;
      if (typing) return;

      if (e.key === "/") {
        e.preventDefault();
        ctx.composerRef.current?.focus();
        return;
      }
      if (e.key === "?") {
        e.preventDefault();
        ctx.setHelpOpen(true);
        return;
      }
      if (e.key.toLowerCase() === "f") {
        e.preventDefault();
        fitLatestMap();
        return;
      }
      if (e.key.toLowerCase() === "o") {
        e.preventDefault();
        ctx.toggleLayer("optical");
        return;
      }
      if (e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (ctx.hasSar) ctx.toggleLayer("sar");
        return;
      }
      if (e.key.toLowerCase() === "g") {
        e.preventDefault();
        ctx.toggleLayer("change");
        return;
      }
      if (e.key.toLowerCase() === "u") {
        e.preventDefault();
        ctx.toggleLayer("uncertain");
        return;
      }
      if (e.key.toLowerCase() === "j") {
        e.preventDefault();
        ctx.copyJobId();
        return;
      }
      if (e.key.toLowerCase() === "i") {
        e.preventDefault();
        if (ctx.inspectJson) ctx.setInspectOpen(true);
        return;
      }
      const digit = Number(e.key);
      if (digit >= 1 && digit <= OFFICIAL_CHIPS.length) {
        e.preventDefault();
        ctx.insertChip(OFFICIAL_CHIPS[digit - 1]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ctx]);
}
