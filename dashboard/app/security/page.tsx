"use client";
// Day 5 — on-site guards: zone levels, big alert cards, Acknowledge. Built for a phone.
// Day 6 v2 (§2.12): every alert shows its camera, snapshot and place on a small map; orders from the control room
// (§2.8) arrive with the same camera view and go "On my way" → "Done".
import { KakaoMap } from "@/components/KakaoMap";
import { SoundGate } from "@/components/TopBar";
import {
  CARD,
  Clock,
  FONT,
  LangSwitch,
  LevelTag,
  LiveDot,
  LiveFrame,
  OrderStatusTag,
  ReplayTag,
  cameraLabel,
  eventText,
  eventTime,
  wallClock,
  worstLevel,
} from "@/components/wall";
import {
  LEVEL_COLOR,
  SEVERITY_COLOR,
  acknowledge,
  setOrderStatus,
  snapshotUrl,
  type Camera,
  type Order,
  type SumteoEvent,
} from "@/lib/api";
import { dict, useLang, type Dict } from "@/lib/i18n";
import { useLive } from "@/lib/useLive";

export default function Security() {
  const live = useLive("security");
  const t = dict[useLang()];
  const camera = (id: string) => live.cameras.find((c) => c.id === id);
  const ack = async (e: SumteoEvent) => {
    const row = await acknowledge(e.id, "security");
    if (row) live.applyAck(row);
  };
  const move = async (o: Order, status: "on_my_way" | "done") => {
    const row = await setOrderStatus(o.id, status);
    if (row) live.applyOrder(row);
  };
  const main = live.cameras.find((c) => c.main);
  const openOrders = live.orders.filter((o) => o.status !== "done");
  const doneOrders = live.orders.filter((o) => o.status === "done").slice(0, 3);

  return (
    <div className="min-h-screen bg-[#EEF1F4] text-[#1B2430]" style={{ fontFamily: FONT }}>
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-[#D5DBE3] bg-white px-4 py-2.5">
        <div className="leading-tight">
          <div className="text-[16px] font-semibold">
            Sumteo <span className="font-normal text-[#5B6675]">숨터</span>
          </div>
          <div className="text-[11px] text-[#5B6675]">
            {t.guardView} · {t.area}
          </div>
        </div>
        <div className="flex items-center gap-3 text-[12px]">
          <LiveDot connected={live.connected} cameras={live.cameras} t={t} />
          <span className="hidden sm:inline">
            <Clock />
          </span>
          <LangSwitch />
        </div>
      </header>
      <SoundGate />

      <main className="mx-auto max-w-lg space-y-4 p-3">
        {main && (
          <section className={`${CARD} overflow-hidden`}>
            <LiveFrame camera={main} className="aspect-video w-full" />
            <div className="flex items-start justify-between gap-2 p-3">
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wide text-[#5B6675]">{t.mainCamera}</div>
                <div className="text-[15px] font-semibold">{cameraLabel(main, main.id)}</div>
                <Tags camera={main} t={t} />
              </div>
              <LevelTag level={worstLevel(main)} t={t} />
            </div>
          </section>
        )}

        <section>
          <h2 className="mb-2 px-1 text-[13px] font-semibold">
            {t.orders} <span className="font-normal text-[#5B6675]">{openOrders.length}</span>
          </h2>
          {!openOrders.length && <p className={`${CARD} p-4 text-center text-[13px] text-[#5B6675]`}>{t.noOrders}</p>}
          <div className="space-y-3">
            {openOrders.map((o) => (
              <OrderCard key={o.id} order={o} camera={camera(o.camera_id)} t={t} onMove={move} />
            ))}
          </div>
          {!!doneOrders.length && (
            <ul className="mt-2 space-y-1 px-1">
              {doneOrders.map((o) => (
                <li key={o.id} className="flex items-center justify-between gap-2 text-[12px] text-[#5B6675]">
                  <span className="truncate">
                    {t.orderTexts[o.text_key]} · {cameraLabel(camera(o.camera_id), o.camera_id)}
                  </span>
                  <span className="flex shrink-0 items-center gap-1.5 tabular-nums">
                    {wallClock(o.done_at ?? o.created_at)}
                    <OrderStatusTag status={o.status} t={t} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h2 className="mb-2 px-1 text-[13px] font-semibold">
            {t.alerts} <span className="font-normal text-[#5B6675]">{live.popups.length}</span>
          </h2>
          {!live.popups.length && <p className={`${CARD} p-4 text-center text-[13px] text-[#5B6675]`}>{t.noEvents}</p>}
          <div className="space-y-3">
            {live.popups.map((e) => (
              <AlertCard key={e.id} event={e} camera={camera(e.camera_id)} t={t} onAck={ack} />
            ))}
          </div>
        </section>

        <section className={`${CARD} divide-y divide-[#EEF1F4]`}>
          {live.cameras.map((c) => (
            <div key={c.id} className="flex items-center justify-between gap-2 px-3 py-2">
              <div className="min-w-0">
                <div className="truncate text-[13px] font-medium">{cameraLabel(c, c.id)}</div>
                <div className="text-[11px] tabular-nums text-[#5B6675]">
                  {c.zones.map((z) => (z.density_ppm2 != null ? `${z.density_ppm2.toFixed(2)}/m²` : "—")).join(" · ")}
                </div>
              </div>
              <LevelTag level={worstLevel(c)} t={t} />
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}

function Tags({ camera, t }: { camera: Camera; t: Dict }) {
  const l = camera.demo.levels;
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1.5">
      {camera.mode === "replay" && <ReplayTag t={t} short />}
      {camera.demo.overridden && l && (
        <span className="text-[10px] font-semibold text-[#C62828]">{t.demo(l.yellow, l.orange, l.red)}</span>
      )}
    </div>
  );
}

/** Where the camera is: a small, still Kakao map with its pin. */
function MiniMap({ camera }: { camera: Camera }) {
  if (!camera.location) return null;
  const { lat, lon } = camera.location;
  const level = worstLevel(camera);
  return (
    <KakaoMap
      className="relative h-28 overflow-hidden rounded border border-[#E3E8EE]"
      center={{ lat, lon }}
      level={3}
      interactive={false}
      pins={[{ id: camera.id, lat, lon, color: level ? LEVEL_COLOR[level] : "#9AA4B2", label: cameraLabel(camera, camera.id), level }]}
    />
  );
}

function AlertCard({ event, camera, t, onAck }: { event: SumteoEvent; camera?: Camera; t: Dict; onAck: (e: SumteoEvent) => void }) {
  const snap = snapshotUrl(event.snapshot_path);
  return (
    <article className={`${CARD} overflow-hidden border-l-4`} style={{ borderLeftColor: SEVERITY_COLOR[event.severity] }}>
      <div className="p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[15px] font-semibold" style={{ color: SEVERITY_COLOR[event.severity] }}>
            {t.severity[event.severity]} · {eventText(event, t)}
          </span>
          <span className="text-[11px] tabular-nums text-[#5B6675]">{eventTime(event)}</span>
        </div>
        <div className="text-[13px] font-medium">{cameraLabel(camera, event.camera_id)}</div>
        {camera && <Tags camera={camera} t={t} />}
      </div>
      {camera && <LiveFrame camera={camera} className="aspect-video w-full" />}
      <div className="grid grid-cols-2 gap-2 p-3">
        {snap && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={snap} alt={t.snapshot} className="h-28 w-full rounded bg-[#1B2430] object-cover" />
        )}
        {camera && <MiniMap camera={camera} />}
      </div>
      <div className="px-3 pb-3">
        <button
          onClick={() => onAck(event)}
          className="w-full rounded bg-[#1D4F91] py-3 text-[16px] font-semibold text-white hover:bg-[#163E73]"
        >
          {t.onMyWay}
        </button>
      </div>
    </article>
  );
}

function OrderCard({
  order,
  camera,
  t,
  onMove,
}: {
  order: Order;
  camera?: Camera;
  t: Dict;
  onMove: (o: Order, status: "on_my_way" | "done") => void;
}) {
  return (
    <article className={`${CARD} overflow-hidden border-l-4 border-l-[#1D4F91]`}>
      <div className="p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[16px] font-semibold text-[#1D4F91]">{t.orderTexts[order.text_key]}</span>
          <OrderStatusTag status={order.status} t={t} />
        </div>
        <div className="text-[13px] font-medium">{cameraLabel(camera, order.camera_id)}</div>
        {order.note && <p className="mt-1 rounded bg-[#F5F7FA] px-2 py-1.5 text-[13px]">{order.note}</p>}
        <div className="mt-1 text-[11px] tabular-nums text-[#5B6675]">{wallClock(order.created_at)}</div>
      </div>
      {camera && <LiveFrame camera={camera} className="aspect-video w-full" />}
      {camera && (
        <div className="px-3 pt-3">
          <MiniMap camera={camera} />
        </div>
      )}
      <div className="flex gap-2 p-3">
        {order.status === "sent" && (
          <button
            onClick={() => onMove(order, "on_my_way")}
            className="flex-1 rounded bg-[#1D4F91] py-3 text-[16px] font-semibold text-white hover:bg-[#163E73]"
          >
            {t.onMyWay}
          </button>
        )}
        <button
          onClick={() => onMove(order, "done")}
          className={`flex-1 rounded py-3 text-[16px] font-semibold ${
            order.status === "sent"
              ? "border border-[#2E7D32] text-[#2E7D32] hover:bg-[#EEF7EE]"
              : "bg-[#2E7D32] text-white hover:bg-[#256628]"
          }`}
        >
          {t.markDone}
        </button>
      </div>
    </article>
  );
}
