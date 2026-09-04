import {
  healthSchema,
  ingestResponseSchema,
  jobViewSchema,
  modelsSchema,
  type IngestResponse,
  type JobView,
} from "./schema";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export function apiUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

async function parseError(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      return JSON.stringify(detail);
    }
  } catch {
    /* ignore */
  }
  return `${response.status} ${response.statusText}`;
}

export async function fetchHealth() {
  const response = await fetch(apiUrl("/health"));
  if (!response.ok) throw new Error(await parseError(response));
  return healthSchema.parse(await response.json());
}

export async function fetchModels() {
  const response = await fetch(apiUrl("/models"));
  if (!response.ok) throw new Error(await parseError(response));
  return modelsSchema.parse(await response.json());
}

export async function ingestRasters(files: File[], sensor: string, query = ""): Promise<IngestResponse> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  if (sensor) form.append("sensor", sensor);
  if (query) form.append("query", query);
  const response = await fetch(apiUrl("/ingest"), { method: "POST", body: form });
  if (!response.ok) throw new Error(await parseError(response));
  return ingestResponseSchema.parse(await response.json());
}

export async function runJob(jobId: string, query: string) {
  const response = await fetch(apiUrl("/run"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, query }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as { job_id: string; session_id: string; status: string };
}

export async function fetchJob(jobId: string): Promise<JobView> {
  const response = await fetch(apiUrl(`/jobs/${jobId}`));
  if (!response.ok) throw new Error(await parseError(response));
  return jobViewSchema.parse(await response.json());
}

export async function downloadExport(jobId: string, format: "geojson" | "kml") {
  const response = await fetch(apiUrl(`/jobs/${jobId}/export.${format}`));
  if (!response.ok) throw new Error(await parseError(response));
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `satquery-${jobId}.${format === "geojson" ? "geojson" : "kml"}`;
  anchor.click();
  URL.revokeObjectURL(url);
}
