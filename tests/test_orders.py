"""Day 6 — orders control room → guards (ARCHITECTURE §2.8), main camera flag (§2.12), replay repeat limit (§2.11)."""
import json
import queue
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from sumteo.api.replay import Replay
from sumteo.api.server import create_app, with_main
from sumteo.storage.db import Storage

ROOT = Path(__file__).resolve().parents[1]
CAMERA = str(ROOT / "configs/cameras/crowd_demo.yaml")


@pytest.fixture
def client(tmp_path):
    """The API on a temporary database; no lifespan, so no camera workers start."""
    cfg = yaml.safe_load((ROOT / "configs/default.yaml").read_text())
    cfg["storage"]["db_path"] = str(tmp_path / "db.sqlite")
    cfg["events"]["snapshot_dir"] = str(tmp_path / "snaps")
    default = tmp_path / "default.yaml"
    default.write_text(yaml.safe_dump(cfg))
    return TestClient(create_app([CAMERA], str(default)))


def test_admin_sends_and_security_moves_an_order_forward_with_each_steps_time(client):
    sent = client.post("/orders", json={"camera_id": "crowd-demo-1", "text_key": "redirect_exit", "role": "admin",
                                        "note": "Use exit 4"}).json()
    assert sent["status"] == "sent" and sent["created_at"] and sent["on_my_way_at"] is None
    on_way = client.post(f"/orders/{sent['id']}/status", json={"status": "on_my_way", "role": "security"}).json()
    assert on_way["status"] == "on_my_way" and on_way["on_my_way_at"] >= sent["created_at"] and on_way["by_role"] == "security"
    done = client.post(f"/orders/{sent['id']}/status", json={"status": "done", "role": "security"}).json()
    assert done["status"] == "done" and done["done_at"] >= done["on_my_way_at"]
    assert client.get("/orders?status=done").json()[0]["id"] == sent["id"]


def test_order_rules_roles_forward_only_known_text_short_note(client):
    def new(**kw):
        return client.post("/orders", json={"camera_id": "crowd-demo-1", "text_key": "stop_entry", "role": "admin", **kw})
    assert new(role="security").status_code == 403               # only admin sends
    assert new(text_key="dance").status_code == 400                # fixed bilingual list only
    assert new(note="x" * 141).status_code == 400                  # note ≤ 140 characters
    assert new(camera_id="nope").status_code == 404
    order = new().json()
    status = lambda st, role="security": client.post(f"/orders/{order['id']}/status", json={"status": st, "role": role})
    assert status("on_my_way", role="admin").status_code == 403    # only security moves the status
    assert status("done").status_code == 200                       # a step may be skipped
    assert status("on_my_way").status_code == 409                  # never backwards
    assert status("sent").status_code == 409


def test_main_camera_is_marked():
    assert with_main({"id": "crowd-demo-1"}, "crowd-demo-1")["main"] is True
    assert with_main({"id": "crossing-demo-1"}, "crowd-demo-1")["main"] is False


def test_replay_repeat_limit_holds_repeats_back_but_lets_a_rise_through(tmp_path):
    rec = tmp_path / "rec"
    rec.mkdir()
    def event(ts, severity, type_="CROWD_LEVEL"):
        return {"kind": "event", "ts": ts, "event": {"camera_id": "c", "type": type_, "severity": severity, "ts": ts,
                                                   "zone_id": "z", "track_id": None, "details": {}, "snapshot_path": None}}
    entries = [event(1, "INFO"), event(2, "WARNING"), event(3, "CRITICAL"), event(4, "WARNING", "COUNTER_FLOW")]
    (rec / "timeline.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
    (rec / "manifest.json").write_text(json.dumps({"duration_s": 9.0, "fps": 1.0}))   # period = 10 s per loop
    out, now = queue.Queue(), [0.0]
    replay = Replay(rec, out, None, tmp_path / "snaps", repeat_alerts_s=25,
                    clock=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s))
    replay.run(loops=4)                                            # loops start at 0, 10, 20, 30 s of video time
    fired = []
    while not out.empty():
        e = out.get_nowait()["event"]
        fired.append((round(e["ts"]), e["type"], e["severity"]))
    # Loop 1 emits all (each level is a rise); loops 2–3 are inside 25 s and held back; loop 4 (31 s) repeats them all.
    assert fired == [(1, "CROWD_LEVEL", "INFO"), (2, "CROWD_LEVEL", "WARNING"), (3, "CROWD_LEVEL", "CRITICAL"),
                     (4, "COUNTER_FLOW", "WARNING"), (31, "CROWD_LEVEL", "INFO"), (32, "CROWD_LEVEL", "WARNING"),
                     (33, "CROWD_LEVEL", "CRITICAL"), (34, "COUNTER_FLOW", "WARNING")]


def test_storage_refuses_backward_order_steps(tmp_path):
    storage = Storage(str(tmp_path / "db.sqlite"))
    order = storage.add_order("c", "go_to_camera", 1.0)
    storage.move_order(order["id"], "on_my_way", "security", 2.0)
    with pytest.raises(ValueError):
        storage.move_order(order["id"], "sent", "security", 3.0)
    assert storage.move_order("missing", "done", "security", 4.0) is None


def test_admin_acknowledges_open_alerts_in_bulk(client, tmp_path):
    """Control room "Acknowledge all" (§2.12): admin only, ≤ 500 ids, each one the same as a single ack."""
    from sumteo.events.models import Event, EventType, Severity
    storage = Storage(str(tmp_path / "db.sqlite"))
    ids = []
    for severity in ("CRITICAL", "WARNING", "WARNING"):
        e = Event("crowd-demo-1", EventType.CROWD_LEVEL, Severity(severity), ts=1.0, zone_id="main")
        storage.add_event(e)
        ids.append(e.id)
    client.post(f"/events/{ids[0]}/ack", json={"role": "security"})            # already taken by a guard
    assert client.post("/events/ack", json={"role": "security", "ids": ids}).status_code == 403
    assert client.post("/events/ack", json={"role": "admin", "ids": ["x"] * 501}).status_code == 400
    rows = client.post("/events/ack", json={"role": "admin", "ids": ids + [ids[1], "unknown"]}).json()
    assert [r["id"] for r in rows] == ids                                         # duplicates and unknown ids skipped
    assert all(r["acknowledged"] for r in rows)
    assert rows[0]["acknowledged_by"] == "security"                               # first ack still wins
    assert {r["acknowledged_by"] for r in rows[1:]} == {"admin"}
    assert [r["acknowledged_via"] for r in rows] == ["single", "bulk", "bulk"]     # audit: bulk ≠ reviewed



def test_signboard_names_the_place_and_says_live_or_replay(client):
    """Public signboard (§2.12): level text in Korean and English, the place, the DEMO and REPLAY flags."""
    from sumteo.api.server import signboard_view
    state = {"id": "crossing-demo-1", "mode": "replay", "demo": {"overridden": True},
             "location": {"label": "Itaewon-ro east"}, "zones": [{"id": "crossing", "level": "RED"}]}
    board = signboard_view([state], "crossing")
    assert board["camera"] == "crossing-demo-1" and board["place"] == "Itaewon-ro east"
    assert board["level"] == "RED" and board["message_ko"] and board["message_en"]
    assert board["replay"] is True and board["demo"] is True
    assert signboard_view([{**state, "zones": [{"id": "crossing", "level": None}]}], "crossing")["level"] == "GREEN"
    assert signboard_view([state], "nowhere") is None
    assert client.get("/signboard/nowhere").status_code == 404
