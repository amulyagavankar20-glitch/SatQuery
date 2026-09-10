import type { DemoScene } from "@/lib/demos";
import { cn } from "@/lib/utils";

export function DemoThumb({
  demo,
  className,
}: {
  demo: DemoScene;
  className?: string;
}) {
  return (
    <img
      src={demo.thumb}
      alt=""
      className={cn("object-cover", className)}
      style={{ objectPosition: demo.thumbPos }}
    />
  );
}

export function SlotThumb({
  src,
  pos,
  alt = "",
  className,
}: {
  src: string;
  pos?: string | null;
  alt?: string;
  className?: string;
}) {
  return (
    <img
      src={src}
      alt={alt}
      className={cn("object-cover", className)}
      style={pos ? { objectPosition: pos } : undefined}
    />
  );
}
