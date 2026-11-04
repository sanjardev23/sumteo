"use client";
// Day 6 — control wall (ARCHITECTURE §2.12 v2), replacing the Day 5 camera grid: the Itaewon map fills the screen,
// light cards float on it. Pop-up / acknowledge / escalation behave as before (§2.8, §2.12).
import { useState } from "react";
import { DensityChart } from "@/components/DensityChart";
import { KakaoMap, type LatLon, type Pin, type Ring } from "@/components/KakaoMap";
import { SoundGate } from "@/components/TopBar";
import { worstLevel } from "@/components/ui";
import {
  BigCamera,
  CARD,
  CameraCard,
  CameraThumbs,
  Clock,
  EventDetail,
  EventList,
  FONT,
  Kpis,
  LangSwitch,
  Legend,
  LiveDot,
  cameraLabel,
  eventText,
  eventTime,
  peakDensity,
} from "@/components/wall";
import { LEVEL_COLOR, SEVERITY_COLOR, acknowledge, type Camera, type SumteoEvent } from "@/lib/api";
import { dict, useLang } from "@/lib/i18n";
import { useLive } from "@/lib/useLive";

const ITAEWON: LatLon = { lat: 37.5345, lon: 126.9937 };
const SEOUL: LatLon = { lat: 37.5563, lon: 126.9852 };
const HOTSPOT: Ring[] = [{ ...ITAEWON, radius: 700, color: "#C62828" }];

export default function Admin() {
  const live = useLive("admin");
  const t = dict[useLang()];
  const [selected, setSelected] = useState<string | null>(null);
  const [large, setLarge] = useState<string | null>(null);
  const [focus, setFocus] = useState<LatLon | null>(null);
  const [detail, setDetail] = useState<SumteoEvent | null>(null);

  const ack = async (e: SumteoEvent) => {
    const row = await acknowledge(e.id, "admin");
    if (row) {
      live.applyAck(row);
      setDetail((d) => (d?.id === row.id ? row : d));
    }
  };

  const placed = live.cameras.filter((c) => c.location);
  const pins: Pin[] = placed.map((c) => {
    const level = worstLevel(c);
    const d = peakDensity(c);
    return {
      id: c.id,
      lat: c.location!.lat,
      lon: c.location!.lon,
      color: level ? LEVEL_COLOR[level] : "#9AA4B2",
      label: cameraLabel(c, c.id),
      value: d != null ? `${d.toFixed(1)}/m²` : undefined,
      tag: c.mode === "replay" ? t.replayShort : undefined,
      pulse: level === "RED",
    };
  });
  // First click on a camera icon opens its card, a second click enlarges it (§2.12 v2).
  const clickPin = (id: string) => (id === selected ? setLarge(id) : setSelected(id));
  const showCamera = (c: Camera) => {
    if (!c.location) return setLarge(c.id);
    setSelected(c.id);
    setFocus({ lat: c.location.lat, lon: c.location.lon });
  };
  // An event opens its detail; behind it the map already moved to the camera, card open.
  const pick = (e: SumteoEvent) => {
    const c = live.cameras.find((x) => x.id === e.camera_id);
    if (c?.location) showCamera(c);
    setDetail(e);
  };

  const sel = placed.find((c) => c.id === selected);
  const chartCamera = sel ?? worstCamera(live.cameras);
  const chartZone = chartCamera && [...chartCamera.zones].sort((a, b) => (b.density_ppm2 ?? 0) - (a.density_ppm2 ?? 0))[0];

  const popup = [...live.popups].sort((a, b) => (b.severity === "CRITICAL" ? 1 : 0) - (a.severity === "CRITICAL" ? 1 : 0))[0];
  const popCamera = popup && live.cameras.find((c) => c.id === popup.camera_id);
  const bigCamera = large ? live.cameras.find((c) => c.id === large) : undefined;
  const latest = live.events.find((e) => e.severity !== "INFO");

  return (
    <div className="fixed inset-0 flex flex-col bg-[#EEF1F4] text-[#1B2430]" style={{ fontFamily: FONT }}>
      <header className="z-20 flex h-12 shrink-0 items-center justify-between border-b border-[#D5DBE3] bg-white px-5">
        <div className="flex items-center gap-3">
          <span className="text-[17px] font-semibold tracking-tight">
            Sumteo <span className="font-normal text-[#5B6675]">숨터</span>
          </span>
          <span className="border-l border-[#D5DBE3] pl-3 text-[13px] text-[#5B6675]">
            {t.title} · {t.area}
          </span>
        </div>
        <div className="flex items-center gap-5 text-[13px]">
          <LiveDot connected={live.connected} t={t} />
          <Clock />
          <LangSwitch />
        </div>
      </header>
      <SoundGate light />

      <main className="relative min-h-0 flex-1">
        <KakaoMap
          className="absolute inset-0"
          center={ITAEWON}
          level={3}
          pins={pins}
          selected={selected}
          onPin={clickPin}
          focus={focus}
          popup={
            sel
              ? {
                  lat: sel.location!.lat,
                  lon: sel.location!.lon,
                  node: (
                    <CameraCard
                      camera={sel}
                      open={live.popups.find((e) => e.camera_id === sel.id)}
                      t={t}
                      onAck={ack}
                      onEnlarge={() => setLarge(sel.id)}
                      onClose={() => setSelected(null)}
                    />
                  ),
                }
              : null
          }
        />

        <aside className="absolute bottom-4 left-4 top-4 z-10 flex w-[320px] flex-col">
          <EventList events={live.events} escalated={live.escalated} cameras={live.cameras} t={t} onAck={ack} onPick={pick} />
        </aside>

        <aside className={`${CARD} absolute right-4 top-4 z-10 max-h-[calc(100%-2rem)] w-[300px] space-y-3 overflow-y-auto p-3`}>
          <div>
            <h2 className="mb-2 text-[13px] font-semibold">{t.seoul}</h2>
            <KakaoMap
              className="relative h-[150px] overflow-hidden rounded border border-[#E3E8EE]"
              center={SEOUL}
              level={9}
              rings={HOTSPOT}
              interactive={false}
            />
            <p className="mt-1.5 text-[11px] text-[#5B6675]">{t.hotspot}</p>
          </div>
          <Kpis cameras={live.cameras} openAlerts={live.popups.length} t={t} />
          <CameraThumbs cameras={live.cameras} selected={selected} t={t} onPick={showCamera} />
          {chartCamera && chartZone && (
            <div>
              <div className="mb-1 flex items-baseline justify-between gap-2 text-[12px]">
                <span className="font-medium">{t.densityChart}</span>
                <span className="truncate text-[11px] text-[#5B6675]">{cameraLabel(chartCamera, chartCamera.id)}</span>
              </div>
              <DensityChart
                key={`${chartCamera.id}/${chartZone.id}`}
                camera={chartCamera}
                zoneId={chartZone.id}
                live={live.series[`${chartCamera.id}/${chartZone.id}`] ?? []}
              />
            </div>
          )}
        </aside>

        <Legend t={t} className="absolute bottom-4 left-[352px] z-10" />
      </main>

      <footer className="z-20 flex h-8 shrink-0 items-center justify-between gap-4 border-t border-[#D5DBE3] bg-white px-5 text-[12px]">
        <span className="truncate">
          {latest ? (
            <>
              <span className="mr-2 inline-block size-2 rounded-full" style={{ background: SEVERITY_COLOR[latest.severity] }} />
              <span className="tabular-nums text-[#5B6675]">{eventTime(latest)}</span>{" "}
              {cameraLabel(live.cameras.find((c) => c.id === latest.camera_id), latest.camera_id)} —{" "}
              <span className="font-medium" style={{ color: SEVERITY_COLOR[latest.severity] }}>
                {t.severity[latest.severity]}
              </span>
              , {eventText(latest, t)}
            </>
          ) : (
            <span className="text-[#5B6675]">{t.noEvents}</span>
          )}
        </span>
        <span className="shrink-0 text-[#5B6675]">
          {live.cameras.filter((c) => !c.health.length).length} {t.camerasOnlineTicker} ·{" "}
          {t.modeCount(live.cameras.filter((c) => c.mode !== "replay").length, live.cameras.filter((c) => c.mode === "replay").length)}
        </span>
      </footer>

      {popup && popCamera && (
        <BigCamera
          camera={popCamera}
          t={t}
          event={popup}
          more={live.popups.length - 1}
          noResponse={live.escalated.has(popup.id)}
          onAck={ack}
        />
      )}
      {!popup && bigCamera && <BigCamera camera={bigCamera} t={t} onClose={() => setLarge(null)} />}
      {!popup && !bigCamera && detail && (
        <EventDetail
          event={detail}
          camera={live.cameras.find((c) => c.id === detail.camera_id)}
          t={t}
          onAck={ack}
          onClose={() => setDetail(null)}
        />
      )}
    </div>
  );
}

function worstCamera(cameras: Camera[]): Camera | undefined {
  return [...cameras].sort((a, b) => (peakDensity(b) ?? -1) - (peakDensity(a) ?? -1))[0];
}
