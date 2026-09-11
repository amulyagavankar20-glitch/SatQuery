import { OFFICIAL_CHIPS } from "./constants";
import type { TraceStep } from "./types";

export function specialistId(query: string, sar: boolean): string {
  const q = query.toLowerCase();
  if (sar || q.includes("sar") || q.includes("sentinel-1") || q.includes("radar")) return "sarchat_vqa";
  if (q.includes("flood") || q.includes("inundat") || q.includes("high-water") || q.includes("high water")) return "lulc_map";
  if (q.includes("water body") || q.includes("highlight the water")) return "lulc_map";
  if (q.includes("land-cover") || q.includes("vegetation") || q.includes("built-up") || q.includes("objects")) return "lulc_map";
  if (q.includes("increased") || q.includes("decreased") || q.includes("stayed the same")) return "change_detection";
  if (q.includes("changed") || q.includes("where?")) return "change_detection";
  return "describe";
}

export function routingSteps(query: string, sar: boolean): string[] {
  return ["ROUTING", `SELECTING SPECIALIST: ${specialistId(query, sar).toUpperCase()}`, "SEGMENTING PIXELS"];
}

export function thinkingSteps(query: string, pair: boolean, sar: boolean): string[] {
  return routingSteps(query, sar || pair);
}

function firstParam(step: TraceStep): string | null {
  for (const [key, value] of Object.entries(step.params)) {
    if (key === "event" || key === "message" || key === "summary" || value == null || value === true) continue;
    if (typeof value === "string" || typeof value === "number") return String(value);
  }
  return null;
}

export function formatTraceStep(step: TraceStep): string {
  const summary = step.params.summary;
  if (typeof summary === "string" && summary) return `${step.tool}: ${summary}`;
  const value = firstParam(step);
  return value ? `${step.tool}: ${value}` : step.tool;
}

export function formatTraceChain(steps: TraceStep[], confidence?: string | null): string {
  const parts = steps.map(formatTraceStep);
  if (confidence) parts.push(`confidence ${confidence.toLowerCase()}`);
  return parts.join(" -> ");
}

export function followUpQuestions(lastQuery: string): string[] {
  return OFFICIAL_CHIPS.filter((chip) => chip !== lastQuery).slice(0, 3);
}
