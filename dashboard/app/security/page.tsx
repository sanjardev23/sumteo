"use client";
// Day 5 — on-site guards: zone levels, big alert cards, Acknowledge. Built for a phone.
import { AckButton, DemoTag, HealthBadge, LevelChip, ago, reasons } from "@/components/ui";
import { SoundGate, TopBar } from "@/components/TopBar";
import { SEVERITY_COLOR, acknowledge, type SumteoEvent } from "@/lib/api";
import { useLive } from "@/lib/useLive";

export default function Security() {
  const live = useLive("security");
  const ack = async (e: SumteoEvent) => {
    const row = await acknowledge(e.id, "security");
    if (row) live.applyAck(row);
  };
  const open = live.popups;
  return (
    <div className="min-h-screen">
      <TopBar role="security" connected={live.connected} />
      <SoundGate />
      <main className="mx-auto max-w-lg space-y-4 p-4">
        {open.map((e) => (
          <div key={e.id} className="rounded-xl border-4 bg-zinc-900 p-4" style={{ borderColor: SEVERITY_COLOR[e.severity] }}>
            <div className="text-2xl font-bold" style={{ color: SEVERITY_COLOR[e.severity] }}>
              {e.severity === "CRITICAL" ? "심각 · Act now" : "주의 · Check the zone"}
            </div>
            <div className="mt-1 text-lg">{reasons(e)}</div>
            <div className="mb-3 text-sm text-zinc-400">
              {e.camera_id} · {e.zone_id ?? "camera"} · {ago(e.created_at)}
            </div>
            <AckButton event={e} onAck={ack} big />
          </div>
        ))}
        {!open.length && <p className="rounded-xl bg-zinc-900 p-4 text-center text-zinc-400">No open alerts · 경보 없음</p>}

        <h2 className="pt-2 font-semibold">My zones · 담당 구역</h2>
        {live.cameras.flatMap((c) =>
          c.zones.map((z) => (
            <div key={`${c.id}/${z.id}`} className="rounded-xl bg-zinc-900 p-4">
              <div className="flex items-center justify-between">
                <span className="font-semibold">{z.id}</span>
                <LevelChip level={z.level} big />
              </div>
              <div className="mt-1 text-sm text-zinc-400">
                {c.name}
                {z.density_ppm2 != null && ` · ${z.density_ppm2.toFixed(2)} /m² · ${Math.round(z.count ?? 0)} people`}
              </div>
              <div className="mt-1"><HealthBadge camera={c} /></div>
              <DemoTag camera={c} />
            </div>
          )),
        )}
      </main>
    </div>
  );
}
