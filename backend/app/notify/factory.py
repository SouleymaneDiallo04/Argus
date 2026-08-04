from __future__ import annotations

import os

from app.notify.base import NotificationDispatcher, Notifier
from app.notify.email import EmailNotifier
from app.notify.teams import TeamsNotifier


def build_dispatcher(env=os.environ) -> NotificationDispatcher:
    notifiers: list[Notifier] = []
    public_url = env.get("ARGUS_PUBLIC_URL")

    host, to = env.get("ARGUS_SMTP_HOST"), env.get("ARGUS_SMTP_TO")
    if host and to:
        notifiers.append(EmailNotifier(
            host=host,
            port=int(env.get("ARGUS_SMTP_PORT", "587")),
            sender=env.get("ARGUS_SMTP_FROM", "argus@localhost"),
            recipients=[r.strip() for r in to.split(",") if r.strip()],
            user=env.get("ARGUS_SMTP_USER"),
            password=env.get("ARGUS_SMTP_PASSWORD"),
            public_url=public_url,
        ))

    webhook = env.get("ARGUS_TEAMS_WEBHOOK")
    if webhook:
        notifiers.append(TeamsNotifier(webhook, public_url=public_url))

    return NotificationDispatcher(notifiers)
