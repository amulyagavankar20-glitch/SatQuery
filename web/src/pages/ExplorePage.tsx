import { Link } from "@tanstack/react-router";
import { Globe2 } from "lucide-react";
import { BrandMark } from "@/components/BrandMark";

export function ExplorePage() {
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      <header className="glass-strong rise flex items-center justify-between rounded-2xl px-5 py-3">
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-3">
            <BrandMark className="h-10 w-10 drop-shadow-[0_0_16px_rgba(240,132,42,0.35)]" />
            <div>
              <div className="text-[15px] font-semibold tracking-[0.32em] text-ink">SATQUERY</div>
              <div className="font-mono text-[10px] tracking-[0.2em] text-muted">SAC / ISRO · Earth observation desk</div>
            </div>
          </div>
          <nav className="hidden items-center gap-1 rounded-full border border-white/10 bg-black/20 p-1 text-[11px] tracking-[0.16em] uppercase md:flex">
            <Link to="/" className="rounded-full px-3 py-1 text-muted transition hover:bg-white/5 hover:text-ink">
              Analyze
            </Link>
            <span className="rounded-full bg-gradient-to-r from-saffron to-gold px-3 py-1 font-medium text-navy">
              Explore
            </span>
          </nav>
        </div>
      </header>
      <main className="flex flex-1 items-center justify-center">
        <div className="glass rise max-w-lg rounded-3xl px-10 py-12 text-center">
          <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-cyan/10 ring-1 ring-cyan/30">
            <Globe2 className="h-7 w-7 text-cyan" />
          </div>
          <h1 className="bg-gradient-to-r from-saffron to-gold bg-clip-text font-mono text-xs tracking-[0.32em] text-transparent uppercase">
            Explore · deferred
          </h1>
          <p className="mt-5 text-[15px] leading-relaxed text-ink/90">
            The globe is last. Analyze is the operational console: ingest GeoTIFFs, run the graph, read the
            receipt. Explore will only open packaged scene cards — never a WebGL screenshot as model input.
          </p>
          <Link
            to="/"
            className="btn-shine mt-8 inline-block rounded-xl bg-gradient-to-r from-saffron to-[#ffb056] px-5 py-2.5 font-mono text-[11px] tracking-[0.2em] text-navy uppercase shadow-[0_10px_30px_rgba(240,132,42,0.3)] transition hover:brightness-110"
          >
            Return to Analyze
          </Link>
        </div>
      </main>
    </div>
  );
}
