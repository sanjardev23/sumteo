"use client";
// Day 5 — control room: camera grid, priority pop-up until acknowledged, alert feed, density charts, event detail.
import { useState } from "react";
import { DensityChart } from "@/components/DensityChart";
import { AckButton, AlertFeed, CameraTile, DemoTag, EventDetail, HealthBadge, Modal, ZoneLine, reasons } from "@/components/ui";
import { SoundGate, TopBar } from "@/components/TopBar";
import { SEVERITY_COLOR, acknowledge, streamUrl, type SumteoEvent } from "@/lib/api";
import { useLive } from "@/lib/useLive";

export default function Admin() {
  const live = useLive("admin");
  const [detail, setDetail] = useState<SumteoEvent | null>(null);
  const [large, setLarge] = useState<string | null>(null);
  const ack = async (e: SumteoEvent) => {
    const row = await acknowledge(e.id, "admin");
    if (row) {
      live.applyAck(row);
      if (detail?.id === row.id) setDetail(row);
    }
  };
  // Priority pop-up: the most severe unacknowledged live alert, its camera feed large on top (§2.12).
  const popup = [...live.popups].sort((a, b) => (b.severity === "CRITICAL" ? 1 : 0) - (a.severity === "CRITICAL" ? 1 : 0))[0];
  const popCamera = popup && live.cameras.find((c) => c.id === popup.camera_id);
  const bigCamera = large ? live.cameras.find((c) => c.id === large) : undefined;

  return (
    <div className="min-h-screen">
      <TopBar role="admin" connected={live.connected} />
      <SoundGate />
      <div className="grid gap-4 p-4 xl:grid-cols-[1fr_380px]">
        <section className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            {live.cameras.map((c) => (
              <CameraTile key={c.id} camera={c} onOpen={() => setLarge(c.id)} />
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {live.cameras.flatMap((c) =>
              c.zones.map((z) => (
                <div key={`${c.id}/${z.id}`} className="rounded-lg bg-zinc-900 p-3">
                  <div className="mb-1 text-sm text-zinc-400">
                    {c.name} · {z.id} · people/m²
                  </div>
                  <DensityChart camera={c} zoneId={z.id} live={live.series[`${c.id}/${z.id}`] ?? []} />
                  <DemoTag camera={c} />
                </div>
              )),
            )}
          </div>
        </section>
        <aside>
          <h2 className="mb-2 font-semibold">Alerts · 경보</h2>
          <AlertFeed events={live.events} escalated={live.escalated} onAck={ack} onOpen={setDetail} />
        </aside>
      </div>

      {popup && popCamera && (
        <Modal>
          <div className="mb-2 flex items-center justify-between gap-3">
            <h2 className="text-2xl font-bold" style={{ color: SEVERITY_COLOR[popup.severity] }}>
              {live.escalated.has(popup.id) && <span className="mr-2 rounded bg-red-600 px-2 text-base text-white">NO RESPONSE</span>}
              {popup.severity} · {popCamera.name} · {popup.zone_id ?? "camera"}
            </h2>
            {live.popups.length > 1 && <span className="text-sm text-zinc-400">+{live.popups.length - 1} more waiting</span>}
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={streamUrl(popCamera.id)} alt={popCamera.name} className="mb-3 max-h-[55vh] w-full rounded bg-black object-contain" />
          <p className="mb-1 text-lg">{reasons(popup)}</p>
          <div className="mb-3 space-y-1">
            {popCamera.zones.map((z) => (
              <ZoneLine key={z.id} zone={z} />
            ))}
            <HealthBadge camera={popCamera} />
            <DemoTag camera={popCamera} />
          </div>
          <AckButton event={popup} onAck={ack} big />
        </Modal>
      )}
      {!popup && bigCamera && (
        <Modal onClose={() => setLarge(null)}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={streamUrl(bigCamera.id)} alt={bigCamera.name} className="mb-3 max-h-[75vh] w-full rounded bg-black object-contain" />
          {bigCamera.zones.map((z) => (
            <ZoneLine key={z.id} zone={z} />
          ))}
          <DemoTag camera={bigCamera} />
        </Modal>
      )}
      {!popup && detail && <EventDetail event={detail} onAck={ack} onClose={() => setDetail(null)} />}
    </div>
  );
}
