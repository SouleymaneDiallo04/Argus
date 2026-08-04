from __future__ import annotations

import json

from app.domain.types import ViolationEvent
from app.notify.teams import TeamsNotifier


def _ev():
    return ViolationEvent(track_id=37, zone="Fonderie",
                          missing=frozenset({"helmet", "shoes"}), timestamp=0.0, camera="cam-1")


def test_teams_notifier_poste_une_carte():
    captured = {}

    def fake_post(url, payload):
        captured.update(url=url, payload=payload)

    TeamsNotifier("https://webhook", public_url="https://argus.example",
                  poster=fake_post).notify(_ev())

    assert captured["url"] == "https://webhook"
    text = json.dumps(json.loads(captured["payload"]))
    assert "Fonderie" in text and "#37" in text and "helmet" in text
    assert "argus.example/dashboard" in text
