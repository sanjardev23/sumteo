"""Day 5 — FastAPI: cameras, MJPEG stream, events, ack, metrics, WebSocket.

Run: python scripts/serve.py --cameras configs/cameras/crowd_demo.yaml configs/cameras/crossing_demo.yaml
Day 6: `--replay data/recordings/<id> …` adds replay workers (api/replay.py) on the same queue → Hub → WebSocket path.

One process per camera (ARCHITECTURE §3): in threads the cameras block each other on the GIL (two cameras 4.9 + 3.2
FPS in threads vs 8.8 + 4.1 FPS in processes). Each worker sends frames, its state once a second and its events over a
multiprocessing queue; in the API process a reader thread per camera feeds the Hub.
"""
from __future__ import annotations

import asyncio
import multiprocessing as mp
import queue as queue_errors
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sumteo.analytics.crowd import CrowdLevel
from sumteo.api.hub import Hub
from sumteo.api.replay import load_recording, replay_main
from sumteo.config import load_config
from sumteo.events.escalation import AckTracker
from sumteo.events.notifiers.platform import ROLES, PlatformNotifier, put_reliably, roles_for
from sumteo.events.orders import NOTE_MAX, SENDER_ROLE, STATUS_ROLE, STATUSES, TEXT_KEYS
from sumteo.storage.db import Storage

if TYPE_CHECKING:   # the replay path never imports torch / ultralytics (§2.11); only live workers do
    from sumteo.pipeline import Pipeline

STREAM_WIDTH = 960       # MJPEG frames are scaled down to this width: a dashboard tile doesn't need more
STREAM_FPS = 15
STATE_EVERY_S = 1.0      # camera state (levels, health) is pushed to every client once a second
_QUEUE_SIZE = 64         # per camera; frames are dropped when the API falls behind, events and state never
SIGNBOARD = {            # public signboard text per level (§2.12)
    "GREEN": ("여유 — 편하게 이동하세요", "Clear — walk normally"),
    "YELLOW": ("혼잡 — 천천히 이동하세요", "Busy — please slow down"),
    "ORANGE": ("매우 혼잡 — 다른 길을 이용하세요", "Very crowded — use another route"),
    "RED": ("위험 — 진입하지 마세요, 안내에 따르세요", "Danger — do not enter, follow staff"),
}


def camera_main(camera_path: str, default_path: str, out) -> None:
    """Entry point of a camera worker process."""
    from sumteo.pipeline import Pipeline   # here, not at module level: replay-only servers load no model libraries

    app, camera = load_config(camera_path, default_path)
    app.runtime.update(show_window=False, save_path=None, loop=True)
    pipeline = Pipeline(app, camera, notifiers=[PlatformNotifier(out)])
    last_state = [0.0]

    def on_image(image) -> None:
        h, w = image.shape[:2]
        if w > STREAM_WIDTH:
            image = cv2.resize(image, (STREAM_WIDTH, round(h * STREAM_WIDTH / w)), interpolation=cv2.INTER_AREA)
        ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ok:
            try:
                out.put_nowait({"kind": "frame", "jpeg": jpeg.tobytes()})
            except queue_errors.Full:
                pass

    def on_frame(ts, metrics, events) -> None:
        now = time.time()
        if now - last_state[0] >= STATE_EVERY_S:
            last_state[0] = now
            put_reliably(out, {"kind": "state", "camera": camera_state(pipeline)})

    put_reliably(out, {"kind": "state", "camera": camera_state(pipeline)})
    pipeline.run(on_frame=on_frame, on_image=on_image)


def camera_state(p: Pipeline) -> dict:
    zones = []
    for zone in p.zones:
        m, analyzer = p.metrics.get(zone.id), p.analyzers.get(zone.id)
        zones.append({
            "id": zone.id, "area_m2": p.zone_areas.get(zone.id),
            "level": m.level.value if m else None, "label": m.level.label if m else None,
            "density_ppm2": m.density_ppm2 if m else None, "count": m.count if m else None,
            "count_source": m.count_source if m else None, "speed_mps": m.speed_mps if m else None,
            "active": p.active.get(zone.id, []),
            "thresholds": {lvl.value.lower(): v for lvl, v in analyzer.thresholds.items()} if analyzer else None,
        })
    return {
        "id": p.camera.id, "name": p.camera.name or p.camera.id, "mode": "live", "zones": zones,
        "health": list(p.health.problems),
        "location": p.camera.location.model_dump() if p.camera.location else None,
        # Day 2 promise (§2.1, §2.12): a camera with its own level thresholds is a demo and must say so.
        "demo": {"overridden": p.demo_levels is not None, "levels": p.demo_levels},
    }


def with_main(state: dict, main_camera: str | None) -> dict:
    """The camera state as clients get it: marked `main` for the one dashboards show first / large (§2.12)."""
    return {**state, "main": state["id"] == main_camera}


class Ack(BaseModel):
    role: str


class AckMany(BaseModel):
    role: str
    ids: list[str]


ACK_MANY_MAX = 500   # one control-room click; more would hide what is being acknowledged


class NewOrder(BaseModel):
    camera_id: str
    text_key: str
    role: str
    zone_id: str | None = None
    event_id: str | None = None
    note: str | None = None


class OrderStatus(BaseModel):
    status: str
    role: str


def create_app(camera_paths: list[str], default_path: str = "configs/default.yaml",
               replay_dirs: list[str] = ()) -> FastAPI:
    hub = Hub()
    manifests = {str(d): load_recording(d, default_path) for d in replay_dirs}   # a stale recording refuses to start
    first = camera_paths[0] if camera_paths else next(iter(manifests.values()))["camera_config"]
    defaults, _ = load_config(first, default_path)
    routes = defaults.notifiers["routes"]
    main_camera = defaults.api.get("main_camera")
    tracker = AckTracker(defaults.notifiers["ack_timeout_s"])
    storage = Storage(defaults.storage["db_path"])
    snapshot_dir = Path(defaults.events["snapshot_dir"])
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    ctx = mp.get_context("spawn")
    sources = {load_config(path, default_path)[1].id: path for path in camera_paths}   # camera id → YAML
    replays = {m["camera_id"]: d for d, m in manifests.items()}                         # camera id → recording
    if both := sources.keys() & replays.keys():
        raise ValueError(f"camera both live and replayed: {sorted(both)}")
    sources.update({cid: manifests[d]["camera_config"] for cid, d in replays.items()})
    queues = {cid: ctx.Queue(_QUEUE_SIZE) for cid in sources}
    workers = {cid: ctx.Process(target=camera_main, args=(path, default_path, queues[cid]), name=f"camera-{cid}",
                                daemon=True) for cid, path in sources.items() if cid not in replays}
    workers.update({cid: ctx.Process(target=replay_main, args=(d, default_path, queues[cid]), name=f"replay-{cid}",
                                     daemon=True) for cid, d in replays.items()})
    states: dict[str, dict] = {}
    started = time.time()

    def read(camera_id: str) -> None:
        q = queues[camera_id]
        while True:
            msg = q.get()
            if msg["kind"] == "frame":
                hub.set_frame(camera_id, msg["jpeg"])
            elif msg["kind"] == "state":
                state = with_main(msg["camera"], main_camera)
                states[camera_id] = state
                hub.publish({"type": "camera", "camera": state})
            elif msg["kind"] == "event":
                event = msg["event"]
                roles = roles_for(routes, event["severity"])
                if roles:
                    hub.publish({"type": "event", "event": event}, roles)
                tracker.track(event["id"], event["severity"], event["acknowledged"])

    async def escalate() -> None:
        while True:
            await asyncio.sleep(1.0)
            for event_id in tracker.due():
                storage.mark_escalated(event_id, time.time())
                row = storage.event(event_id)
                if row is None:
                    continue
                print(f"\033[31mESCALATION: CRITICAL {row['type']} zone {row['zone_id']} on {row['camera_id']} "
                      f"not acknowledged in {tracker.timeout_s:.0f} s → admin\033[0m")
                hub.publish({"type": "escalation", "event": row}, {"admin"})

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        hub.attach(asyncio.get_running_loop())
        for camera_id, worker in workers.items():
            worker.start()
            threading.Thread(target=read, args=(camera_id,), name=f"read-{camera_id}", daemon=True).start()
        task = asyncio.create_task(escalate())
        yield
        task.cancel()
        for worker in workers.values():
            worker.terminate()

    app = FastAPI(title="Sumteo", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.mount("/snapshots", StaticFiles(directory=snapshot_dir), name="snapshots")

    def _known(camera_id: str) -> None:
        if camera_id not in sources:
            raise HTTPException(404, f"unknown camera {camera_id}")

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    @app.get("/cameras")
    async def cameras() -> list[dict]:
        return [states[cid] for cid in sources if cid in states]

    @app.get("/cameras/{camera_id}/stream")
    async def stream(camera_id: str) -> StreamingResponse:
        _known(camera_id)

        async def frames():
            last = -1
            while True:
                current = hub.frame(camera_id)
                if current and current[0] != last:
                    last, jpeg = current
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                await asyncio.sleep(1 / STREAM_FPS)

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/cameras/{camera_id}/frame.jpg")
    async def frame(camera_id: str) -> Response:
        """Latest blurred frame. Thumbnails poll this: browsers allow ~6 connections per host, and every MJPEG
        stream holds one open, so only the preview and the enlarged view stream."""
        _known(camera_id)
        current = hub.frame(camera_id)
        if current is None:
            raise HTTPException(404, "no frame yet")
        return Response(current[1], media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/events")
    async def events(camera: str | None = None, severity: str | None = None, limit: int = 200) -> list[dict]:
        return storage.events(camera, severity, limit)

    @app.get("/events/{event_id}")
    async def event(event_id: str) -> dict:
        row = storage.event(event_id)
        if row is None:
            raise HTTPException(404, "unknown event")
        return row

    @app.post("/events/{event_id}/ack")
    async def ack(event_id: str, body: Ack) -> dict:
        if body.role not in ROLES:
            raise HTTPException(400, f"role must be one of {ROLES}")
        row = storage.acknowledge(event_id, body.role, time.time())
        if row is None:
            raise HTTPException(404, "unknown event")
        tracker.ack(event_id)
        hub.publish({"type": "ack", "event": row})
        return row

    @app.post("/orders")
    async def new_order(body: NewOrder) -> dict:
        """Control room → guards (§2.8): only admin sends; a fixed text key, an optional short note."""
        if body.role != SENDER_ROLE:
            raise HTTPException(403, "only admin sends orders")
        _known(body.camera_id)
        if body.text_key not in TEXT_KEYS:
            raise HTTPException(400, f"text_key must be one of {TEXT_KEYS}")
        note = (body.note or "").strip() or None
        if note and len(note) > NOTE_MAX:
            raise HTTPException(400, f"note is limited to {NOTE_MAX} characters")
        row = storage.add_order(body.camera_id, body.text_key, time.time(), body.zone_id, body.event_id, note)
        hub.publish({"type": "order", "order": row}, {"security"})
        hub.publish({"type": "order_update", "order": row}, {"admin"})
        return row

    @app.post("/orders/{order_id}/status")
    async def order_status(order_id: str, body: OrderStatus) -> dict:
        if body.role != STATUS_ROLE:
            raise HTTPException(403, "only security moves an order's status")
        if body.status not in STATUSES:
            raise HTTPException(400, f"status must be one of {STATUSES}")
        try:
            row = storage.move_order(order_id, body.status, body.role, time.time())
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        if row is None:
            raise HTTPException(404, "unknown order")
        hub.publish({"type": "order_update", "order": row})
        return row

    @app.get("/orders")
    async def orders(camera: str | None = None, status: str | None = None, limit: int = 100) -> list[dict]:
        return storage.orders(camera, status, limit)

    @app.post("/events/ack")
    async def ack_many(body: AckMany) -> list[dict]:
        """Control room "Acknowledge all": each listed alert goes through the same path as a single ack (first ack
        wins, its escalation is cancelled, every client is told). Admin only; the dashboard confirms first."""
        if body.role != "admin":
            raise HTTPException(403, "only admin acknowledges alerts in bulk")
        if len(body.ids) > ACK_MANY_MAX:
            raise HTTPException(400, f"at most {ACK_MANY_MAX} alerts per call")
        now, rows = time.time(), []
        for event_id in dict.fromkeys(body.ids):
            row = storage.acknowledge(event_id, body.role, now, via="bulk")
            if row is None:
                continue
            tracker.ack(event_id)
            hub.publish({"type": "ack", "event": row})
            rows.append(row)
        return rows

    @app.get("/metrics/{camera_id}")
    async def metrics(camera_id: str, since: float = 0.0) -> list[dict]:
        _known(camera_id)
        return storage.metrics(camera_id, since)

    @app.get("/signboard/{zone_id}")
    async def signboard(zone_id: str) -> dict:
        for state in states.values():
            for zone in state["zones"]:
                if zone["id"] == zone_id:
                    level = zone["level"] or CrowdLevel.GREEN.value
                    ko, en = SIGNBOARD[level]
                    return {"zone": zone_id, "camera": state["id"], "level": level, "label": CrowdLevel[level].label,
                            "message_ko": ko, "message_en": en, "demo": state["demo"]["overridden"]}
        raise HTTPException(404, f"unknown zone {zone_id}")

    @app.websocket("/ws")
    async def ws(socket: WebSocket, role: str = "admin") -> None:
        if role not in ROLES:
            await socket.close(code=1008)
            return
        await socket.accept()
        queue = hub.subscribe(role)
        try:
            # Alerts stay open until acknowledged (§2.8): a reload or a phone reconnecting gets them back as pop-ups.
            severities = {s for s in ("WARNING", "CRITICAL") if role in roles_for(routes, s)}
            await socket.send_json({"type": "hello", "role": role, "cameras": [states[c] for c in sources if c in states],
                                    "open": storage.open_alerts(severities, started)})
            while True:
                await socket.send_json(await queue.get())
        except WebSocketDisconnect:
            pass
        finally:
            hub.unsubscribe(queue)

    return app
