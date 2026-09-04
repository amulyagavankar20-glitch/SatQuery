import { OFFICIAL_CHIPS } from "./constants";

export function thinkingSteps(query: string, pair: boolean, sar: boolean): string[] {
  const q = query.toLowerCase();
  if (q.includes("water body") || q.includes("highlight the water")) {
    return ["Opening the raster", "Finding open water", "Tracing the shoreline", "Writing the answer"];
  }
  if (q.includes("increased") || q.includes("decreased") || q.includes("stayed the same")) {
    return ["Reading both dates", "Comparing built-up", "Measuring the net", "Writing the answer"];
  }
  if (q.includes("changed") || q.includes("where?")) {
    return ["Reading the pair", "Checking alignment", "Finding what moved", "Drawing the polygons", "Writing the answer"];
  }
  if ((q.includes("optical") && q.includes("sar")) || sar) {
    return ["Reading the optical", "Reading the SAR", "Agreeing on built-up and water", "Writing the answer"];
  }
  if (q.includes("land-cover") || q.includes("objects")) {
    return ["Opening the raster", "Sorting cover classes", "Noting major objects", "Writing the answer"];
  }
  if (pair) {
    return ["Reading the pair", "Routing the question", "Asking the specialist", "Writing the answer"];
  }
  return ["Reading the scene", "Routing the question", "Asking the specialist", "Writing the answer"];
}

export function followUpQuestions(lastQuery: string): string[] {
  return OFFICIAL_CHIPS.filter((chip) => chip !== lastQuery).slice(0, 3);
}
