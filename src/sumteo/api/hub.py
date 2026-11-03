"""Day 5 — pub/sub inside the API process: camera messages (read from the worker processes' queues on threads) fan out
to the WebSocket clients, each of which owns an asyncio queue on the API loop. The latest JPEG per camera is kept for
the MJPEG stream (ARCHITECTURE §3).
"""
from __future__ import annotations

import asyncio
import threading

_QUEUE_SIZE = 500   # a client that stops reading loses old messages, never blocks a camera


class Hub:
    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subs: dict[asyncio.Queue, str] = {}
        self._lock = threading.Lock()
        self._frames: dict[str, tuple[int, bytes]] = {}   # camera id → (frame number, JPEG)

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, role: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(_QUEUE_SIZE)
        with self._lock:
            self._subs[queue] = role
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subs.pop(queue, None)

    def publish(self, message: dict, roles: set[str] | None = None) -> None:
        """Thread-safe. `roles` None = every connected client."""
        if self._loop is None:
            return
        with self._lock:
            targets = [q for q, role in self._subs.items() if roles is None or role in roles]
        for queue in targets:
            self._loop.call_soon_threadsafe(_put, queue, message)

    def set_frame(self, camera_id: str, jpeg: bytes) -> None:
        number = self._frames.get(camera_id, (0, b""))[0] + 1
        self._frames[camera_id] = (number, jpeg)

    def frame(self, camera_id: str) -> tuple[int, bytes] | None:
        return self._frames.get(camera_id)


def _put(queue: asyncio.Queue, message: dict) -> None:
    if queue.full():
        queue.get_nowait()
    queue.put_nowait(message)
