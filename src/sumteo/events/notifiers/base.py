from __future__ import annotations

from typing import Protocol

from sumteo.events.models import Event


class Notifier(Protocol):
    def send(self, event: Event) -> None: ...
