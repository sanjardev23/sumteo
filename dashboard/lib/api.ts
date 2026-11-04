// Day 5 — types and calls for the Sumteo API (src/sumteo/api/server.py).
export const API = process.env.NEXT_PUBLIC_API ?? "http://127.0.0.1:8000";
export const WS_URL = API.replace(/^http/, "ws");

export type Role = "security" | "admin";
export type Level = "GREEN" | "YELLOW" | "ORANGE" | "RED";
export type Severity = "INFO" | "WARNING" | "CRITICAL";

export interface Zone {
  id: string;
  area_m2: number | null;
  level: Level | null;
  label: string | null;
  density_ppm2: number | null;
  count: number | null;
  count_source: string | null;
  speed_mps: number | null;
  active: string[];
  thresholds: { yellow: number; orange: number; red: number } | null;
}

export interface Camera {
  id: string;
  name: string;
  zones: Zone[];
  health: string[];
  location: { lat: number; lon: number; label: string; clip: string } | null;
  demo: { overridden: boolean; levels: { yellow: number; orange: number; red: number } | null };
}

export interface SumteoEvent {
  id: string;
  camera_id: string;
  type: string;
  severity: Severity;
  ts: number;
  zone_id: string | null;
  track_id: number | null;
  details: Record<string, unknown> & { reasons?: string[]; level?: Level; escalated?: string };
  snapshot_path: string | null;
  acknowledged: boolean;
  acknowledged_by: string | null;
  acknowledged_ts: number | null;
  created_at: number;
}

export interface MetricRow {
  zone_id: string;
  ts: number;
  wall_ts: number;
  count: number;
  density_ppm2: number;
  level: Level;
}

export const streamUrl = (cameraId: string) => `${API}/cameras/${cameraId}/stream`;
export const frameUrl = (cameraId: string) => `${API}/cameras/${cameraId}/frame.jpg`;
export const snapshotUrl = (path: string | null) => (path ? `${API}/snapshots/${path.split("/").pop()}` : null);

export async function getEvents(limit = 100): Promise<SumteoEvent[]> {
  const r = await fetch(`${API}/events?limit=${limit}`, { cache: "no-store" });
  return r.ok ? r.json() : [];
}

export async function getMetrics(cameraId: string, since: number): Promise<MetricRow[]> {
  const r = await fetch(`${API}/metrics/${cameraId}?since=${since}`, { cache: "no-store" });
  return r.ok ? r.json() : [];
}

export async function acknowledge(eventId: string, role: Role): Promise<SumteoEvent | null> {
  const r = await fetch(`${API}/events/${eventId}/ack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
  return r.ok ? r.json() : null;
}

// Same colors as the video overlay (src/sumteo/video/overlay.py).
export const LEVEL_COLOR: Record<Level, string> = {
  GREEN: "#3cbe5a",
  YELLOW: "#ffd700",
  ORANGE: "#ff8200",
  RED: "#e62828",
};
export const SEVERITY_COLOR: Record<Severity, string> = { INFO: "#38bdf8", WARNING: "#ff8200", CRITICAL: "#e62828" };
export const LEVEL_KO: Record<Level, string> = { GREEN: "관심", YELLOW: "주의", ORANGE: "경계", RED: "심각" };
export const RULE_KO: Record<string, string> = {
  CROWD_LEVEL: "밀집 단계",
  STAGNATION: "정체",
  DENSITY_RISING: "급증",
  COUNTER_FLOW: "역류",
  INFLOW_IMBALANCE: "유입 과다",
  CAMERA_HEALTH: "카메라 이상",
  ALL_CLEAR: "해제",
};
