import type { BBox } from "./types";
import type { DemoScene } from "./demos";

export function bboxFromCorners(
  a: { lng: number; lat: number },
  b: { lng: number; lat: number },
): BBox {
  return [
    Math.min(a.lng, b.lng),
    Math.min(a.lat, b.lat),
    Math.max(a.lng, b.lng),
    Math.max(a.lat, b.lat),
  ];
}

export function bboxPolygon(bounds: BBox) {
  const [w, s, e, n] = bounds;
  return {
    type: "Feature" as const,
    properties: {},
    geometry: {
      type: "Polygon" as const,
      coordinates: [
        [
          [w, s],
          [e, s],
          [e, n],
          [w, n],
          [w, s],
        ],
      ],
    },
  };
}

export function bboxArea(bounds: BBox) {
  return Math.max(0, bounds[2] - bounds[0]) * Math.max(0, bounds[3] - bounds[1]);
}

export function intersectBBox(a: BBox, b: BBox): BBox | null {
  const west = Math.max(a[0], b[0]);
  const south = Math.max(a[1], b[1]);
  const east = Math.min(a[2], b[2]);
  const north = Math.min(a[3], b[3]);
  if (east <= west || north <= south) return null;
  return [west, south, east, north];
}

export function pointInBBox(lng: number, lat: number, bounds: BBox) {
  return lng >= bounds[0] && lng <= bounds[2] && lat >= bounds[1] && lat <= bounds[3];
}

export function sceneUnderPoint(demos: DemoScene[], lng: number, lat: number): DemoScene | null {
  return demos.find((d) => pointInBBox(lng, lat, d.slots[0]!.bounds)) ?? null;
}

export function bestSceneForBox(demos: DemoScene[], box: BBox): { demo: DemoScene; hit: BBox; coverage: number } | null {
  let best: { demo: DemoScene; hit: BBox; coverage: number } | null = null;
  for (const demo of demos) {
    const hit = intersectBBox(box, demo.slots[0]!.bounds);
    if (!hit) continue;
    const coverage = bboxArea(hit) / bboxArea(demo.slots[0]!.bounds);
    if (!best || bboxArea(hit) > bboxArea(best.hit)) best = { demo, hit, coverage };
  }
  return best;
}

function loadImage(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new Image();
    img.decoding = "async";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Could not read ${src}`));
    img.src = src;
  });
}

export async function cropScenePng(demo: DemoScene, crop: BBox): Promise<File | null> {
  const scene = demo.slots[0]!.bounds;
  const hit = intersectBBox(scene, crop);
  if (!hit) return null;
  const img = await loadImage(demo.thumb);
  const [w, s, e, n] = scene;
  const sx = ((hit[0] - w) / (e - w)) * img.width;
  const sy = ((n - hit[3]) / (n - s)) * img.height;
  const sw = ((hit[2] - hit[0]) / (e - w)) * img.width;
  const sh = ((hit[3] - hit[1]) / (n - s)) * img.height;
  const width = Math.max(1, Math.round(sw));
  const height = Math.max(1, Math.round(sh));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, width, height);
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) return null;
  return new File([blob], `${demo.id}-crop.png`, { type: "image/png" });
}
