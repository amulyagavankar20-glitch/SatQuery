import { JOBS_STORAGE_KEY, MAX_JOBS } from "./constants";
import type { JobRecord, SceneSlot } from "./types";

function stripFiles(slots: SceneSlot[]): SceneSlot[] {
  return slots.map(({ file: _file, ...rest }) => rest);
}

function serialize(jobs: JobRecord[]): string {
  return JSON.stringify(
    jobs.map((job) => ({
      ...job,
      slots: stripFiles(job.slots),
    })),
  );
}

export function loadJobs(): JobRecord[] {
  try {
    const raw = localStorage.getItem(JOBS_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as JobRecord[];
  } catch {
    return [];
  }
}

export function saveJobs(jobs: JobRecord[]) {
  try {
    localStorage.setItem(JOBS_STORAGE_KEY, serialize(jobs.slice(0, MAX_JOBS)));
  } catch {
    /* ignore quota */
  }
}
