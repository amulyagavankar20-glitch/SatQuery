const STARS: { x: number; y: number; s: number; kind: "warm" | "cool" | "bright"; twinkle?: boolean; delay?: string }[] = [
  { x: 140, y: 90, s: 1.1, kind: "warm" },
  { x: 280, y: 160, s: 0.7, kind: "warm", twinkle: true, delay: "1.2s" },
  { x: 420, y: 70, s: 1.6, kind: "bright" },
  { x: 510, y: 210, s: 0.6, kind: "cool" },
  { x: 80, y: 340, s: 0.9, kind: "warm", twinkle: true, delay: "3.4s" },
  { x: 190, y: 480, s: 0.5, kind: "cool" },
  { x: 330, y: 620, s: 1.2, kind: "warm" },
  { x: 70, y: 720, s: 0.6, kind: "warm", twinkle: true, delay: "0.6s" },
  { x: 250, y: 880, s: 0.8, kind: "cool" },
  { x: 460, y: 940, s: 0.5, kind: "warm" },
  { x: 620, y: 80, s: 0.7, kind: "cool" },
  { x: 780, y: 140, s: 1.0, kind: "warm", twinkle: true, delay: "4.1s" },
  { x: 910, y: 50, s: 0.55, kind: "warm" },
  { x: 1040, y: 180, s: 1.4, kind: "bright" },
  { x: 1180, y: 90, s: 0.6, kind: "cool" },
  { x: 1320, y: 220, s: 0.8, kind: "warm" },
  { x: 1480, y: 70, s: 1.1, kind: "warm", twinkle: true, delay: "2.2s" },
  { x: 1620, y: 160, s: 0.5, kind: "cool" },
  { x: 1780, y: 110, s: 0.9, kind: "warm" },
  { x: 1860, y: 280, s: 0.7, kind: "cool", twinkle: true, delay: "5s" },
  { x: 1540, y: 340, s: 0.6, kind: "warm" },
  { x: 1720, y: 460, s: 1.3, kind: "bright" },
  { x: 1830, y: 580, s: 0.5, kind: "warm" },
  { x: 1600, y: 680, s: 0.8, kind: "cool" },
  { x: 1760, y: 790, s: 0.6, kind: "warm", twinkle: true, delay: "1.8s" },
  { x: 1880, y: 900, s: 1.0, kind: "warm" },
  { x: 1520, y: 960, s: 0.55, kind: "cool" },
  { x: 1680, y: 1040, s: 0.7, kind: "warm" },
  { x: 1280, y: 980, s: 0.9, kind: "cool", twinkle: true, delay: "3s" },
  { x: 1100, y: 1020, s: 0.5, kind: "warm" },
  { x: 920, y: 960, s: 1.15, kind: "warm" },
  { x: 740, y: 1040, s: 0.6, kind: "cool" },
  { x: 580, y: 990, s: 0.8, kind: "warm" },
  { x: 1380, y: 720, s: 0.5, kind: "warm" },
  { x: 1200, y: 540, s: 0.45, kind: "cool" },
  { x: 860, y: 400, s: 0.5, kind: "warm" },
];

function Star({ x, y, s, kind, twinkle, delay }: (typeof STARS)[number]) {
  const fill = kind === "cool" ? "url(#sq-star-cool)" : kind === "bright" ? "url(#sq-star-bright)" : "url(#sq-star-warm)";
  const r = 7 * s;
  return (
    <g className={twinkle ? "sq-star" : undefined} style={twinkle ? { animationDelay: delay } : undefined}>
      {kind === "bright" ? (
        <>
          <line x1={x - 11 * s} y1={y} x2={x + 11 * s} y2={y} stroke="url(#sq-spike-h)" strokeWidth={0.6 * s} />
          <line x1={x} y1={y - 9 * s} x2={x} y2={y + 9 * s} stroke="url(#sq-spike-v)" strokeWidth={0.55 * s} />
        </>
      ) : null}
      <circle cx={x} cy={y} r={r} fill={fill} />
    </g>
  );
}

export function NightSky() {
  return (
    <div className="sq-sky pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      <svg viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMid slice" className="h-full w-full">
        <defs>
          <radialGradient id="sq-star-warm">
            <stop offset="0%" stopColor="#F4F0E8" stopOpacity="0.95" />
            <stop offset="28%" stopColor="#E8E4DC" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#E8E4DC" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="sq-star-cool">
            <stop offset="0%" stopColor="#D5E8E5" stopOpacity="0.8" />
            <stop offset="30%" stopColor="#5E8F8A" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#5E8F8A" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="sq-star-bright">
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.95" />
            <stop offset="18%" stopColor="#F4F0E8" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#E8E4DC" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="sq-spike-h" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#E8E4DC" stopOpacity="0" />
            <stop offset="50%" stopColor="#F4F0E8" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#E8E4DC" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="sq-spike-v" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#E8E4DC" stopOpacity="0" />
            <stop offset="50%" stopColor="#F4F0E8" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#E8E4DC" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="sq-orbit-stroke" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#5E8F8A" stopOpacity="0" />
            <stop offset="40%" stopColor="#5E8F8A" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#5E8F8A" stopOpacity="0" />
          </linearGradient>
          <filter id="sq-orbit-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {STARS.map((star, i) => (
          <Star key={i} {...star} />
        ))}

        <g filter="url(#sq-orbit-glow)" opacity="0.7">
          <ellipse
            cx="1300"
            cy="700"
            rx="620"
            ry="240"
            fill="none"
            stroke="url(#sq-orbit-stroke)"
            strokeWidth="1.1"
            transform="rotate(16 1300 700)"
          />
          <ellipse
            cx="1380"
            cy="640"
            rx="760"
            ry="300"
            fill="none"
            stroke="url(#sq-orbit-stroke)"
            strokeWidth="1.25"
            transform="rotate(-22 1380 640)"
          />
        </g>
      </svg>
    </div>
  );
}
