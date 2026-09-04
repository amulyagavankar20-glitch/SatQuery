export const OFFICIAL_CHIPS = [
  "Describe land-cover and major objects",
  "Highlight the water body",
  "What changed between these two dates, and where?",
  "Use optical and SAR together for built-up and water",
  "Has built-up increased, decreased, or stayed the same?",
] as const;

export const LAYER_LABELS: { id: "optical" | "sar" | "change" | "uncertain"; label: string }[] = [
  { id: "optical", label: "Optical" },
  { id: "sar", label: "SAR" },
  { id: "change", label: "Change" },
  { id: "uncertain", label: "Uncertain" },
];

export const DEFAULT_LAYERS = {
  optical: true,
  sar: true,
  change: true,
  uncertain: true,
} as const;

export const JOBS_STORAGE_KEY = "satquery.jobs.v1";
export const MAX_JOBS = 16;
