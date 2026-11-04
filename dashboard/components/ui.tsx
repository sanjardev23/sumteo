"use client";
// Day 5 — shared pieces of both views.
import {
  LEVEL_COLOR,
  LEVEL_KO,
  RULE_KO,
  type Camera,
  type Level,
  type SumteoEvent,
} from "@/lib/api";

export function LevelChip({ level, big = false }: { level: Level | null; big?: boolean }) {
  if (!level) return <span className="rounded bg-zinc-700 px-2 py-0.5 text-xs text-zinc-300">not calibrated</span>;
  const dark = level === "YELLOW" || level === "ORANGE";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded font-semibold ${big ? "px-3 py-1 text-lg" : "px-2 py-0.5 text-xs"}`}
      style={{ background: LEVEL_COLOR[level], color: dark ? "#111" : "#fff" }}
    >
      {LEVEL_KO[level]} <span className="font-normal opacity-80">{level}</span>
    </span>
  );
}

/** Same promise as the video overlay (§2.1, §2.12): a camera on its own thresholds can't pass for real danger. */
export function DemoTag({ camera }: { camera: Camera }) {
  const l = camera.demo.levels;
  if (!camera.demo.overridden || !l) return null;
  return (
    <p className="text-xs font-semibold text-red-500">
      DEMO THRESHOLDS: yellow {l.yellow} / orange {l.orange} / red {l.red} /m² (not the real levels)
    </p>
  );
}

export function HealthBadge({ camera }: { camera: Camera }) {
  if (!camera.health.length) return <span className="text-xs text-emerald-400">● camera OK</span>;
  return (
    <span className="rounded bg-orange-500 px-2 py-0.5 text-xs font-bold text-black">
      CAMERA {camera.health.join(" + ").toUpperCase()} — zones hold last level
    </span>
  );
}

export function worstLevel(camera: Camera): Level | null {
  const order: Level[] = ["GREEN", "YELLOW", "ORANGE", "RED"];
  const levels = camera.zones.map((z) => z.level).filter((l): l is Level => !!l);
  return levels.length ? levels.reduce((a, b) => (order.indexOf(b) > order.indexOf(a) ? b : a)) : null;
}

export function ago(epoch: number): string {
  const s = Math.max(0, Math.round(Date.now() / 1000 - epoch));
  return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.floor(s / 60)}m ago` : new Date(epoch * 1000).toLocaleTimeString();
}

export function reasons(e: SumteoEvent): string {
  return (e.details.reasons ?? [e.type]).map((r) => `${RULE_KO[r] ?? r} ${r}`).join(" + ");
}

export function AckButton({ event, onAck, big = false }: { event: SumteoEvent; onAck: (e: SumteoEvent) => void; big?: boolean }) {
  if (event.acknowledged)
    return <span className="text-xs text-emerald-400">✓ {event.acknowledged_by}</span>;
  return (
    <button
      onClick={(ev) => {
        ev.stopPropagation();
        onAck(event);
      }}
      className={`rounded bg-white font-bold text-black hover:bg-zinc-200 ${big ? "w-full px-6 py-4 text-xl" : "px-2 py-1 text-xs"}`}
    >
      Acknowledge · 확인
    </button>
  );
}

