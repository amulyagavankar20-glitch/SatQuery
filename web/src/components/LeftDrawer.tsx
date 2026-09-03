import { type ReactNode, useState } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { cn } from "@/lib/cn";

export function LeftDrawer({
  children,
  defaultOpen = true,
}: {
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <aside
      className={cn(
        "drawer-container relative flex flex-col gap-3 overflow-hidden rounded-xl",
        open ? "min-w-[340px] w-[380px]" : "min-w-[48px] w-[48px]",
      )}
    >
      {/* Toggle button */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "absolute top-2 z-20 grid h-7 w-7 place-items-center rounded-lg border border-white/8 bg-panel/90 text-muted transition hover:border-cyan/30 hover:text-ink",
          open ? "right-2" : "left-[10px]",
        )}
        title={open ? "Collapse drawer" : "Expand drawer"}
      >
        {open ? <PanelLeftClose className="h-3.5 w-3.5" /> : <PanelLeftOpen className="h-3.5 w-3.5" />}
      </button>

      {/* Drawer content — fades out when collapsed */}
      <div className={cn("drawer-content flex min-h-0 flex-1 flex-col gap-3", !open && "drawer-collapsed")}>
        {children}
      </div>
    </aside>
  );
}
