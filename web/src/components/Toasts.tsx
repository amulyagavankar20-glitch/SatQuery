import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";

export function Toasts() {
  const { toasts } = useConsole();
  if (!toasts.length) return null;
  return (
    <div className="pointer-events-none fixed right-4 bottom-24 z-[70] flex w-64 flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            "sq-enter rounded-xl border border-hairline bg-surface px-3 py-2 text-[12px] text-ink",
            t.kind === "bad" && "border-destructive/40 text-destructive",
          )}
        >
          {t.text}
        </div>
      ))}
    </div>
  );
}
