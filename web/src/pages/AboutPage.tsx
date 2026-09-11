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
    body: "Intent router reads the question and the input class, then picks one specialist.",
  },
  {
    n: "03",
    title: "Specialist",
    body: "A deterministic graph runs one path — 9-class pixels, SAR backscatter & classification, change and fusion as specialist tools. Nothing is invented at runtime.",
  },
] as const;

const RETURNS = [
  { title: "Prose", body: "An English answer about this scene, not a generic caption." },
  { title: "Pixel mark", body: "Sage vectors on the raster — water, vegetation, built-up, or change." },
  { title: "Trace", body: "The tool path, collapsed, so you can see what ran." },
] as const;

const BENCH = [
  ["Router", "Agent Intent Router · text only · JSON schema"],
  ["Talk", "VLM Reasoning · multimodal synthesis"],
  ["Pixels", "Dynamic World 9-class on S2 · RGB demos use spectral fallback"],
  ["Tags", "BigEarthNet-19 names from those pixels — DW is not trained on BEN"],
  ["Change", "bit_cd → vectorize"],
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
          <p className="text-[12px] tracking-[0.14em] text-mute">About</p>
          <h1 className="mt-5 max-w-xl text-[2.05rem] font-medium leading-[1.14] tracking-[-0.035em] text-ink sm:text-[2.7rem] lg:text-[3.05rem]">
            <span className="block">Satellites write</span>
            <span className="sq-kicker-soft mt-[0.08em] inline-block pb-1">measurement grids.</span>
          </h1>
          <p className="mt-8 max-w-[28rem] text-[16px] leading-[1.65] text-mute sm:text-[17px]">
            Ask a Cartosat or RISAT scene a question.
            <span className="mt-2.5 block text-ink/80">
              A router picks one specialist. You get words, a mark on the pixels, and a receipt.
            </span>
          </p>

          <figure className="mt-14 w-full max-w-3xl sm:mt-16">
            <ol className="grid gap-10 sm:grid-cols-3 sm:gap-0">
              {INTAKE.map((step, i) => (
                <li key={step.n} className={i < INTAKE.length - 1 ? "sm:pr-8" : ""}>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-[11px] tracking-wide text-primary">{step.n}</span>
                    {i < INTAKE.length - 1 ? <span className="hidden h-px flex-1 bg-primary/35 sm:block" /> : null}
                  </div>
                  <h2 className="mt-4 text-[16px] font-medium text-ink">{step.title}</h2>
                  <p className="mt-2 max-w-[16rem] text-[13px] leading-relaxed text-mute">{step.body}</p>
                </li>
              ))}
            </ol>

            <div className="mt-12 border-t border-hairline pt-8">
              <p className="font-mono text-[11px] tracking-wide text-mute">Returns</p>
              <ol className="mt-5 grid gap-8 sm:grid-cols-3 sm:gap-0">
                {RETURNS.map((item, i) => (
                  <li key={item.title} className={i < RETURNS.length - 1 ? "sm:pr-8" : ""}>
                    <h3 className="text-[16px] font-medium text-ink">{item.title}</h3>
                    <p className="mt-2 max-w-[16rem] text-[13px] leading-relaxed text-mute">{item.body}</p>
                  </li>
                ))}
              </ol>
            </div>
          </figure>

          <dl className="mt-14 max-w-xl">
            {BENCH.map(([key, value]) => (
              <div key={key} className="sq-spec-row grid grid-cols-[5.5rem_1fr] gap-x-4 border-t border-hairline py-2.5 first:border-t-0 sm:grid-cols-[6.5rem_1fr]">
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
              className="sq-glass sq-cta group inline-flex h-12 items-center gap-2 rounded-xl px-7 text-[15px] font-medium text-ink transition-all duration-200 active:scale-[0.98]"
              style={{ borderColor: "rgba(94,143,138,0.5)" }}
            >
              Open console
              <ArrowRight className="size-4 text-primary" />
            </Link>
          </p>
        </div>
      </article>
      <Footer />
    </div>
  );
}

