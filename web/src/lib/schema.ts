import { z } from "zod";

export const jobAnswerSchema = z.object({
  text: z.string().nullable().optional(),
  model: z.string(),
  backend: z.string(),
  confidence: z.string().nullable().optional(),
});

export const jobAssetSchema = z.object({
  filename: z.string(),
  modality: z.string(),
  sensor: z.string().nullable().optional(),
  bounds_wgs84: z.array(z.number()).nullable().optional(),
  preview_url: z.string().nullable().optional(),
});

export const jobOverlaySchema = z.object({
  type: z.string(),
  geojson_url: z.string(),
  confidence: z.number().nullable().optional(),
});

export const jobTraceSchema = z.object({
  event_type: z.string(),
  node_name: z.string().nullable().optional(),
  tool_id: z.string().nullable().optional(),
  message: z.string().nullable().optional(),
  timestamp: z.string().nullable().optional(),
});

export const jobLulcSchema = z.object({
  backend: z.string(),
  focus: z.string(),
  fractions: z.record(z.string(), z.number()),
  scene_tags: z
    .array(
      z.object({
        name: z.string(),
        score: z.number(),
        source: z.string().nullable().optional(),
      }),
    )
    .optional()
    .default([]),
});

export const jobViewSchema = z.object({
  job_id: z.string(),
  session_id: z.string(),
  status: z.string(),
  query: z.string().optional().default(""),
  input_class: z.string().optional().default(""),
  task: z.string().optional().default("UNROUTED"),
  route: z.record(z.string(), z.any()).nullable().optional(),
  answer: jobAnswerSchema.nullable().optional(),
  assets: z.array(jobAssetSchema).optional().default([]),
  overlays: z.array(jobOverlaySchema).optional().default([]),
  traces: z.array(jobTraceSchema).optional().default([]),
  warnings: z.array(z.string()).optional().default([]),
  errors: z.array(z.string()).optional().default([]),
  refusal_reason: z.string().nullable().optional(),
  tile_count: z.number().optional().default(0),
  lulc: jobLulcSchema.nullable().optional(),
});

export type JobView = z.infer<typeof jobViewSchema>;

export const ingestAssetSchema = z.object({
  filename: z.string().optional(),
  modality: z.string().optional(),
  sensor: z.string().nullable().optional(),
  width: z.number().nullable().optional(),
  height: z.number().nullable().optional(),
  crs: z.string().nullable().optional(),
  bounds_wgs84: z.array(z.number()).nullable().optional(),
});

export const ingestResponseSchema = z.object({
  job_id: z.string(),
  session_id: z.string(),
  status: z.string(),
  input_class: z.string().optional(),
  valid: z.boolean(),
  validation_messages: z.array(z.string()).optional().default([]),
  refusal_reason: z.string().nullable().optional(),
  assets: z.array(ingestAssetSchema).optional().default([]),
});

export type IngestResponse = z.infer<typeof ingestResponseSchema>;

export const healthSchema = z.object({
  status: z.string(),
  router_model: z.string().optional(),
  talking_vlm: z.string().optional(),
  ollama: z.string().optional(),
  postgres: z
    .object({
      status: z.string().optional(),
    })
    .passthrough()
    .optional(),
});

export const modelSlotSchema = z.object({
  slot_id: z.string(),
  name: z.string(),
  target_model: z.string(),
  status: z.string(),
  backend_type: z.string(),
  weights_path: z.string().nullable().optional(),
  weights_expected_at: z.string(),
  description: z.string(),
  notes: z.string(),
});

export type ModelSlot = z.infer<typeof modelSlotSchema>;

export const modelsSchema = z.object({
  router_model: z.string().optional(),
  router_ready: z.boolean().optional(),
  talking_vlm: z.string().optional(),
  talking_vlm_backend: z.string().optional(),
  available: z.array(z.string()).optional(),
  model_slots: z.array(modelSlotSchema).optional().default([]),
});

export const TERMINAL_STATUSES = new Set(["completed", "failed", "refused"]);
