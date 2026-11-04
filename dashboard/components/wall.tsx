"use client";
// Day 6 — control-wall pieces (ARCHITECTURE §2.12 v2): light cards floating on the map.
import { useEffect, useState, useSyncExternalStore } from "react";
import { worstLevel } from "@/components/ui";
import {
  LEVEL_COLOR,
  SEVERITY_COLOR,
  frameUrl,
  snapshotUrl,
  streamUrl,
  type Camera,
  type Level,
  type SumteoEvent,
  type Zone,
} from "@/lib/api";
import { setLang, useLang, type Dict } from "@/lib/i18n";

export const CARD = "rounded-lg border border-[#D5DBE3] bg-white shadow-[0_1px_3px_rgb(16_24_40/0.08),0_4px_12px_rgb(16_24_40/0.06)]";
const LEVELS: Level[] = ["GREEN", "YELLOW", "ORANGE", "RED"];

export const cameraLabel = (c: Camera | undefined, id: string) => c?.location?.label || c?.name || id;

export function peakDensity(c: Camera): number | null {
  const d = c.zones.map((z) => z.density_ppm2).filter((v): v is number => v != null);
  return d.length ? Math.max(...d) : null;
}

const clockTick = (f: () => void) => {
  const id = setInterval(f, 1000);
  return () => clearInterval(id);
};
// useSyncExternalStore needs the same value for back-to-back reads, so the text is kept per whole second.
let clock = { second: 0, text: "" };
function seoulTime(): string {
  const second = Math.floor(Date.now() / 1000);
  if (second !== clock.second)
    clock = { second, text: new Date(second * 1000).toLocaleTimeString("en-GB", { hour12: false, timeZone: "Asia/Seoul" }) };
  return clock.text;
}

export function Clock() {
  const now = useSyncExternalStore(clockTick, seoulTime, () => "");
  return <span className="tabular-nums text-[#1B2430]">{now} KST</span>;
}

export function LangSwitch() {
  const lang = useLang();
  const btn = (on: boolean) => (on ? "font-semibold text-[#1D4F91]" : "text-[#5B6675] hover:text-[#1B2430]");
  return (
    <span className="flex items-center gap-1.5">
      <button className={btn(lang === "en")} onClick={() => setLang("en")}>EN</button>
      <span className="text-[#C5CDD8]">|</span>
      <button className={btn(lang === "ko")} onClick={() => setLang("ko")}>한국어</button>
    </span>
  );
}

export function LiveDot({ connected, t }: { connected: boolean; t: Dict }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`size-2 rounded-full ${connected ? "bg-[#2E7D32]" : "bg-[#C62828]"}`} />
      <span className={connected ? "text-[#1B2430]" : "text-[#C62828]"}>{connected ? t.live : t.reconnecting}</span>
    </span>
  );
}

/** Every view of a replayed camera says so (§2.11): a recorded run is never shown as live inference. */
export function ReplayTag({ t, short = false }: { t: Dict; short?: boolean }) {
  return (
    <span className="rounded border border-[#8A94A3] bg-[#F1F3F6] px-1.5 py-px text-[10px] font-semibold tracking-wide text-[#3A4553]">
      {short ? t.replayShort : t.replayTag}
    </span>
  );
}

export function LevelTag({ level, t }: { level: Level | null; t: Dict }) {
  if (!level) return <span className="rounded bg-[#EEF1F4] px-1.5 py-0.5 text-[11px] text-[#5B6675]">{t.notCalibrated}</span>;
  const dark = level === "YELLOW" || level === "ORANGE";
  return (
    <span
      className="rounded px-1.5 py-0.5 text-[11px] font-semibold"
      style={{ background: LEVEL_COLOR[level], color: dark ? "#1B2430" : "#fff" }}
    >
      {t.levels[level]}
    </span>
  );
}

export function eventText(e: SumteoEvent, t: Dict): string {
  const rules = (e.details.reasons ?? [e.type]).map((r) => t.rules[r] ?? r).join(" + ");
  return e.details.level ? `${rules} · ${t.levels[e.details.level]}` : rules;
}

// 24-hour hh:mm:ss in both languages: Korean locale formatting would print "14시 29분 24초".
export const eventTime = (e: SumteoEvent) =>
  new Date(e.created_at * 1000).toLocaleTimeString("en-GB", { hour12: false, timeZone: "Asia/Seoul" });

function AckLink({ event, t, onAck }: { event: SumteoEvent; t: Dict; onAck: (e: SumteoEvent) => void }) {
  if (event.severity === "INFO") return null;
  if (event.acknowledged) return <span className="text-[#2E7D32]">✓ {t.acknowledgedBy} · {event.acknowledged_by}</span>;
  return (
    <button
      onClick={(ev) => {
        ev.stopPropagation();
        onAck(event);
      }}
      className="rounded border border-[#1D4F91] px-1.5 py-px font-medium text-[#1D4F91] hover:bg-[#1D4F91] hover:text-white"
    >
      {t.acknowledge}
    </button>
  );
}

type Filter = "all" | "open" | "critical" | "warning";
const FILTERS: Filter[] = ["all", "open", "critical", "warning"];
const keep: Record<Filter, (e: SumteoEvent) => boolean> = {
  all: () => true,
  open: (e) => e.severity !== "INFO" && !e.acknowledged,
  critical: (e) => e.severity === "CRITICAL",
  warning: (e) => e.severity === "WARNING",
};

export function EventList({
  events,
  escalated,
  cameras,
  t,
  onAck,
  onPick,
}: {
  events: SumteoEvent[];
  escalated: Set<string>;
  cameras: Camera[];
  t: Dict;
  onAck: (e: SumteoEvent) => void;
  onPick: (e: SumteoEvent) => void;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const shown = events.filter(keep[filter]).slice(0, 100);
  return (
    <section className={`${CARD} flex min-h-0 flex-1 flex-col`}>
      <div className="flex items-center justify-between gap-2 border-b border-[#E3E8EE] px-3 py-2.5">
        <h2 className="text-[13px] font-semibold">
          {t.events} <span className="ml-0.5 font-normal text-[#5B6675]">{shown.length}</span>
        </h2>
        <div className="flex gap-0.5 rounded-md bg-[#EEF1F4] p-0.5 text-[11px]">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={f === filter ? "rounded bg-white px-2 py-0.5 font-medium text-[#1D4F91] shadow-sm" : "px-2 py-0.5 text-[#5B6675] hover:text-[#1B2430]"}
            >
              {t.filters[f]}
            </button>
          ))}
        </div>
      </div>
      {!shown.length && <p className="px-3 py-4 text-[12px] text-[#5B6675]">{t.noEvents}</p>}
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {shown.map((e) => {
          const noResponse = escalated.has(e.id) || !!e.details.escalated;
          return (
            <li
              key={e.id}
              onClick={() => onPick(e)}
              className={`flex cursor-pointer gap-2.5 border-b border-[#EEF1F4] px-3 py-2 hover:bg-[#F5F7FA] ${e.acknowledged ? "opacity-70" : ""}`}
            >
              <span className="w-1 shrink-0 rounded-full" style={{ background: SEVERITY_COLOR[e.severity] }} />
              <div className="min-w-0 flex-1 space-y-0.5">
                <div className="flex items-center justify-between gap-2 text-[11px] text-[#5B6675]">
                  <span className="tabular-nums">
                    {eventTime(e)} ·<span style={{ color: SEVERITY_COLOR[e.severity] }}>{t.severity[e.severity]}</span>
                  </span>
                  <AckLink event={e} t={t} onAck={onAck} />
                </div>
                <div className="truncate text-[13px] font-medium">
                  {cameraLabel(cameras.find((c) => c.id === e.camera_id), e.camera_id)}
                </div>
                <div className="text-[12px] text-[#3A4553]">
                  {eventText(e, t)}
                  {e.zone_id && <span className="text-[#8A94A3]"> · {e.zone_id}</span>}
                  {noResponse && (
                    <span className="ml-1.5 rounded bg-[#C62828] px-1 text-[10px] font-semibold text-white">{t.noResponse}</span>
                  )}
                  {e.replay && (
                    <span className="ml-1.5">
                      <ReplayTag t={t} short />
                    </span>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function DemoLine({ camera, t }: { camera: Camera; t: Dict }) {
  const l = camera.demo.levels;
  if (!camera.demo.overridden || !l) return null;
  return <p className="text-[11px] font-semibold text-[#C62828]">{t.demo(l.yellow, l.orange, l.red)}</p>;
}

function ZoneNumbers({ zone, t, many }: { zone: Zone; t: Dict; many: boolean }) {
  const cell = (k: string, v: string, color?: string) => (
    <div className="px-2 py-1.5 text-center">
      <div className="text-[10px] text-[#5B6675]">{k}</div>
      <div className="text-[14px] font-semibold tabular-nums" style={{ color }}>{v}</div>
    </div>
  );
  const rules = zone.active.filter((r) => r !== "CROWD_LEVEL" && r !== "ALL_CLEAR");
  return (
    <div className="space-y-1">
      {many && (
        <div className="flex items-center gap-1.5 text-[11px] text-[#5B6675]">
          {t.zone} {zone.id} <LevelTag level={zone.level} t={t} />
        </div>
      )}
      <div className="grid grid-cols-3 divide-x divide-[#E3E8EE] rounded border border-[#E3E8EE]">
        {cell(t.density, zone.density_ppm2 != null ? `${zone.density_ppm2.toFixed(1)}/m²` : "—", zone.level ? levelInk(zone.level) : undefined)}
        {cell(t.people, zone.count != null ? String(Math.round(zone.count)) : "—")}
        {cell(t.speed, zone.speed_mps != null ? `${zone.speed_mps.toFixed(1)} m/s` : "—")}
      </div>
      {!!rules.length && (
        <div className="flex flex-wrap gap-1">
          {rules.map((r) => (
            <span key={r} className="rounded border border-[#C62828] px-1 text-[10px] font-medium text-[#C62828]">
              {t.rules[r] ?? r}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/** Yellow and orange are fill colors; as text on white they need a darker ink to stay readable. */
const levelInk = (l: Level) => ({ GREEN: "#2E7D32", YELLOW: "#8A6A00", ORANGE: "#C2410C", RED: "#C62828" })[l];

export function CameraCard({
  camera,
  open,
  t,
  onAck,
  onEnlarge,
  onClose,
}: {
  camera: Camera;
  open?: SumteoEvent;
  t: Dict;
  onAck: (e: SumteoEvent) => void;
  onEnlarge: () => void;
  onClose: () => void;
}) {
  return (
    <div className={`${CARD} w-[290px] overflow-hidden text-[#1B2430] shadow-lg`} style={{ fontFamily: FONT }}>
      <button onClick={onEnlarge} className="relative block w-full bg-black" title={t.enlarge}>
        {/* MJPEG: one open stream, only while the card is open. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={streamUrl(camera.id)} alt={camera.name} className="aspect-video w-full object-contain" />
        <span className="absolute left-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-medium text-white">
          {camera.mode === "replay" ? t.replayTag : "● LIVE"} · {t.blurred}
        </span>
      </button>
      <div className="space-y-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-[14px] font-semibold leading-snug">{cameraLabel(camera, camera.id)}</h3>
            <p className="text-[11px] leading-snug text-[#5B6675]">{camera.location?.clip || camera.name}</p>
            {camera.mode === "replay" && (
              <div className="mt-1">
                <ReplayTag t={t} />
              </div>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <LevelTag level={worstLevel(camera)} t={t} />
            <button onClick={onClose} className="px-1 text-[#8A94A3] hover:text-[#1B2430]" aria-label={t.close}>✕</button>
          </div>
        </div>
        {camera.zones.map((z) => (
          <ZoneNumbers key={z.id} zone={z} t={t} many={camera.zones.length > 1} />
        ))}
        {!!camera.health.length && <p className="text-[11px] font-semibold text-[#C2410C]">{t.cameraProblem}</p>}
        <DemoLine camera={camera} t={t} />
        <div className="flex gap-2 pt-0.5">
          <button onClick={onEnlarge} className="flex-1 rounded bg-[#1D4F91] py-1.5 text-[12px] font-medium text-white hover:bg-[#163E73]">
            {t.enlarge}
          </button>
          {open && (
            <button
              onClick={() => onAck(open)}
              className="flex-1 rounded border border-[#C62828] py-1.5 text-[12px] font-medium text-[#C62828] hover:bg-[#C62828] hover:text-white"
            >
              {t.acknowledge}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export const FONT = 'var(--font-plex), "Apple SD Gothic Neo", system-ui, sans-serif';

export function Kpis({ cameras, openAlerts, t }: { cameras: Camera[]; openAlerts: number; t: Dict }) {
  const ok = cameras.filter((c) => !c.health.length).length;
  const peaks = cameras.map((c) => ({ c, d: peakDensity(c) })).filter((x): x is { c: Camera; d: number } => x.d != null);
  const top = peaks.sort((a, b) => b.d - a.d)[0];
  const people = cameras.flatMap((c) => c.zones).reduce((n, z) => n + (z.count ?? 0), 0);
  const tile = (k: string, v: string, sub?: string, alert = false) => (
    <div className={`rounded border px-2.5 py-2 ${alert ? "border-[#F1C4C4] bg-[#FDF3F3]" : "border-[#E3E8EE]"}`}>
      <div className="text-[11px] text-[#5B6675]">{k}</div>
      <div className={`text-[18px] font-semibold tabular-nums leading-tight ${alert ? "text-[#C62828]" : ""}`}>{v}</div>
      {sub && <div className="truncate text-[10px] text-[#8A94A3]">{sub}</div>}
    </div>
  );
  return (
    <div className="grid grid-cols-2 gap-2">
      {tile(t.camerasOnline, `${ok} / ${cameras.length}`)}
      {tile(t.openAlerts, String(openAlerts), undefined, openAlerts > 0)}
      {tile(t.peakDensity, top ? `${top.d.toFixed(1)}/m²` : "—", top ? cameraLabel(top.c, top.c.id) : undefined)}
      {tile(t.peopleNow, String(Math.round(people)))}
    </div>
  );
}

const thumbTick = (f: () => void) => {
  const id = setInterval(f, 2000);
  return () => clearInterval(id);
};
const thumbStamp = () => Math.floor(Date.now() / 2000);

/** Still frames refreshed every 2 s: an MJPEG stream per tile would use up the browser's ~6 connections per host. */
export function CameraThumbs({
  cameras,
  selected,
  t,
  onPick,
}: {
  cameras: Camera[];
  selected: string | null;
  t: Dict;
  onPick: (c: Camera) => void;
}) {
  const stamp = useSyncExternalStore(thumbTick, thumbStamp, () => 0);
  return (
    <div>
      <h3 className="mb-1.5 text-[12px] font-medium">{t.cameras}</h3>
      <div className="grid grid-cols-2 gap-1.5">
        {cameras.map((c) => {
          const level = worstLevel(c);
          return (
            <button
              key={c.id}
              onClick={() => onPick(c)}
              className={`overflow-hidden rounded border text-left ${
                c.id === selected ? "border-[#1D4F91] ring-1 ring-[#1D4F91]" : "border-[#E3E8EE] hover:border-[#9AA4B2]"
              }`}
            >
              <div className="aspect-video bg-[#1B2430]">
                {stamp > 0 && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={`${frameUrl(c.id)}?t=${stamp}`} alt={c.name} className="size-full object-cover" />
                )}
              </div>
              <div className="flex items-center gap-1 px-1.5 py-1 text-[10px]">
                <span className="size-2 shrink-0 rounded-full" style={{ background: level ? LEVEL_COLOR[level] : "#9AA4B2" }} />
                <span className="truncate">{cameraLabel(c, c.id)}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Blurred snapshot, the rules that fired and every detail the server stored (VLM note included, §2.9). */
export function EventDetail({
  event,
  camera,
  t,
  onAck,
  onClose,
}: {
  event: SumteoEvent;
  camera?: Camera;
  t: Dict;
  onAck: (e: SumteoEvent) => void;
  onClose: () => void;
}) {
  const snap = snapshotUrl(event.snapshot_path);
  const { escalated, escalated_at } = event.details;
  const rest = Object.entries(event.details).filter(([k]) => !["reasons", "level", "escalated", "escalated_at"].includes(k));
  const row = (k: string, v: React.ReactNode, red = false) => (
    <div key={k} className="contents">
      <dt className={red ? "text-[#C62828]" : "text-[#5B6675]"}>{k}</dt>
      <dd className={red ? "text-[#C62828]" : ""}>{v}</dd>
    </div>
  );
  return (
    <LightModal onClose={onClose}>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-[13px] font-semibold" style={{ color: SEVERITY_COLOR[event.severity] }}>
            {t.severity[event.severity]} · {eventText(event, t)}
          </div>
          <h2 className="text-[18px] font-semibold">{cameraLabel(camera, event.camera_id)}</h2>
        </div>
        <button onClick={onClose} className="px-1 text-[#8A94A3] hover:text-[#1B2430]" aria-label={t.close}>✕</button>
      </div>
      {snap ? (
        <figure className="mb-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={snap} alt={t.snapshot} className="max-h-[55vh] w-full rounded bg-[#1B2430] object-contain" />
          <figcaption className="mt-1 text-[11px] text-[#5B6675]">{t.snapshot}</figcaption>
        </figure>
      ) : (
        <p className="mb-3 rounded bg-[#EEF1F4] px-3 py-6 text-center text-[12px] text-[#5B6675]">{t.noSnapshot}</p>
      )}
      <dl className="mb-3 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-[13px]">
        {row(t.when, `${new Date(event.created_at * 1000).toLocaleString("en-GB", { timeZone: "Asia/Seoul" })} KST`)}
        {row(t.videoTime, `${event.ts.toFixed(1)} s`)}
        {row(t.zone, event.zone_id ?? "—")}
        {rest.map(([k, v]) => row(k, <span className="font-mono text-[12px]">{JSON.stringify(v)}</span>))}
        {escalated &&
          row(
            t.noResponse,
            `${String(escalated)}${escalated_at ? ` · ${new Date(Number(escalated_at) * 1000).toLocaleTimeString("en-GB", { timeZone: "Asia/Seoul" })}` : ""}`,
            true,
          )}
        {row(
          t.acknowledgedBy,
          event.acknowledged
            ? `${event.acknowledged_by} · ${new Date((event.acknowledged_ts ?? 0) * 1000).toLocaleTimeString("en-GB", { timeZone: "Asia/Seoul" })}`
            : t.notYet,
        )}
      </dl>
      {event.severity !== "INFO" && !event.acknowledged && (
        <button
          onClick={() => onAck(event)}
          className="w-full rounded bg-[#1D4F91] py-2.5 text-[15px] font-semibold text-white hover:bg-[#163E73]"
        >
          {t.acknowledge}
        </button>
      )}
    </LightModal>
  );
}

export function Legend({ t, className = "" }: { t: Dict; className?: string }) {
  return (
    <div className={`${CARD} px-3 py-2 ${className}`}>
      <div className="mb-1 text-[11px] font-semibold text-[#5B6675]">{t.legend}</div>
      <div className="flex gap-3 text-[12px]">
        {LEVELS.map((l) => (
          <span key={l} className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full" style={{ background: LEVEL_COLOR[l] }} />
            {t.levels[l]}
          </span>
        ))}
      </div>
      <div className="mt-1 text-[10px] text-[#8A94A3]">{t.legendNote}</div>
    </div>
  );
}

export function LightModal({ children, onClose }: { children: React.ReactNode; onClose?: () => void }) {
  useEffect(() => {
    if (!onClose) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[#1B2430]/45 p-6" onClick={onClose}>
      <div
        className={`${CARD} max-h-full w-full max-w-4xl overflow-auto p-4 text-[#1B2430]`}
        style={{ fontFamily: FONT }}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

/** Large live view: the enlarged camera, or the priority pop-up that stays until acknowledged (§2.12). */
export function BigCamera({
  camera,
  t,
  event,
  more = 0,
  noResponse = false,
  onAck,
  onClose,
}: {
  camera: Camera;
  t: Dict;
  event?: SumteoEvent;
  more?: number;
  noResponse?: boolean;
  onAck?: (e: SumteoEvent) => void;
  onClose?: () => void;
}) {
  return (
    <LightModal onClose={event ? undefined : onClose}>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          {event && (
            <div className="mb-1 flex items-center gap-2 text-[13px] font-semibold" style={{ color: SEVERITY_COLOR[event.severity] }}>
              {noResponse && <span className="rounded bg-[#C62828] px-1.5 text-white">{t.noResponse}</span>}
              {t.severity[event.severity]} · {eventText(event, t)}
              {more > 0 && <span className="font-normal text-[#5B6675]">+{more} {t.moreWaiting}</span>}
            </div>
          )}
          <h2 className="text-[18px] font-semibold">{cameraLabel(camera, camera.id)}</h2>
          <p className="text-[12px] text-[#5B6675]">{camera.location?.clip || camera.name}</p>
          {camera.mode === "replay" && (
            <div className="mt-1">
              <ReplayTag t={t} />
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <LevelTag level={worstLevel(camera)} t={t} />
          {!event && onClose && (
            <button onClick={onClose} className="px-1 text-[#8A94A3] hover:text-[#1B2430]" aria-label={t.close}>✕</button>
          )}
        </div>
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={streamUrl(camera.id)} alt={camera.name} className="mb-3 max-h-[60vh] w-full rounded bg-black object-contain" />
      <div className="grid gap-3 sm:grid-cols-2">
        {camera.zones.map((z) => (
          <ZoneNumbers key={z.id} zone={z} t={t} many={camera.zones.length > 1} />
        ))}
      </div>
      {!!camera.health.length && <p className="mt-2 text-[12px] font-semibold text-[#C2410C]">{t.cameraProblem}</p>}
      <div className="mt-2">
        <DemoLine camera={camera} t={t} />
      </div>
      {event && onAck && (
        <button
          onClick={() => onAck(event)}
          className="mt-3 w-full rounded bg-[#1D4F91] py-3 text-[16px] font-semibold text-white hover:bg-[#163E73]"
        >
          {t.acknowledge}
        </button>
      )}
    </LightModal>
  );
}
