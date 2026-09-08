import { Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";

import { EntryHeader } from "@/components/EntryHeader";
import { Footer } from "@/components/Footer";
import { Grain } from "@/components/Grain";
import { ScenePlate } from "@/components/ScenePlate";

const INTAKE = [
  {
    n: "01",
    title: "Scene",
    body: "One GeoTIFF, or a pair. Optical, SAR, or both over the same ground.",
  },
  {
    n: "02",
    title: "Router",
    body: "Qwen2.5-3B reads the question and the input class, then picks one specialist.",
  },
  {
    n: "03",
    title: "Specialist",
    body: "A frozen graph runs one path — GeoChat for talk and grounding, change and fusion as specialist tools. Nothing is invented at runtime.",
  },
] as const;

const RETURNS = [
  { title: "Prose", body: "An English answer about this scene, not a generic caption." },
  { title: "Pixel mark", body: "Sage vectors on the raster — shoreline, change, or the grounded phrase." },
  { title: "Trace", body: "The tool path, collapsed, so you can see what ran." },
] as const;

const BENCH = [
  ["Router", "Qwen2.5-3B-Instruct · text only · JSON schema"],
  ["Talk", "GeoChat-7B · geochat_vqa / geochat_describe"],
  ["Change", "align → bit_cd → vectorize"],
  ["Fusion", "Optical + SAR, co-registered over the intersection"],
] as const;

export function AboutPage() {
  return (
    <div className="relative flex h-dvh min-w-0 flex-col overflow-x-hidden">
      <div className="pointer-events-none fixed inset-0 z-0">
        <ScenePlate />
        <Grain />
      </div>
      <EntryHeader />
      <article className="sq-scroll relative z-10 min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
        <div className="mx-auto flex w-full min-w-0 max-w-5xl flex-1 flex-col px-6 py-12 sm:px-10 sm:py-16 lg:px-16 lg:py-20">
          <p className="sq-hero-in text-[12px] tracking-[0.14em] text-mute" style={{ animationDelay: "0.05s" }}>About</p>
          <h1 className="mt-5 max-w-xl text-[2.05rem] font-medium leading-[1.08] tracking-[-0.035em] text-ink sm:text-[2.7rem] lg:text-[3.05rem]">
            <span className="sq-hero-in block" style={{ animationDelay: "0.1s" }}>Satellites write</span>
            <span className="sq-hero-in sq-kicker-soft mt-[0.08em] block" style={{ animationDelay: "0.22s" }}>measurement grids.</span>
          </h1>
          <p className="sq-hero-in mt-8 max-w-[28rem] text-[16px] leading-[1.65] text-mute sm:text-[17px]" style={{ animationDelay: "0.35s" }}>
            Ask a Cartosat or RISAT scene a question.
            <span className="mt-2.5 block text-ink/80">
              A router picks one specialist. You get words, a mark on the pixels, and a receipt.
            </span>
          </p>

          <figure className="mt-14 w-full max-w-3xl sm:mt-16">
            <ol className="grid gap-4 sm:grid-cols-3 sm:gap-3">
              {INTAKE.map((step, i) => (
                <li key={step.n} className="sq-hero-in sq-glass-card group rounded-xl p-4 transition-all duration-200 hover:-translate-y-1 hover:border-primary/40 hover:shadow-[0_8px_20px_-8px_rgba(0,0,0,0.5)]" style={{ animationDelay: `${0.45 + i * 0.08}s` }}>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-[11px] tracking-wide text-primary transition-transform duration-200 group-hover:scale-110">{step.n}</span>
                    {i < INTAKE.length - 1 ? <span className="hidden h-px flex-1 bg-primary/40 sm:block" /> : null}
                  </div>
                  <h2 className="mt-4 text-[16px] font-medium text-ink transition-colors duration-150 group-hover:text-primary">{step.title}</h2>
                  <p className="mt-2 max-w-[16rem] text-[13px] leading-relaxed text-mute">{step.body}</p>
                </li>
              ))}
            </ol>

            <div className="mt-12 pt-8">
              <div className="sq-gradient-divider mb-8" />
              <p className="font-mono text-[11px] tracking-wide text-primary">Returns</p>
              <ol className="mt-5 grid gap-4 sm:grid-cols-3 sm:gap-3">
                {RETURNS.map((item, i) => (
                  <li key={item.title} className="sq-hero-in sq-glass-card group rounded-xl p-4 transition-all duration-200 hover:-translate-y-1 hover:border-primary/40 hover:shadow-[0_8px_20px_-8px_rgba(0,0,0,0.5)]" style={{ animationDelay: `${0.7 + i * 0.08}s` }}>
                    <h3 className="text-[16px] font-medium text-ink transition-colors duration-150 group-hover:text-primary">{item.title}</h3>
                    <p className="mt-2 max-w-[16rem] text-[13px] leading-relaxed text-mute">{item.body}</p>
                  </li>
                ))}
              </ol>
            </div>
          </figure>

          <dl className="mt-14 max-w-xl">
            {BENCH.map(([key, value]) => (
              <div key={key} className="sq-spec-row grid grid-cols-[5.5rem_1fr] gap-x-4 py-2.5 first:border-t-0 sm:grid-cols-[6.5rem_1fr]" style={{ borderTop: "1px solid rgb(94 143 138 / 0.12)" }}>
                <dt className="font-mono text-[11px] tracking-wide text-primary">{key}</dt>
                <dd className="font-mono text-[11px] leading-relaxed text-mute sm:text-[12px]">{value}</dd>
              </div>
            ))}
          </dl>

          <p className="mt-10 max-w-md text-[13px] leading-relaxed text-mute">
            Evaluated on SIH demo scenes. Overlay quality follows pair fitness and cloud — not a marketing score.
          </p>
          <p className="mt-8">
            <Link
              to="/console"
              className="sq-glass sq-cta sq-glow-border group inline-flex h-12 items-center gap-2 rounded-xl px-7 text-[15px] font-medium text-ink transition-all duration-200 active:scale-[0.98]"
              style={{ borderColor: "rgba(94,143,138,0.5)" }}
            >
              Open console
              <ArrowRight className="size-4 text-primary transition-transform duration-200 group-hover:translate-x-1" />
            </Link>
          </p>
        </div>
      </article>
      <Footer />
    </div>
  );
}

