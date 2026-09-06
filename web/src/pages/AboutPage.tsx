import { Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";

import { EntryHeader } from "@/components/EntryHeader";
import { Footer } from "@/components/Footer";
import { NightSky } from "@/components/NightSky";

export function AboutPage() {
  return (
    <div className="relative flex h-dvh min-w-0 flex-col overflow-x-hidden bg-background">
      <NightSky />
      <EntryHeader />
      <article className="sq-scroll relative z-10 min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
        <div className="mx-auto w-full min-w-0 max-w-3xl overflow-x-hidden px-6 py-16 pb-24 sm:py-24">
          <p className="text-[12px] tracking-[0.14em] text-mute">About</p>
          <h1 className="sq-title mt-5 max-w-xl text-[1.5rem] font-medium leading-[1.2] tracking-[-0.025em] sm:text-[2.05rem]">
            Satellites write
            <br className="sm:hidden" /> measurement grids.
          </h1>
          <p className="mt-6 max-w-md text-[16px] leading-[1.65] text-mute">
            People ask. A router picks a specialist.
            <span className="mt-3 block text-ink/80">The specialist answers in words and in pixels.</span>
          </p>

          <figure className="sq-glass mt-16 w-full min-w-0 overflow-hidden rounded-xl px-4 py-6 sm:px-8 sm:py-8">
            <div className="flex flex-col gap-2 sm:hidden">
              {(
                [
                  ["Scene", "GeoTIFF"],
                  ["Router", "picks a specialist"],
                  ["Specialist", "one tool path"],
                ] as const
              ).map(([title, sub], i) => (
                <div key={title}>
                  {i > 0 ? <div className="mx-auto mb-2 h-4 w-px bg-primary/80" /> : null}
                  <div className="rounded-xl border border-hairline bg-background/50 px-4 py-3">
                    <div className="text-[14px] text-ink">{title}</div>
                    <div className="mt-0.5 text-[12px] text-mute">{sub}</div>
                  </div>
                </div>
              ))}
              <div className="mx-auto h-4 w-px bg-primary/80" />
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-primary/70 bg-background/50 px-3 py-3 text-center text-[14px] text-ink">
                  Words
                </div>
                <div className="rounded-xl border border-primary/70 bg-background/50 px-3 py-3 text-center text-[14px] text-ink">
                  Map evidence
                </div>
              </div>
            </div>
            <svg
              viewBox="0 0 560 220"
              className="hidden w-full sm:block"
              style={{ height: "auto" }}
              preserveAspectRatio="xMidYMid meet"
              role="img"
              aria-label="Scene to router to specialist, then words and map evidence"
            >
              <rect x="8" y="24" width="148" height="64" rx="12" fill="#121417" stroke="#2C343C" />
              <text x="82" y="50" textAnchor="middle" fill="#E8E4DC" fontSize="14" fontFamily="IBM Plex Sans, sans-serif">
                Scene
              </text>
              <text x="82" y="70" textAnchor="middle" fill="#8B959E" fontSize="11" fontFamily="IBM Plex Sans, sans-serif">
                GeoTIFF
              </text>

              <path d="M156 56 H196" stroke="#5E8F8A" strokeWidth="1.5" />
              <path d="M188 50 L196 56 L188 62" fill="none" stroke="#5E8F8A" strokeWidth="1.5" />

              <rect x="196" y="24" width="148" height="64" rx="12" fill="#121417" stroke="#2C343C" />
              <text x="270" y="50" textAnchor="middle" fill="#E8E4DC" fontSize="14" fontFamily="IBM Plex Sans, sans-serif">
                Router
              </text>
              <text x="270" y="70" textAnchor="middle" fill="#8B959E" fontSize="11" fontFamily="IBM Plex Sans, sans-serif">
                picks a specialist
              </text>

              <path d="M344 56 H384" stroke="#5E8F8A" strokeWidth="1.5" />
              <path d="M376 50 L384 56 L376 62" fill="none" stroke="#5E8F8A" strokeWidth="1.5" />

              <rect x="384" y="24" width="148" height="64" rx="12" fill="#121417" stroke="#2C343C" />
              <text x="458" y="50" textAnchor="middle" fill="#E8E4DC" fontSize="14" fontFamily="IBM Plex Sans, sans-serif">
                Specialist
              </text>
              <text x="458" y="70" textAnchor="middle" fill="#8B959E" fontSize="11" fontFamily="IBM Plex Sans, sans-serif">
                one tool path
              </text>

              <path d="M458 88 V120" stroke="#5E8F8A" strokeWidth="1.5" />
              <path d="M196 120 H458" stroke="#5E8F8A" strokeWidth="1.5" />
              <path d="M196 120 V136" stroke="#5E8F8A" strokeWidth="1.5" />
              <path d="M458 120 V136" stroke="#5E8F8A" strokeWidth="1.5" />

              <rect x="122" y="136" width="148" height="56" rx="12" fill="#121417" stroke="#5E8F8A" />
              <text x="196" y="169" textAnchor="middle" fill="#E8E4DC" fontSize="14" fontFamily="IBM Plex Sans, sans-serif">
                Words
              </text>

              <rect x="384" y="136" width="148" height="56" rx="12" fill="#121417" stroke="#5E8F8A" />
              <text x="458" y="169" textAnchor="middle" fill="#E8E4DC" fontSize="14" fontFamily="IBM Plex Sans, sans-serif">
                Map evidence
              </text>
            </svg>
            <figcaption className="mt-5 text-[13px] leading-relaxed text-mute">
              One question. One specialist. A receipt you can audit.
            </figcaption>
          </figure>

          <p className="mt-14 max-w-md text-[13px] leading-relaxed text-mute">
            Evaluated on SIH demo scenes. Overlay quality follows pair fitness and cloud — not a marketing score.
          </p>
          <p className="mt-8">
            <Link to="/console" className="text-primary inline-flex items-center gap-2 text-[14px] hover:underline">
              Open console
              <ArrowRight className="size-4" />
            </Link>
          </p>
        </div>
      </article>
      <Footer />
    </div>
  );
}
