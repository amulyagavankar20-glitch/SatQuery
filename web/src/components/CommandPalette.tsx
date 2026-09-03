import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";

export type PaletteCommand = {
  id: string;
  label: string;
  hint?: string;
  kbd?: string;
  disabled?: boolean;
  run: () => void;
};

export function CommandPalette({
  open,
  commands,
  onClose,
}: {
  open: boolean;
  commands: PaletteCommand[];
  onClose: () => void;
}) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const filtered = useMemo(() => {
    const n = q.trim().toLowerCase();
    if (!n) return commands;
    return commands.filter(
      (c) => c.label.toLowerCase().includes(n) || (c.hint ?? "").toLowerCase().includes(n),
    );
  }, [commands, q]);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setActive(0);
    const t = window.setTimeout(() => inputRef.current?.focus(), 20);
    return () => window.clearTimeout(t);
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [q]);

  if (!open) return null;

  const run = (cmd: PaletteCommand | undefined) => {
    if (!cmd || cmd.disabled) return;
    cmd.run();
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-[60] grid place-items-start bg-black/55 px-3 pt-[12vh] backdrop-blur-sm"
      onMouseDown={onClose}
    >
      <div
        className="glass-strong w-full max-w-lg overflow-hidden rounded-2xl shadow-[0_30px_80px_rgba(0,0,0,0.55)]"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="border-b border-white/10 px-3 py-2">
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                e.preventDefault();
                onClose();
              }
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((i) => Math.min(filtered.length - 1, i + 1));
              }
              if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((i) => Math.max(0, i - 1));
              }
              if (e.key === "Enter") {
                e.preventDefault();
                run(filtered[active]);
              }
            }}
            placeholder="Run a command…"
            className="w-full bg-transparent px-1 py-2 text-sm text-ink outline-none placeholder:text-muted"
            aria-label="Command palette"
          />
        </div>
        <ul className="sq-scroll max-h-[min(360px,50vh)] overflow-y-auto p-1.5">
          {filtered.length === 0 ? (
            <li className="px-3 py-4 font-mono text-[11px] text-muted">No matches.</li>
          ) : (
            filtered.map((cmd, i) => (
              <li key={cmd.id}>
                <button
                  type="button"
                  disabled={cmd.disabled}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => run(cmd)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left transition",
                    i === active ? "bg-cyan/15" : "hover:bg-white/5",
                    cmd.disabled && "opacity-35",
                  )}
                >
                  <span>
                    <span className="block text-[13px] text-ink">{cmd.label}</span>
                    {cmd.hint ? <span className="font-mono text-[10px] text-muted">{cmd.hint}</span> : null}
                  </span>
                  {cmd.kbd ? <kbd>{cmd.kbd}</kbd> : null}
                </button>
              </li>
            ))
          )}
        </ul>
        <p className="border-t border-white/10 px-3 py-1.5 font-mono text-[10px] text-muted">
          ↑↓ navigate · ↵ run · esc close
        </p>
      </div>
    </div>
  );
}
