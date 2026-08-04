from __future__ import annotations

import json
import urllib.request

from app.domain.types import ViolationEvent
from app.notify.base import format_lines


def _urllib_post(url: str, payload: bytes) -> None:
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=10).close()


class TeamsNotifier:
    def __init__(self, webhook_url: str, public_url=None, poster=_urllib_post):
        self._url = webhook_url
        self._public_url = public_url
        self._post = poster

    def notify(self, event: ViolationEvent) -> None:
        info = format_lines(event, self._public_url)
        card: dict = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": info["subject"],
            "themeColor": "F0464B",
            "title": info["title"],
            "sections": [{"facts": [{"name": k, "value": v} for k, v in info["facts"]]}],
        }
        if info["link"]:
            card["potentialAction"] = [{
                "@type": "OpenUri", "name": "Ouvrir le dashboard",
                "targets": [{"os": "default", "uri": info["link"]}],
            }]
        self._post(self._url, json.dumps(card).encode("utf-8"))
