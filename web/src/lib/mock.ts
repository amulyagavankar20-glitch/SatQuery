import type { AssistantTurn, BBox, LulcReport, OverlayCollection, SceneSlot, TraceStep } from "./types";

/** Image y grows down; geographic y grows north. xs/ys are normalized image coords. */
function ring(bounds: BBox, xs: number[], ys: number[]): number[][] {
  const [w, s, e, n] = bounds;
  const dx = e - w;
  const dy = n - s;
  const coords = xs.map((x, i) => [w + dx * x, n - dy * ys[i]!]);
  coords.push(coords[0]!);
  return coords;
}

function poly(bounds: BBox, xs: number[], ys: number[], id: string, kind: "change" | "uncertain", cls: string) {
  return {
    type: "Feature" as const,
    properties: { id, kind, class: cls, label: cls.replaceAll("_", " ") },
    geometry: { type: "Polygon" as const, coordinates: [ring(bounds, xs, ys)] },
  };
}

const DW_TO_BEN: Record<string, [string, number][]> = {
  water: [["Inland waters", 1.0]],
  trees: [
    ["Broad-leaved forest", 0.4],
    ["Mixed forest", 0.35],
    ["Coniferous forest", 0.25],
  ],
  grass: [
    ["Pastures", 0.55],
    ["Natural grassland and sparsely vegetated areas", 0.45],
  ],
  flooded_vegetation: [
    ["Inland wetlands", 0.7],
    ["Coastal wetlands", 0.3],
  ],
  crops: [
    ["Arable land", 0.55],
    ["Permanent crops", 0.2],
    ["Complex cultivation patterns", 0.25],
  ],
  shrub_and_scrub: [
    ["Transitional woodland, shrub", 0.55],
    ["Moors, heathland and sclerophyllous vegetation", 0.45],
  ],
  built: [
    ["Urban fabric", 0.55],
    ["Industrial or commercial units", 0.45],
  ],
  bare: [
    ["Beaches, dunes, sands", 0.45],
    ["Natural grassland and sparsely vegetated areas", 0.55],
  ],
  snow_and_ice: [["Natural grassland and sparsely vegetated areas", 1.0]],
};

function sceneTagsFromFractions(fractions: Record<string, number>, coastal = false): LulcReport["sceneTags"] {
  const mapping = { ...DW_TO_BEN };
  if (coastal) {
    mapping.water = [
      ["Marine waters", 0.75],
      ["Inland waters", 0.25],
    ];
  }
  const scores: Record<string, number> = {};
  for (const [dw, share] of Object.entries(fractions)) {
    for (const [name, weight] of mapping[dw] ?? []) {
      scores[name] = (scores[name] ?? 0) + share * weight;
    }
  }
  return Object.entries(scores)
    .filter(([, score]) => score >= 0.04)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([name, score]) => ({ name, score: Math.round(score * 1000) / 1000 }));
}

export function mockOverlays(bounds: BBox, query = ""): OverlayCollection {
  const q = query.toLowerCase();
  if (q.includes("water body") || q.includes("highlight the water") || q.includes("flood")) {
    return {
      type: "FeatureCollection",
      features: [
        poly(
          bounds,
          [0.1, 0.26, 0.36, 0.46, 0.54, 0.52, 0.42, 0.2, 0.14, 0.1],
          [0.18, 0.1, 0.14, 0.26, 0.48, 0.68, 0.86, 0.94, 0.76, 0.46],
          "water-1",
          "change",
          "water",
        ),
      ],
    };
  }
  if (q.includes("land-cover") || q.includes("vegetation") || q.includes("objects")) {
    return {
      type: "FeatureCollection",
      features: [
        poly(
          bounds,
          [0.0, 0.16, 0.36, 0.46, 0.54, 0.52, 0.42, 0.2, 0.04, 0.0],
          [0.18, 0.1, 0.14, 0.26, 0.48, 0.68, 0.86, 0.94, 0.76, 0.46],
          "water-1",
          "change",
          "water",
        ),
        poly(bounds, [0.54, 0.74, 0.76, 0.54], [0.36, 0.36, 0.58, 0.58], "built-1", "uncertain", "built"),
        poly(bounds, [0.56, 0.98, 0.98, 0.62], [0.02, 0.02, 0.36, 0.38], "crops-1", "uncertain", "crops"),
      ],
    };
  }
  if (q.includes("changed") || q.includes("difference") || q.includes("increased") || q.includes("decreased")) {
    return {
      type: "FeatureCollection",
      features: [
        poly(bounds, [0.42, 0.58, 0.61, 0.44], [0.62, 0.59, 0.44, 0.45], "chg-1", "change", "change"),
        poly(bounds, [0.62, 0.78, 0.81, 0.64], [0.82, 0.8, 0.64, 0.66], "chg-2", "change", "change"),
        poly(bounds, [0.22, 0.36, 0.38, 0.24], [0.38, 0.36, 0.22, 0.24], "unc-1", "uncertain", "uncertain"),
      ],
    };
  }
  return {
    type: "FeatureCollection",
    features: [],
  };
}

function mockLulc(query: string, slots: SceneSlot[]): LulcReport | undefined {
  const q = query.toLowerCase();
  // Don't trigger optical LULC for SAR queries
  if (q.includes("sar") || q.includes("radar") || slots.every((s) => s.modality === "SAR")) {
    return undefined;
  }
  const id = `${slots[0]?.filename ?? ""} ${query}`;
  const coastal = /port|coast|harbour|harbor|marine/.test(id.toLowerCase());
  const cloudy = id.toLowerCase().includes("cloud");
  if (
    !(
      q.includes("water") ||
      q.includes("flood") ||
      q.includes("land-cover") ||
      q.includes("vegetation") ||
      q.includes("built")
    )
  ) {
    return undefined;
  }
  const fractions = cloudy
    ? {
        water: 0.08,
        trees: 0.06,
        grass: 0.16,
        flooded_vegetation: 0.04,
        crops: 0.2,
        shrub_and_scrub: 0.08,
        built: 0.14,
        bare: 0.12,
        snow_and_ice: 0.12,
      }
    : coastal
      ? {
          water: 0.44,
          trees: 0.04,
          grass: 0.05,
          flooded_vegetation: 0.08,
          crops: 0.04,
          shrub_and_scrub: 0.02,
          built: 0.24,
          bare: 0.09,
          snow_and_ice: 0.0,
        }
      : {
          water: 0.26,
          trees: 0.12,
          grass: 0.14,
          flooded_vegetation: 0.03,
          crops: 0.21,
          shrub_and_scrub: 0.06,
          built: 0.12,
          bare: 0.06,
          snow_and_ice: 0.0,
        };
  const focus: LulcReport["focus"] =
    q.includes("flood")
      ? "flood"
      : q.includes("water")
        ? "water"
        : q.includes("built")
          ? "built"
          : q.includes("vegetation") || q.includes("tree") || q.includes("crop")
            ? "vegetation"
            : "land_cover";
  return {
    backend: "spectral_fallback",
    focus,
    fractions,
    sceneTags: sceneTagsFromFractions(fractions, coastal),
  };
}

function mockTrace(query: string, slots: SceneSlot[]): TraceStep[] {
  const isSar = slots.some((s) => s.modality === "SAR");
  const inputClass = slots.length < 2 ? (isSar ? "SINGLE_SAR" : "SINGLE_OPTICAL") : isSar ? "OPTICAL_SAR" : "BI_TEMPORAL";
  const q = query.toLowerCase();
  const gate: TraceStep = { tool: "gate", params: { valid: true, input_class: inputClass } };

  if (isSar || q.includes("sar") || q.includes("radar")) {
    return [
      gate,
      { tool: "router", params: { task: "SINGLE_VQA", specialist: "sar_map" } },
      {
        tool: "sar_map",
        params: {
          backend: "reben_s1_resnet50",
          model: "BIFOLD-BigEarthNetv2-0/resnet50-s1-v0.2.0",
        },
      },
      { tool: "evidence_fusion", params: { fused: true } },
    ];
  }

  if (
    q.includes("water body") ||
    q.includes("highlight the water") ||
    q.includes("flood") ||
    q.includes("land-cover") ||
    q.includes("vegetation")
  ) {
    return [
      gate,
      { tool: "router", params: { task: "GROUNDING", specialist: "lulc_map" } },
      {
        tool: "lulc_map",
        params: {
          summary: "spectral_fallback · DW 9-class names · BEN-19 tags",
          backend: "spectral_fallback",
          class_set: "dynamic_world_9class",
        },
      },
      { tool: "evidence_fusion", params: { fused: true } },
    ];
  }
  if ((q.includes("optical") && q.includes("sar")) || (slots.some((s) => s.modality === "SAR") && q.includes("sar"))) {
    return [
      gate,
      { tool: "router", params: { task: "OPTICAL_SAR_ANALYSIS", specialist: "fusion_s1s2" } },
      { tool: "preprocess", params: { coregister: true } },
      { tool: "evidence_fusion", params: { agree: true } },
    ];
  }
  if (q.includes("changed") || q.includes("increased") || q.includes("decreased") || slots.length > 1) {
    return [
      gate,
      { tool: "router", params: { task: "CHANGE_VQA", specialist: "bit_cd" } },
      { tool: "align", params: { pair_fitness: 0.91 } },
      { tool: "bit_cd", params: { pair_fitness: 0.91 } },
      { tool: "vectorize", params: {} },
    ];
  }
  return [
    gate,
    { tool: "router", params: { task: "CAPTIONING", specialist: "lulc_map" } },
    { tool: "lulc_map", params: {} },
    { tool: "evidence_fusion", params: { fused: true } },
  ];
}

export const MOCK_TRACE: TraceStep[] = mockTrace("What changed between these two dates, and where?", [
  { id: "t1", slot: "T1", filename: "t1.tif", modality: "OPTICAL", sensor: "Cartosat-2S", crs: "EPSG:4326", date: null, bands: 4, bounds: [0, 0, 1, 1], previewUrl: "" },
  { id: "t2", slot: "T2", filename: "t2.tif", modality: "OPTICAL", sensor: "Cartosat-2S", crs: "EPSG:4326", date: null, bands: 4, bounds: [0, 0, 1, 1], previewUrl: "" },
]);

function answerFor(query: string, slots: SceneSlot[]): string {
  const q = query.toLowerCase();
  const hasSar = slots.some((s) => s.modality === "SAR");
  const pair = slots.length > 1;

  if (hasSar || q.includes("sar") || q.includes("radar")) {
    return "**SAR Scene Interpretation & Classification** (reBEN ResNet50 · Sentinel-1 S1)\n\n" +
      "**Radiometric Distribution:** Built-up 24% · water 36% · vegetation 28% · other 12% (Mean VV: -12.4 dB / VH: -19.8 dB).\n\n" +
      "**Scene Classification Tags:** Marine waters (88%) · Urban fabric (72%) · Pastures (46%).\n\n" +
      "Radar backscatter indicates open water in low-return areas and dense structural features in high-return clusters.";
  }
  if (q.includes("water body") || q.includes("highlight the water") || q.includes("flood")) {
    return "A single contiguous water body occupies the western basin. The shoreline is sharp along the cut bank and irregular where fields wet. Two small farm tanks sit east of the water.";
  }
  if (q.includes("land-cover") || q.includes("vegetation")) {
    return "Open water takes the western third. Irrigated and fallow plots fill the east, cut by pale tracks. A compact settlement sits on the terrace above the water.";
  }
  if (q.includes("increased") || q.includes("decreased") || q.includes("stayed the same")) {
    return "Built-up has increased. The net change sits in two blocks east of the harbour and a thinner strip along the highway. No comparable decrease is detected.";
  }
  if (q.includes("optical") && q.includes("sar")) {
    return "Optical holds the cloud-free gaps; SAR carries the rest. Built-up is bright in SAR and confirmed where optical is clear. Water is dark in SAR and meets the optical shoreline.";
  }
  if (q.includes("changed") || q.includes("where") || pair) {
    return "Between the two dates, built-up expanded along the access road and at the port apron. Water extent is stable within the intertidal margin.";
  }
  return "The scene is a mixed rural frame: open water, small built-up, and agricultural plots. Confidence is medium.";
}

export function mockAssistantTurn(query: string, slots: SceneSlot[]): Omit<AssistantTurn, "id"> {
  const q = query.toLowerCase();
  const optical = slots.find((s) => s.modality === "OPTICAL");
  const sar = slots.find((s) => s.modality === "SAR");
  const bounds = optical?.bounds ?? sar?.bounds ?? slots[0]?.bounds ?? [72.5, 23.0, 72.7, 23.2];
  const isSarQuery = q.includes("sar") || q.includes("radar");
  const isOpticalOnly = slots.length > 0 && slots.every((s) => s.modality === "OPTICAL");

  if (isSarQuery && isOpticalOnly) {
    return {
      role: "assistant",
      status: "failed",
      error: `Modality Mismatch: The query explicitly requested SAR/radar analysis ('${query}'), but the provided asset is optical. Please provide a SAR image (Sentinel-1) or adjust your query for optical analysis.`,
      answer: `Modality Mismatch: The query explicitly requested SAR/radar analysis ('${query}'), but the provided asset is optical. Please provide a SAR image (Sentinel-1) or adjust your query for optical analysis.`,
      confidence: "Low",
      jobId: crypto.randomUUID(),
      bounds,
      opticalUrl: optical?.previewUrl ?? null,
      sarUrl: null,
      compareUrl: null,
      overlays: { type: "FeatureCollection", features: [] },
      trace: [
        { tool: "input_validator", params: { status: "refused", reason: "Modality mismatch" } },
      ],
    };
  }

  const inputClass =
    slots.length < 2 ? (sar ? "SINGLE_SAR" : "SINGLE_OPTICAL") : sar ? "OPTICAL_SAR" : "BI_TEMPORAL";
  const lulc = mockLulc(query, slots);

  return {
    role: "assistant",
    status: "completed",
    answer: answerFor(query, slots),
    confidence: "Medium",
    jobId: crypto.randomUUID(),
    bounds,
    opticalUrl: optical?.previewUrl ?? slots[0]?.previewUrl ?? null,
    sarUrl: sar?.previewUrl ?? null,
    compareUrl:
      slots.find((s) => s.slot === "T2" && s.modality === "OPTICAL" && s.previewUrl !== optical?.previewUrl)
        ?.previewUrl ?? null,
    overlays: mockOverlays(bounds, query),
    lulc,
    trace: mockTrace(query, slots).map((step, i) =>
      i === 0 ? { ...step, params: { ...step.params, input_class: inputClass } } : step,
    ),
  };
}
