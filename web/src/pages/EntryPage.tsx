import { Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";

import { EntryHeader } from "@/components/EntryHeader";
import { Footer } from "@/components/Footer";
import { Grain } from "@/components/Grain";
import { StillEarth } from "@/components/StillEarth";
import { DemoThumb } from "@/components/DemoThumb";
import { DEMOS } from "@/lib/demos";

export function EntryPage() {
  return (
    <div className="flex min-h-dvh w-full min-w-0 max-w-[100vw] flex-col overflow-x-hidden">
      <EntryHeader />
      <main className="flex-1">
        <section className="relative flex min-h-[calc(100dvh-3rem)] min-w-0 items-center overflow-hidden px-6 py-12 sm:px-10 lg:px-16">
          <StillEarth />
          <Grain />
          <div className="relative z-10 w-full min-w-0 max-w-[40rem]">
            <h1 className="text-[2.35rem] font-medium leading-[1.12] tracking-[-0.035em] text-ink sm:text-[3.15rem] lg:text-[3.75rem]">
              <span className="sq-hero-in block" style={{ animationDelay: "0.1s" }}>Ask a scene.</span>
              <span className="sq-hero-in sq-kicker-soft mt-[0.08em] inline-block pb-1" style={{ animationDelay: "0.25s" }}>Get words and a mark.</span>
            </h1>
            <p className="sq-hero-in mt-8 max-w-[26rem] text-[16px] leading-[1.65] text-mute sm:text-[17px]" style={{ animationDelay: "0.4s" }}>
              Optical, SAR, or a pair.
              <span className="mt-2.5 block">A specialist answers in prose and on the pixels.</span>
            </p>
            <Link
              to="/console"
              className="sq-hero-in sq-glass sq-cta sq-glow-border group mt-12 inline-flex h-12 items-center gap-2 rounded-xl px-7 text-[15px] font-medium text-ink transition-all duration-200 active:scale-[0.98]"
              style={{ borderColor: "rgba(94,143,138,0.5)", animationDelay: "0.55s" }}
            >
              Open console
              <ArrowRight className="size-4 text-primary transition-transform duration-200 group-hover:translate-x-1" />
            </Link>
          </div>
        </section>

        <section className="px-6 py-12 sm:px-10 lg:px-16">
          <div className="sq-gradient-divider mx-auto mb-10 max-w-5xl" />
          <p className="sq-hero-in mx-auto mb-5 max-w-5xl text-[12px] tracking-[0.14em] text-mute" style={{ animationDelay: "0.6s" }}>
            Scenes
          </p>
          <div className="mx-auto grid max-w-5xl gap-3 sm:grid-cols-3">
            {DEMOS.map((demo, i) => (
              <Link
                key={demo.id}
                to="/console"
                search={{ scene: demo.id }}
                aria-label={`Load demo: ${demo.title}`}
                className="sq-hero-in sq-glass group overflow-hidden rounded-xl text-left transition-all duration-300 hover:-translate-y-1 hover:border-primary/50 hover:shadow-[0_8px_24px_-8px_rgba(94,143,138,0.25)] active:scale-[0.98]"
                style={{ animationDelay: `${0.65 + i * 0.08}s` }}
              >
                <div className="aspect-[4/3] overflow-hidden">
                  <DemoThumb demo={demo} className="h-full w-full transition-transform duration-300 group-hover:scale-[1.04]" />
                </div>
                <div className="p-3">
                  <div className="font-mono text-[11px] tracking-wide text-mute transition-colors duration-200 group-hover:text-primary">
                    {String(i + 1).padStart(2, "0")} // {demo.title}
                  </div>
                  <div className="mt-1 text-[12px] leading-snug text-mute">{demo.blurb}</div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}

