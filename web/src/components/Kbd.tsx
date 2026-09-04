import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        "font-mono rounded-md border border-hairline bg-raised px-1.5 py-0.5 text-[10px] tracking-wide text-mute",
        className,
      )}
    >
      {children}
    </kbd>
  );
}
