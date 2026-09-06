import { Link } from "@tanstack/react-router";

import { EntryHeader } from "@/components/EntryHeader";
import { StillEarth } from "@/components/StillEarth";
import { Button } from "@/components/ui/button";
import { DEMOS } from "@/lib/demos";

export function EntryPage() {
  return (
    <div className="flex min-h-dvh w-full min-w-0 max-w-[100vw] flex-col overflow-x-hidden bg-background">
      <EntryHeader />
      <main className="flex-1">
        <section className="relative flex min-h-[calc(100dvh-3rem)] min-w-0 items-center overflow-hidden px-6 py-12 sm:px-10 lg:px-16">
          <StillEarth />
          <div className="relative z-10 w-full min-w-0 max-w-[40rem]">
            <h1 className="text-[2.35rem] font-medium leading-[1.05] tracking-[-0.035em] text-ink sm:text-[3.15rem] lg:text-[3.75rem]">
              <span className="block">Ask a scene.</span>
              <span className="sq-kicker-soft mt-[0.08em] block">Get words and a mark.</span>
            </h1>
            <p className="mt-8 max-w-[26rem] text-[16px] leading-[1.65] text-mute sm:text-[17px]">
              Optical, SAR, or a pair.
              <span className="mt-2.5 block">A specialist answers in prose and on the pixels.</span>
            </p>
            <Button asChild size="lg" className="sq-cta mt-12 h-12 px-7 text-[15px]">
              <Link to="/console">Open console</Link>
            </Button>
          </div>
        </section>

        <section className="border-t border-hairline px-6 py-12 sm:px-10 lg:px-16">
          <p className="mx-auto mb-5 max-w-5xl text-[12px] tracking-[0.14em] text-mute">Scenes</p>
          <div className="mx-auto grid max-w-5xl gap-3 sm:grid-cols-3">
            {DEMOS.map((demo) => (
              <Link
                key={demo.id}
                to="/console"
                search={{ scene: demo.id }}
                aria-label={`Load demo: ${demo.title}`}
                className="sq-glass group overflow-hidden rounded-xl text-left hover:border-primary/50"
              >
                <div className="overflow-hidden">
                  <img
                    src={demo.thumb}
                    alt=""
                    className="h-32 w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
                  />
                </div>
                <div className="p-3">
                  <div className="text-[13px] font-medium text-ink">{demo.title}</div>
                  <div className="mt-1 text-[12px] leading-snug text-mute">{demo.blurb}</div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
