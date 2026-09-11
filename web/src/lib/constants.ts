import type { SceneSlot } from "./types";

export function getSuggestedQuestions(slots: SceneSlot[], activeSlot: "T1" | "T2" = "T1"): string[] {
  const t1 = slots.find((s) => s.slot === "T1") ?? slots[0];
  const t2 = slots.find((s) => s.slot === "T2");
  const hasPair = Boolean(t1 && t2);
  const activeObj = (activeSlot === "T2" && t2) ? t2 : t1;

  if (hasPair) {
    const isTemporal = t1?.modality === t2?.modality;
    if (isTemporal) {
      return [
        "What changed between T1 and T2?",
        "Describe the major changes between the two images",
        "Compare the built-up areas between T1 and T2",
        "Has built-up increased, decreased, or stayed the same?",
        "Highlight the water body",
      ];
    } else {
      return [
        "Use optical and SAR together for built-up and water",
        "Compare optical surface features with radar backscatter",
        "Describe land-cover and major objects",
        "Highlight the water body",
      ];
    }
  }

  if (activeObj?.modality === "SAR") {
    return [
      "What objects are visible in this SAR image?",
      "Describe the land cover and major objects",
      "Analyze radar backscatter and surface roughness",
      "Describe this SAR scene",
      "Highlight the water body",
    ];
  }

  return [
    "What objects are visible in this optical image?",
    "Describe the land cover and major objects",
    "Describe this optical scene",
    "Highlight the urban area",
    "Highlight the water body",
    "Highlight the vegetation",
  ];
}

export const OFFICIAL_CHIPS = [
  "What objects are visible in this optical image?",
  "Describe the land cover and major objects",
  "Describe this optical scene",
  "Highlight the urban area",
  "Highlight the water body",
  "What changed between T1 and T2?",
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
