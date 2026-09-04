import { Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

import { AppHeader } from "@/components/AppHeader";
import { Footer } from "@/components/Footer";

export function AboutPage() {
  return (
    <div className="flex h-dvh flex-col bg-background">
      <AppHeader />
      <article className="sq-scroll min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-6 py-16">
          <p className="text-[22px] leading-snug text-ink">
            Satellites write measurement grids. People ask. A router picks a specialist. The specialist answers in words
            and in pixels.
          </p>

          <figure className="sq-enter mt-14">
            <svg
              viewBox="0 0 560 220"
              className="w-full"
              role="img"
              aria-label="Scene to router to specialist, then words and map evidence"
            >
              <rect x="8" y="24" width="148" height="64" rx="12" fill="#1A1E22" stroke="#2C343C" />
              <text x="82" y="50" textAnchor="middle" fill="#E8E4DC" fontSize="14" fontFamily="IBM Plex Sans, sans-serif">
                Scene
              </text>
              <text x="82" y="70" textAnchor="middle" fill="#8B959E" fontSize="11" fontFamily="IBM Plex Sans, sans-serif">
                GeoTIFF
              </text>

              <path d="M156 56 H196" stroke="#5E8F8A" strokeWidth="1.5" />
              <path d="M188 50 L196 56 L188 62" fill="none" stroke="#5E8F8A" strokeWidth="1.5" />

              <rect x="196" y="24" width="148" height="64" rx="12" fill="#1A1E22" stroke="#2C343C" />
              <text x="270" y="50" textAnchor="middle" fill="#E8E4DC" fontSize="14" fontFamily="IBM Plex Sans, sans-serif">
                Router
              </text>
              <text x="270" y="70" textAnchor="middle" fill="#8B959E" fontSize="11" fontFamily="IBM Plex Sans, sans-serif">
                picks a specialist
              </text>

              <path d="M344 56 H384" stroke="#5E8F8A" strokeWidth="1.5" />
              <path d="M376 50 L384 56 L376 62" fill="none" stroke="#5E8F8A" strokeWidth="1.5" />

              <rect x="384" y="24" width="148" height="64" rx="12" fill="#1A1E22" stroke="#2C343C" />
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

              <rect x="122" y="136" width="148" height="56" rx="12" fill="#1A1E22" stroke="#2C343C" />
              <text x="196" y="169" textAnchor="middle" fill="#E8E4DC" fontSize="14" fontFamily="IBM Plex Sans, sans-serif">
                Words
              </text>

              <rect x="384" y="136" width="148" height="56" rx="12" fill="#1A1E22" stroke="#2C343C" />
              <text x="458" y="169" textAnchor="middle" fill="#E8E4DC" fontSize="14" fontFamily="IBM Plex Sans, sans-serif">
                Map evidence
              </text>
            </svg>
            <figcaption className="mt-3 text-[12px] text-mute">One question. One specialist. A receipt you can audit.</figcaption>
          </figure>

          <p className="mt-14 text-[14px] leading-relaxed text-mute">
            Evaluated on SIH demo scenes. Overlay quality follows pair fitness and cloud — not a marketing score.
          </p>

          <p className="mt-10">
            <Link to="/" className="text-primary inline-flex items-center gap-2 text-[14px] hover:underline">
              <ArrowLeft className="size-4" />
              Back to console
            </Link>
          </p>
        </div>
      </article>
      <Footer />
    </div>
  );
}
