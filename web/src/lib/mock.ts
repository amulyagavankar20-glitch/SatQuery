import type { AssistantTurn, BBox, OverlayCollection, SceneSlot, TraceStep } from "./types";

function ring(bounds: BBox, xs: number[], ys: number[]): number[][] {
  const [w, s, e, n] = bounds;
  const dx = e - w;
  const dy = n - s;
  const coords = xs.map((x, i) => [w + dx * x, s + dy * ys[i]]);
  coords.push(coords[0]);
  return coords;
}

export function mockOverlays(bounds: BBox): OverlayCollection {
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { id: "chg-1", kind: "change" },
        geometry: {
          type: "Polygon",
          coordinates: [ring(bounds, [0.42, 0.58, 0.61, 0.44], [0.38, 0.41, 0.56, 0.55])],
        },
      },
      {
        type: "Feature",
        properties: { id: "chg-2", kind: "change" },
        geometry: {
          type: "Polygon",
          coordinates: [ring(bounds, [0.62, 0.78, 0.81, 0.64], [0.18, 0.2, 0.36, 0.34])],
        },
      },
      {
        type: "Feature",
        properties: { id: "unc-1", kind: "uncertain" },
        geometry: {
          type: "Polygon",
          coordinates: [ring(bounds, [0.22, 0.36, 0.38, 0.24], [0.62, 0.64, 0.78, 0.76])],
        },
      },
    ],
  };
}

export const MOCK_TRACE: TraceStep[] = [
  { tool: "gate", params: { valid: true, input_class: "BI_TEMPORAL" } },
  { tool: "router", params: { task: "CHANGE_VQA", need_overlay: true } },
  { tool: "bit_cd", params: { pair_fitness: 0.91 } },
  { tool: "geochat_describe", params: { overlay: true } },
];

function answerFor(query: string, slots: SceneSlot[]): string {
  const q = query.toLowerCase();
  const hasSar = slots.some((s) => s.modality === "SAR");
  const pair = slots.length > 1;

  if (q.includes("water body") || q.includes("highlight the water")) {
    return "A single contiguous water body occupies the western basin. The shoreline is sharp along the cut bank and irregular where fields flood. No second pond of comparable size is visible in this frame.";
  }
  if (q.includes("land-cover") || q.includes("major objects")) {
    return "Open water takes the western third. Irrigated and fallow plots fill the east, cut by pale tracks. A compact settlement sits on the terrace above the water; two farm tanks sit south of the houses. Cloud is absent over the basin.";
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
    overlays: mockOverlays(bounds),
    trace: MOCK_TRACE.map((step, i) =>
      i === 0 ? { ...step, params: { ...step.params, input_class: inputClass } } : step,
    ),
  };
}
