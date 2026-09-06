export function StillEarth() {
  return (
    <div className="sq-earth pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden>
      <img
        src="/earth.jpg"
        alt=""
        width={1024}
        height={1024}
        draggable={false}
        className="sq-earth-img absolute top-1/2 right-0 h-[min(92vh,760px)] w-auto max-w-none -translate-y-1/2 object-contain opacity-[0.72] sm:opacity-[0.84] lg:h-[min(98vh,880px)] lg:opacity-[0.94]"
      />
    </div>
  );
}
