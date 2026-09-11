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
          [0.0, 0.16, 0.36, 0.46, 0.54, 0.52, 0.42, 0.2, 0.04, 0.0],
          [0.18, 0.1, 0.14, 0.26, 0.48, 0.68, 0.86, 0.94, 0.76, 0.46],
          "water-1",
          "change",
          "water",
        ),
        poly(bounds, [0.02, 0.2, 0.22, 0.04], [0.08, 0.06, 0.2, 0.24], "flood-1", "change", "flooded_vegetation"),
        poly(bounds, [0.56, 0.74, 0.74, 0.56], [0.6, 0.6, 0.78, 0.78], "tank-1", "change", "water"),
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
  return {
    type: "FeatureCollection",
    features: [
      poly(bounds, [0.42, 0.58, 0.61, 0.44], [0.62, 0.59, 0.44, 0.45], "chg-1", "change", "change"),
      poly(bounds, [0.62, 0.78, 0.81, 0.64], [0.82, 0.8, 0.64, 0.66], "chg-2", "change", "change"),
      poly(bounds, [0.22, 0.36, 0.38, 0.24], [0.38, 0.36, 0.22, 0.24], "unc-1", "uncertain", "uncertain"),
    ],
  };
}

function mockLulc(query: string, slots: SceneSlot[]): LulcReport | undefined {
  const q = query.toLowerCase();
  const id = `${slots[0]?.filename ?? ""} ${query}`;
  const coastal = /port|coast|harbour|harbor|marine/.test(id.toLowerCase());
  const cloudy = id.toLowerCase().includes("cloud") || slots.some((s) => s.modality === "SAR");
  if (
    !(
      q.includes("water") ||
      q.includes("flood") ||
      q.includes("land-cover") ||
      q.includes("vegetation") ||
      q.includes("objects") ||
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
          water: 0.18,
          trees: 0.02,
          grass: 0.1,
          flooded_vegetation: 0.04,
          crops: 0.08,
          shrub_and_scrub: 0.06,
          built: 0.32,
          bare: 0.2,
          snow_and_ice: 0,
        }
      : {
          water: 0.38,
          trees: 0.03,
          grass: 0.08,
          flooded_vegetation: 0.05,
          crops: 0.22,
          shrub_and_scrub: 0.03,
          built: 0.08,
          bare: 0.13,
          snow_and_ice: 0,
        };
  const focus = q.includes("flood")
    ? "flood"
    : q.includes("water")
      ? "water"
      : q.includes("vegetat")
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
  const inputClass = slots.length < 2 ? "SINGLE_OPTICAL" : slots.some((s) => s.modality === "SAR") ? "OPTICAL_SAR" : "BI_TEMPORAL";
  const q = query.toLowerCase();
  const gate: TraceStep = { tool: "gate", params: { valid: true, input_class: inputClass } };

  if (
    q.includes("water body") ||
    q.includes("highlight the water") ||
    q.includes("flood") ||
    q.includes("land-cover") ||
    q.includes("vegetation") ||
    q.includes("objects")
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
          scene_tags: "bigearthnet_19_taxonomy",
        },
      },
      { tool: "geochat_vqa", params: { phrase: "land cover" } },
      { tool: "grounding", params: { method: "vectorize" } },
    ];
  }
  if ((q.includes("optical") && q.includes("sar")) || (slots.some((s) => s.modality === "SAR") && q.includes("sar"))) {
    return [
      gate,
      { tool: "router", params: { task: "ANALYSIS", specialist: "optical_sar" } },
      { tool: "preprocess", params: { coregister: true } },
      { tool: "evidence_fusion", params: { agree: true } },
    ];
  }
  if (q.includes("changed") || q.includes("increased") || q.includes("decreased") || slots.length > 1) {
    return [
      gate,
      { tool: "router", params: { task: "CHANGE_VQA", specialist: "change_detection" } },
      { tool: "align", params: { pair_fitness: 0.91 } },
      { tool: "bit_cd", params: { pair_fitness: 0.91 } },
      { tool: "vectorize", params: {} },
      { tool: "geochat_describe", params: { overlay: true } },
    ];
  }
  return [
    gate,
    { tool: "router", params: { task: "CAPTIONING", specialist: "describe" } },
    { tool: "geochat_describe", params: {} },
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

  if (q.includes("water body") || q.includes("highlight the water") || q.includes("flood")) {
    return "A single contiguous water body occupies the western basin. The shoreline is sharp along the cut bank and irregular where fields wet. Two small farm tanks sit east of the water; they are not a second lake.";
  }
  if (q.includes("land-cover") || q.includes("vegetation") || q.includes("objects")) {
    return "Open water takes the western third. Irrigated and fallow plots fill the east, cut by pale tracks. A compact settlement sits on the terrace above the water; two farm tanks sit south of the houses.";
  }
  if (q.includes("increased") || q.includes("decreased") || q.includes("stayed the same")) {
    return "Built-up has increased. The net change sits in two blocks east of the harbour and a thinner strip along the highway. No comparable decrease is detected. One polygon remains uncertain under residual cloud, so confidence is medium.";
  }
  if (q.includes("optical") && q.includes("sar")) {
    return "Optical holds the cloud-free gaps; SAR carries the rest. Built-up is bright in SAR and confirmed where optical is clear. Water is dark in SAR and meets the optical shoreline. Agreement is high over the port and the lagoon; the clouded inland strip is SAR only.";
  }
  if (q.includes("changed") || q.includes("where") || pair) {
    return "Between the two dates, built-up expanded along the access road and at the port apron. Two change polygons mark new roof clusters and filled land; one uncertain patch sits under residual cloud. Water extent is stable within the intertidal margin.";
  }
  if (hasSar) {
    return "SAR fills the clouded optical. Bright returns mark built-up; dark returns mark water. Where both are clear they agree. The uncertain polygon is the remaining cloud edge.";
  }
  return "The scene is a mixed rural frame: open water, small built-up, and agricultural plots. Evidence polygons mark the principal change and one uncertain patch. Confidence is medium.";
}

export function mockAssistantTurn(query: string, slots: SceneSlot[]): Omit<AssistantTurn, "id"> {
  const optical = slots.find((s) => s.modality === "OPTICAL");
  const sar = slots.find((s) => s.modality === "SAR");
  const bounds = optical?.bounds ?? slots[0]!.bounds;
  const inputClass =
    slots.length < 2 ? "SINGLE_OPTICAL" : sar ? "OPTICAL_SAR" : "BI_TEMPORAL";
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
