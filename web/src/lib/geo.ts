import type { BBox } from "./types";
import type { DemoScene } from "./demos";

export const DEFAULT_WGS84_BOUNDS: BBox = [72.5, 23.0, 72.7, 23.2];

export function sanitizeBounds(raw: unknown): BBox {
  if (!Array.isArray(raw) || raw.length !== 4) return DEFAULT_WGS84_BOUNDS;
  let [w, s, e, n] = raw.map(Number);
  if (isNaN(w) || isNaN(s) || isNaN(e) || isNaN(n)) return DEFAULT_WGS84_BOUNDS;

  if (w > e) [w, e] = [e, w];
  if (s > n) [s, n] = [n, s];

  // If projected coordinates (UTM meters), fallback to safe WGS84
  if (Math.abs(w) > 180 || Math.abs(e) > 180 || Math.abs(s) > 90 || Math.abs(n) > 90) {
    return DEFAULT_WGS84_BOUNDS;
  }

  w = Math.max(-180, Math.min(180, w));
  e = Math.max(-180, Math.min(180, e));
  s = Math.max(-85.051129, Math.min(85.051129, s));
  n = Math.max(-85.051129, Math.min(85.051129, n));

  if (w === e) {
    w -= 0.05;
    e += 0.05;
  }
  if (s === n) {
    s -= 0.05;
    n += 0.05;
  }

  return [w, s, e, n];
}

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

export function bestSceneForBox(
  demos: DemoScene[],
  box: BBox,
  fallbackDemo?: DemoScene,
): { demo: DemoScene; hit: BBox; coverage: number } {
  let best: { demo: DemoScene; hit: BBox; coverage: number } | null = null;
  for (const demo of demos) {
    const hit = intersectBBox(box, demo.slots[0]!.bounds);
    if (!hit) continue;
    const coverage = bboxArea(hit) / bboxArea(demo.slots[0]!.bounds);
    if (!best || bboxArea(hit) > bboxArea(best.hit)) best = { demo, hit, coverage };
  }
  if (best) return best;

  // If no direct intersection, pick the closest scene to the box center
  const [bw, bs, be, bn] = sanitizeBounds(box);
  const bcx = (bw + be) / 2;
  const bcy = (bs + bn) / 2;

  let closest = fallbackDemo ?? demos[0]!;
  let minDist = Infinity;
  for (const demo of demos) {
    const [sw, ss, se, sn] = demo.slots[0]!.bounds;
    const scx = (sw + se) / 2;
    const scy = (ss + sn) / 2;
    const dist = (bcx - scx) ** 2 + (bcy - scy) ** 2;
    if (dist < minDist) {
      minDist = dist;
      closest = demo;
    }
  }

  return { demo: closest, hit: [bw, bs, be, bn], coverage: 0.5 };
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
  const hit = intersectBBox(scene, crop) ?? crop;
  const img = await loadImage(demo.thumb);
  const [w, s, e, n] = scene;

  const minX = Math.min(hit[0], hit[2]);
  const maxX = Math.max(hit[0], hit[2]);
  const minY = Math.min(hit[1], hit[3]);
  const maxY = Math.max(hit[1], hit[3]);

  let sx = ((minX - w) / Math.max(1e-6, e - w)) * img.width;
  let sy = ((n - maxY) / Math.max(1e-6, n - s)) * img.height;
  let sw = ((maxX - minX) / Math.max(1e-6, e - w)) * img.width;
  let sh = ((maxY - minY) / Math.max(1e-6, n - s)) * img.height;

  if (sw <= 0 || isNaN(sw)) sw = img.width;
  if (sh <= 0 || isNaN(sh)) sh = img.height;

  // Clamp crop rectangle to valid image boundaries
  sx = Math.max(0, Math.min(img.width - 16, sx));
  sy = Math.max(0, Math.min(img.height - 16, sy));
  sw = Math.max(16, Math.min(img.width - sx, sw));
  sh = Math.max(16, Math.min(img.height - sy, sh));

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

export async function fetchAoiSnippet(
  bounds: BBox,
  map?: maplibregl.Map | null,
): Promise<{ file: File; previewUrl: string } | { file: null; previewUrl: null }> {
  const [w, s, e, n] = sanitizeBounds(bounds);
  const width = 640;
  const height = 640;

  // 1. Fetch real satellite imagery snippet from ArcGIS World Imagery export service
  try {
    const exportUrl = `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export?bbox=${w},${s},${e},${n}&bboxSR=4326&imageSR=4326&size=${width},${height}&f=image`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 7000);
    const res = await fetch(exportUrl, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (res.ok) {
      const blob = await res.blob();
      if (blob.size > 1000) {
        const filename = `aoi_${w.toFixed(4)}_${s.toFixed(4)}_${e.toFixed(4)}_${n.toFixed(4)}.png`;
        const file = new File([blob], filename, { type: "image/png" });
        const previewUrl = URL.createObjectURL(blob);
        return { file, previewUrl };
      }
    }
  } catch (err) {
    console.warn("ArcGIS export imagery fetch error:", err);
  }

  // 2. Fallback: Extract directly from rendered MapLibre canvas if available
  if (map) {
    try {
      const p1 = map.project([w, n]);
      const p2 = map.project([e, s]);
      const minX = Math.max(0, Math.min(p1.x, p2.x));
      const minY = Math.max(0, Math.min(p1.y, p2.y));
      const cropW = Math.max(16, Math.abs(p2.x - p1.x));
      const cropH = Math.max(16, Math.abs(p2.y - p1.y));

      const mapCanvas = map.getCanvas();
      const canvas = document.createElement("canvas");
      canvas.width = Math.min(1024, Math.round(cropW));
      canvas.height = Math.min(1024, Math.round(cropH));
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.drawImage(mapCanvas, minX, minY, cropW, cropH, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
        if (blob) {
          const filename = `aoi_${w.toFixed(4)}_${s.toFixed(4)}_${e.toFixed(4)}_${n.toFixed(4)}.png`;
          const file = new File([blob], filename, { type: "image/png" });
          const previewUrl = URL.createObjectURL(blob);
          return { file, previewUrl };
        }
      }
    } catch (err) {
      console.warn("Canvas capture fallback error:", err);
    }
  }

  // 3. Fallback: Generate a crisp raster canvas
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#16202c";
    ctx.fillRect(0, 0, 512, 512);
    ctx.fillStyle = "#38bdf8";
    ctx.font = "16px monospace";
    ctx.fillText(`AOI: [${w.toFixed(3)}, ${s.toFixed(3)}, ${e.toFixed(3)}, ${n.toFixed(3)}]`, 24, 60);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (blob) {
      const filename = `aoi_${w.toFixed(4)}_${s.toFixed(4)}_${e.toFixed(4)}_${n.toFixed(4)}.png`;
      const file = new File([blob], filename, { type: "image/png" });
      const previewUrl = URL.createObjectURL(blob);
      return { file, previewUrl };
    }
  }

  return { file: null, previewUrl: null };
}

