export function ScenePlate() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      <div className="sq-plate-bloom" />
      <img
        src="/about-plate.jpg"
        alt=""
        className="sq-plate-img absolute top-1/2 right-0 h-[min(130vh,980px)] w-[min(78vw,980px)] -translate-y-1/2 object-cover opacity-[0.28] sm:opacity-[0.36] lg:opacity-[0.42]"
      />
    </div>
  );
}