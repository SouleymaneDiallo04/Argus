from __future__ import annotations

from app.domain.types import ViolationEvent
from app.notify.email import EmailNotifier


def _ev():
    return ViolationEvent(track_id=37, zone="Fonderie", missing=frozenset({"helmet"}),
                          timestamp=0.0, camera="cam-1")


def test_email_notifier_construit_et_envoie():
    captured = {}

    def fake_send(msg, host, port, user, password):
        captured.update(msg=msg, host=host, port=port)

    EmailNotifier(host="smtp.x", port=587, sender="argus@x",
                  recipients=["hse@x", "chef@x"], send=fake_send).notify(_ev())

    msg = captured["msg"]
    assert "Fonderie" in msg["Subject"]
    body = msg.get_content()
    assert "#37" in body and "helmet" in body
    assert msg["To"] == "hse@x, chef@x"
    assert captured["host"] == "smtp.x" and captured["port"] == 587
