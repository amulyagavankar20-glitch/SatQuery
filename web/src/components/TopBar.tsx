import { cn } from "@/lib/cn";
import { BrandMark } from "@/components/BrandMark";
import { PipelineStrip } from "@/components/PipelineStrip";
import { Link } from "@tanstack/react-router";
import type { JobView } from "@/lib/schema";

function StatusLed({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/5 bg-white/[0.03] px-2.5 py-1 font-mono text-[9px] tracking-[0.14em] text-muted uppercase">
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full transition-all duration-500",
          ok ? "bg-ok shadow-[0_0_8px_#3dba7a]" : "bg-bad shadow-[0_0_8px_#e05b56]",
        )}
      />
      {label}
    </span>
  );
}

export function TopBar({
  apiOk,
  ollamaOk,
  pgOk,
  vlmBackend,
  job,
  activePage = "analyze",
  onPaletteOpen,
  onHelpOpen,
}: {
  apiOk: boolean;
  ollamaOk: boolean;
  pgOk: boolean;
  vlmBackend: string;
  job: JobView | null;
  activePage?: "analyze" | "explore";
  onPaletteOpen: () => void;
  onHelpOpen: () => void;
}) {
  return (
    <header className="glass-strong rise flex items-center justify-between gap-3 rounded-xl px-4 py-2">
      <div className="flex min-w-0 items-center gap-4">
        <div className="flex items-center gap-2.5">
          <BrandMark className="h-8 w-8 drop-shadow-[0_0_12px_rgba(240,132,42,0.3)]" />
          <div>
            <div className="text-[13px] font-semibold tracking-[0.3em] text-ink">SATQUERY</div>
            <div className="font-mono text-[9px] tracking-[0.16em] text-muted/80">SAC / ISRO</div>
          </div>
        </div>

        <nav className="hidden items-center gap-0.5 rounded-full border border-white/8 bg-black/25 p-0.5 text-[10px] tracking-[0.16em] uppercase md:flex">
          {activePage === "analyze" ? (
            <span className="rounded-full bg-gradient-to-r from-saffron to-gold px-3 py-1 font-medium text-navy">
              Analyze
            </span>
          ) : (
            <Link to="/" className="rounded-full px-3 py-1 text-muted transition hover:bg-white/5 hover:text-ink">
              Analyze
            </Link>
          )}
          {activePage === "explore" ? (
            <span className="rounded-full bg-gradient-to-r from-saffron to-gold px-3 py-1 font-medium text-navy">
              Explore
            </span>
          ) : (
            <Link to="/explore" className="rounded-full px-3 py-1 text-muted transition hover:bg-white/5 hover:text-ink">
              Explore
            </Link>
          )}
        </nav>

        <PipelineStrip job={job} />
      </div>

      <div className="flex flex-wrap items-center justify-end gap-1.5">
        <StatusLed ok={apiOk} label="API" />
        <StatusLed ok={ollamaOk} label="Ollama" />
        <StatusLed ok={pgOk} label="PostGIS" />
        <span className="hidden rounded-full border border-white/8 bg-black/25 px-2 py-1 font-mono text-[9px] tracking-[0.12em] text-muted/80 uppercase sm:inline">
          {vlmBackend}
        </span>
        <button
          type="button"
          onClick={onPaletteOpen}
          className="rounded-full border border-white/8 bg-black/25 px-2.5 py-1 font-mono text-[10px] text-muted transition hover:border-cyan/30 hover:text-ink"
          title="Command palette"
        >
          ⌘K
        </button>
        <button
          type="button"
          onClick={onHelpOpen}
          className="rounded-full border border-white/8 bg-black/25 px-2.5 py-1 font-mono text-[10px] text-muted transition hover:border-cyan/30 hover:text-ink"
          title="Keyboard shortcuts"
        >
          ?
        </button>
      </div>
    </header>
  );
}
