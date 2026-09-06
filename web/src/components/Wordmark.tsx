import { Link } from "@tanstack/react-router";

export function Mark({ className = "size-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#1A1E22" />
      <rect x="0.75" y="0.75" width="30.5" height="30.5" rx="7.25" fill="none" stroke="#2C343C" strokeWidth="1" />
      <g fill="none" stroke="#2C343C" strokeWidth="0.7">
        <rect x="7" y="7" width="18" height="18" rx="1.5" />
        <path d="M13 7v18M19 7v18M7 13h18M7 19h18" />
      </g>
      <g fill="#5E8F8A">
        <rect x="8.15" y="8.15" width="4.7" height="4.7" rx="0.7" />
        <rect x="13.65" y="8.15" width="4.7" height="4.7" rx="0.7" />
        <rect x="13.65" y="13.65" width="4.7" height="4.7" rx="0.7" />
        <rect x="13.65" y="19.15" width="4.7" height="4.7" rx="0.7" />
        <rect x="19.15" y="19.15" width="4.7" height="4.7" rx="0.7" />
      </g>
    </svg>
  );
}

export function Wordmark() {
  return (
    <Link to="/" className="flex items-center gap-2.5 outline-none transition-opacity hover:opacity-80">
      <Mark />
      <span className="sq-kicker hidden text-[15px] tracking-tight sm:inline">SatQuery</span>
    </Link>
  );
}
