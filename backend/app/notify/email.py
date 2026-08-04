from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.domain.types import ViolationEvent
from app.notify.base import format_lines


def _smtp_send(msg: EmailMessage, host: str, port: int,
               user: str | None, password: str | None) -> None:
    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.starttls()
        if user:
            smtp.login(user, password or "")
        smtp.send_message(msg)


class EmailNotifier:
    def __init__(self, host, port, sender, recipients, user=None, password=None,
                 public_url=None, send=_smtp_send):
        self._host = host
        self._port = port
        self._sender = sender
        self._recipients = recipients
        self._user = user
        self._password = password
        self._public_url = public_url
        self._send = send

    def notify(self, event: ViolationEvent) -> None:
        info = format_lines(event, self._public_url)
        msg = EmailMessage()
        msg["Subject"] = info["subject"]
        msg["From"] = self._sender
        msg["To"] = ", ".join(self._recipients)
        body = info["text"] + (f"\n\n{info['link']}" if info["link"] else "")
        msg.set_content(body)
        self._send(msg, self._host, self._port, self._user, self._password)
