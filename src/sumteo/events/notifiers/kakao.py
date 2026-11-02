"""Day 6 (optional) — KakaoTalk push for CRITICAL alerts.

Demo: Kakao Developers "send to me" (나에게 보내기) Talk Message API with the operator's own OAuth token.
Production would use a business channel + AlimTalk (알림톡) instead.
Sends text + a link to the event in the dashboard, not the photo, so snapshots stay on the platform.
"""
from __future__ import annotations

from sumteo.events.models import Event


class KakaoNotifier:
    def __init__(self, access_token: str, dashboard_url: str):
        self.access_token, self.dashboard_url = access_token, dashboard_url

    def send(self, event: Event) -> None:
        # TODO(Day 6): POST https://kapi.kakao.com/v2/api/talk/memo/default/send — level label, zone, reasons, event link
        raise NotImplementedError("Day 6")
