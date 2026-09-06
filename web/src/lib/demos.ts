import type { BBox, DemoId, SceneSlot } from "./types";

export type DemoScene = {
  id: DemoId;
  title: string;
  blurb: string;
  place: string;
  thumb: string;
  pairFitness: number | null;
  slots: Omit<SceneSlot, "id" | "file">[];
};

const WATER_BOUNDS: BBox = [72.042, 22.781, 72.158, 22.879];
const COASTAL_BOUNDS: BBox = [69.684, 22.802, 69.796, 22.894];
const CLOUDY_BOUNDS: BBox = [70.086, 22.404, 70.214, 22.508];

export const DEMOS: DemoScene[] = [
  {
    id: "water",
    title: "Water",
    blurb: "Reservoir, fields, a small settlement.",
    place: "Inland Gujarat",
    thumb: "/demos/water.jpg",
    pairFitness: null,
    slots: [
      {
        slot: "T1",
        filename: "cartosat2s_nal_t1.tif",
        modality: "OPTICAL",
        sensor: "Cartosat-2S",
        crs: "EPSG:32643",
        date: "2023-11-14",
        bands: 4,
        bounds: WATER_BOUNDS,
        previewUrl: "/demos/water.jpg",
      },
    ],
  },
  {
    id: "coastal",
    title: "Coastal built-up",
    blurb: "Port pair, two dates.",
    place: "Gulf of Kachchh",
    thumb: "/demos/coastal-t2.jpg",
    pairFitness: 0.91,
    slots: [
      {
        slot: "T1",
        filename: "cartosat2s_port_2022.tif",
        modality: "OPTICAL",
        sensor: "Cartosat-2S",
        crs: "EPSG:32642",
        date: "2022-03-08",
        bands: 4,
        bounds: COASTAL_BOUNDS,
        previewUrl: "/demos/coastal-t1.jpg",
      },
      {
        slot: "T2",
        filename: "cartosat2s_port_2024.tif",
        modality: "OPTICAL",
        sensor: "Cartosat-2S",
        crs: "EPSG:32642",
        date: "2024-02-21",
        bands: 4,
        bounds: COASTAL_BOUNDS,
        previewUrl: "/demos/coastal-t2.jpg",
      },
    ],
  },
  {
    id: "cloudy",
    title: "Cloudy optical+SAR",
    blurb: "Cloud in optical, SAR underneath.",
    place: "Saurashtra coast",
    thumb: "/demos/cloudy.jpg",
    pairFitness: 0.91,
    slots: [
      {
        slot: "T1",
        filename: "cartosat2s_coast_cloud.tif",
        modality: "OPTICAL",
        sensor: "Cartosat-2S",
        crs: "EPSG:32642",
        date: "2024-07-03",
        bands: 4,
        bounds: CLOUDY_BOUNDS,
        previewUrl: "/demos/cloudy.jpg",
      },
      {
        slot: "T2",
        filename: "risat_coast_s1.tif",
        modality: "SAR",
        sensor: "RISAT",
        crs: "EPSG:32642",
        date: "2024-07-03",
        bands: 1,
        bounds: CLOUDY_BOUNDS,
        previewUrl: "/demos/sar.jpg",
      },
    ],
  },
];

export function isDemoId(value: unknown): value is DemoId {
  return value === "water" || value === "coastal" || value === "cloudy";
}

export function demoById(id: DemoId): DemoScene {
  const found = DEMOS.find((d) => d.id === id);
  if (!found) throw new Error(`Unknown demo: ${id}`);
  return found;
}
