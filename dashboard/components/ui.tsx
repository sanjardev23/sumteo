"use client";
// Day 5 — shared pieces of both views.
import {
  LEVEL_COLOR,
  LEVEL_KO,
  RULE_KO,
  SEVERITY_COLOR,
  snapshotUrl,
  streamUrl,
  type Camera,
  type Level,
  type SumteoEvent,
  type Zone,
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

export function ZoneLine({ zone }: { zone: Zone }) {
  const rules = zone.active.filter((t) => t !== "CROWD_LEVEL" && t !== "ALL_CLEAR");
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="font-mono text-zinc-300">{zone.id}</span>
      <LevelChip level={zone.level} />
      {zone.density_ppm2 != null && (
        <span className="tabular-nums text-zinc-400">
          {zone.density_ppm2.toFixed(2)} /m² · {Math.round(zone.count ?? 0)} people · {zone.speed_mps?.toFixed(1)} m/s
        </span>
      )}
      {rules.map((r) => (
        <span key={r} className="rounded border border-red-500 px-1.5 text-xs text-red-400">
          {RULE_KO[r] ?? r} {r}
        </span>
      ))}
    </div>
  );
}

export function CameraTile({ camera, onOpen }: { camera: Camera; onOpen?: () => void }) {
  const worst = worstLevel(camera);
  return (
    <div
      className="overflow-hidden rounded-lg border-2 bg-zinc-900"
      style={{ borderColor: worst ? LEVEL_COLOR[worst] : "#3f3f46" }}
    >
      <button onClick={onOpen} className="block w-full bg-black" title="Open large view">
        {/* MJPEG: the browser keeps the multipart stream open and swaps frames itself. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={streamUrl(camera.id)} alt={camera.name} className="mx-auto max-h-80 w-auto object-contain" />
      </button>
      <div className="space-y-1.5 p-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-semibold">{camera.name}</h3>
          <HealthBadge camera={camera} />
        </div>
        {camera.zones.map((z) => (
          <ZoneLine key={z.id} zone={z} />
        ))}
        <DemoTag camera={camera} />
      </div>
    </div>
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

export function AlertFeed({
  events,
  escalated,
  onAck,
  onOpen,
}: {
  events: SumteoEvent[];
  escalated: Set<string>;
  onAck: (e: SumteoEvent) => void;
  onOpen: (e: SumteoEvent) => void;
}) {
  if (!events.length) return <p className="text-sm text-zinc-500">No alerts yet.</p>;
  return (
    <ul className="space-y-1.5">
      {events.map((e) => {
        const noResponse = escalated.has(e.id) || !!e.details.escalated;
        return (
          <li
            key={e.id}
            onClick={() => onOpen(e)}
            className={`cursor-pointer rounded border-l-4 bg-zinc-900 p-2 text-sm hover:bg-zinc-800 ${e.acknowledged ? "opacity-60" : ""}`}
            style={{ borderColor: SEVERITY_COLOR[e.severity] }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold" style={{ color: SEVERITY_COLOR[e.severity] }}>
                {e.severity}
                {noResponse && <span className="ml-2 rounded bg-red-600 px-1.5 text-xs text-white">NO RESPONSE</span>}
              </span>
              <AckButton event={e} onAck={onAck} />
            </div>
            <div className="text-zinc-300">{reasons(e)}</div>
            <div className="text-xs text-zinc-500">
              {e.camera_id} · {e.zone_id ?? "camera"} · {ago(e.created_at)}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function Modal({ children, onClose }: { children: React.ReactNode; onClose?: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" onClick={onClose}>
      <div className="max-h-full w-full max-w-4xl overflow-auto rounded-xl bg-zinc-950 p-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

export function EventDetail({ event, onAck, onClose }: { event: SumteoEvent; onAck: (e: SumteoEvent) => void; onClose: () => void }) {
  const snap = snapshotUrl(event.snapshot_path);
  const { escalated, escalated_at } = event.details;
  const rest = Object.entries(event.details).filter(([k]) => !["reasons", "escalated", "escalated_at"].includes(k));
  return (
    <Modal onClose={onClose}>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xl font-bold" style={{ color: SEVERITY_COLOR[event.severity] }}>
          {event.severity} · {reasons(event)}
        </h2>
        <button onClick={onClose} className="text-zinc-400 hover:text-white">✕</button>
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {snap && <img src={snap} alt="blurred snapshot" className="mb-3 max-h-[60vh] w-full rounded object-contain" />}
      <dl className="mb-3 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-zinc-500">camera / zone</dt><dd>{event.camera_id} · {event.zone_id ?? "—"}</dd>
        <dt className="text-zinc-500">when</dt><dd>{new Date(event.created_at * 1000).toLocaleString()} (video {event.ts.toFixed(1)} s)</dd>
        {rest.map(([k, v]) => (
          <div key={k} className="contents"><dt className="text-zinc-500">{k}</dt><dd className="font-mono">{JSON.stringify(v)}</dd></div>
        ))}
        {escalated && <><dt className="text-red-500">escalated</dt><dd className="text-red-400">{String(escalated)} {escalated_at ? `at ${new Date(Number(escalated_at) * 1000).toLocaleTimeString()}` : ""}</dd></>}
        <dt className="text-zinc-500">acknowledged</dt>
        <dd>{event.acknowledged ? `${event.acknowledged_by} at ${new Date((event.acknowledged_ts ?? 0) * 1000).toLocaleTimeString()}` : "not yet"}</dd>
      </dl>
      <AckButton event={event} onAck={onAck} big />
    </Modal>
  );
}
