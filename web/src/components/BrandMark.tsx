export function BrandMark({ className = "h-10 w-10" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#050910" />
      <rect x="0.6" y="0.6" width="30.8" height="30.8" rx="7.4" stroke="#f0842a" strokeOpacity="0.4" strokeWidth="1.2" fill="none" />
      <ellipse cx="16" cy="16" rx="11" ry="6.2" stroke="#f0842a" strokeWidth="1.15" fill="none" transform="rotate(-18 16 16)" />
      <ellipse cx="16" cy="16" rx="6.2" ry="11" stroke="#4ad4d4" strokeOpacity="0.55" strokeWidth="0.9" fill="none" />
      <circle cx="16" cy="16" r="3.1" fill="#4ad4d4" />
      <circle cx="16" cy="16" r="1.15" fill="#050910" />
      <circle cx="25.2" cy="11.2" r="1.35" fill="#f0842a" />
    </svg>
  );
}
