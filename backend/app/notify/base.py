from __future__ import annotations

from typing import Protocol

from app.domain.types import ViolationEvent


class Notifier(Protocol):
    def notify(self, event: ViolationEvent) -> None: ...


def format_lines(event: ViolationEvent, public_url: str | None = None) -> dict:
    zone = event.zone or "hors zone"
    missing = ", ".join(sorted(event.missing)) or "—"
    subject = f"[Argus] Infraction EPI — {zone} (#{event.track_id})"
    facts = [
        ("Zone", zone),
        ("Personne", f"#{event.track_id}"),
        ("EPI manquants", missing),
        ("Caméra", event.camera),
    ]
    text = (
        "Infraction EPI confirmée\n"
        f"Zone : {zone}\n"
        f"Personne : #{event.track_id}\n"
        f"EPI manquants : {missing}\n"
        f"Caméra : {event.camera}"
    )
    link = f"{public_url.rstrip('/')}/dashboard" if public_url else None
    return {"title": "Infraction EPI confirmée", "subject": subject,
            "text": text, "facts": facts, "link": link}


class NotificationDispatcher:
    def __init__(self, notifiers: list[Notifier]):
        self._notifiers = notifiers

    def notify(self, event: ViolationEvent) -> None:
        for n in self._notifiers:
            try:
                n.notify(event)
            except Exception:
                pass  # un canal en panne n'empêche pas les autres

    def __len__(self) -> int:
        return len(self._notifiers)
