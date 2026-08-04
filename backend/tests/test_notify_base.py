from __future__ import annotations

from app.domain.types import ViolationEvent
from app.notify.base import NotificationDispatcher, format_lines


def _ev(track_id=37, zone="Fonderie", missing=("helmet",)):
    return ViolationEvent(track_id=track_id, zone=zone, missing=frozenset(missing),
                          timestamp=0.0, camera="cam-1")


def test_format_lines_contient_les_faits():
    info = format_lines(_ev(), public_url="https://argus.example")
    assert "Fonderie" in info["subject"]
    assert "#37" in info["text"]
    assert "helmet" in info["text"]
    assert info["link"] == "https://argus.example/dashboard"


def test_format_lines_sans_lien_si_pas_d_url():
    assert format_lines(_ev())["link"] is None


def test_dispatcher_fan_out_et_isole_les_pannes():
    calls: list[str] = []

    class Good:
        def notify(self, e):
            calls.append("good")

    class Bad:
        def notify(self, e):
            raise RuntimeError("boom")

    d = NotificationDispatcher([Bad(), Good()])
    d.notify(_ev())
    assert calls == ["good"]          # Bad a levé, Good est quand même appelé
    assert len(d) == 2
