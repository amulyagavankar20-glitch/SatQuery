export type LayerId = "optical" | "sar" | "change" | "uncertain";

export type Modality = "OPTICAL" | "SAR";

export type BBox = [number, number, number, number];

export type GeoJSONPolygon = {
  type: "Feature";
  properties: {
    id?: string;
    kind?: "change" | "uncertain" | "grounding" | "sar_detection" | "detection" | string;
    label?: string;
    feature_type?: string;
    confidence?: number;
    [key: string]: unknown;
  };
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] };
};

export type OverlayCollection = {
  type: "FeatureCollection";
  features: GeoJSONPolygon[];
};

export type SceneSlot = {
  id: string;
  slot: "T1" | "T2";
  filename: string;
  modality: Modality;
  sensor: string;
  crs: string;
  date: string | null;
  bands: number | null;
  gsd?: string | null;
  bounds: BBox;
  previewUrl: string;
  objectPos?: string;
  file?: File;
};

export type TraceStep = {
  tool: string;
  params: Record<string, unknown>;
  elapsedMs?: number;
};

export type UserTurn = {
  id: string;
  role: "user";
  query: string;
};

export type AssistantTurn = {
  id: string;
  role: "assistant";
  status: "pending" | "completed" | "failed";
  pendingLabel?: string;
  answer?: string;
  confidence?: "Low" | "Medium" | "High";
  jobId: string;
  bounds: BBox;
  opticalUrl: string | null;
  sarUrl: string | null;
  vvUrl?: string | null;
  vhUrl?: string | null;
  overlayUrl?: string | null;
  compareUrl: string | null;
  overlays?: OverlayCollection;
  trace?: TraceStep[];
  error?: string;
};

export type Turn = UserTurn | AssistantTurn;

export type JobRecord = {
  id: string;
  query: string;
  createdAt: number;
  summary: string;
  slots: SceneSlot[];
  pairFitness: number | null;
  turns: Turn[];
};

export type DemoId = "water" | "coastal" | "cloudy";
