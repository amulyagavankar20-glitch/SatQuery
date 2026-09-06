import * as React from "react";

import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "placeholder:text-mute flex min-h-16 w-full resize-none rounded-lg border border-hairline bg-surface/55 px-3 py-2 text-[15px] leading-relaxed text-ink outline-none backdrop-blur-sm transition-[border-color,background-color] duration-150 focus-visible:border-primary focus-visible:bg-surface/80 disabled:cursor-not-allowed disabled:opacity-40",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
