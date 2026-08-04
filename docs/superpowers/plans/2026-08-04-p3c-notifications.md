# P3-c — Notifications (email + Teams) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sur chaque infraction confirmée, notifier par email (SMTP) et Microsoft Teams (webhook), en fan-out non bloquant, sans secret en dur et no-op si non configuré.

**Architecture:** Package `app/notify/` — un protocole `Notifier`, un `NotificationDispatcher` (fan-out isolant les pannes), `EmailNotifier` (stdlib `smtplib`), `TeamsNotifier` (stdlib `urllib`), une fabrique depuis l'env — branché au chemin WS via `run_in_threadpool`.

**Tech Stack:** Python 3.13, FastAPI, `smtplib`/`urllib` (stdlib — zéro nouvelle dépendance), pytest.

## Global Constraints

- **Zéro nouvelle dépendance** (`smtplib`, `email.message`, `urllib` stdlib).
- **Déclenchement sur chaque `ViolationEvent` confirmé** — le debounce (3 s) + cooldown (30 s/personne) du moteur est le filtre anti-flood. **Pas de sévérité/risque côté serveur** (elle vit côté front, décision P3-a).
- **Non bloquant** : dispatch via `await run_in_threadpool(...)` ; une panne de notif ne tue ni le flux ni le journal.
- **Sûr par défaut** : rien de configuré → dispatcher **no-op** (aucun secret requis en test/CI).
- **Injectable en test** : `app.state.notifier` comme `journal`/`snapshots` ; transports (`send`/`poster`) injectables.
- Env : `ARGUS_SMTP_{HOST,PORT,USER,PASSWORD,FROM,TO}`, `ARGUS_TEAMS_WEBHOOK`, `ARGUS_PUBLIC_URL`.
- `ViolationEvent` (dataclass gelée) = `(track_id, zone, missing: frozenset, timestamp: float, camera)`.
- Interpréteur test : **`py -3`**. Suite backend existante (**90**) verte. Commits : conventionnels, anglais, **sans `Co-Authored-By`**.

---

### Task 1: Socle — `Notifier`, `format_lines`, `NotificationDispatcher`

**Files:**
- Create: `backend/app/notify/__init__.py` (vide), `backend/app/notify/base.py`
- Test: `backend/tests/test_notify_base.py`

**Interfaces:**
- Consumes: `ViolationEvent`.
- Produces: `Notifier` (Protocol) ; `format_lines(event, public_url=None) -> dict` (`title`, `subject`, `text`, `facts:[(k,v)]`, `link`) ; `NotificationDispatcher(notifiers)` avec `.notify(event)` (fan-out, isole les pannes) et `__len__`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_notify_base.py`
```python
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
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_notify_base.py -q` → FAIL.

- [ ] **Step 3: Écrire l'implémentation**

`backend/app/notify/__init__.py` : vide.

`backend/app/notify/base.py` :
```python
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
```

- [ ] **Step 4: Lancer le test** — PASS (3).

- [ ] **Step 5: Commit**
```bash
git add backend/app/notify/__init__.py backend/app/notify/base.py backend/tests/test_notify_base.py
git commit -m "feat(backend): notification dispatcher + message formatting"
```

---

### Task 2: `EmailNotifier` (SMTP)

**Files:**
- Create: `backend/app/notify/email.py`
- Test: `backend/tests/test_notify_email.py`

**Interfaces:**
- Consumes: `format_lines` (T1), `ViolationEvent`.
- Produces: `EmailNotifier(host, port, sender, recipients, user=None, password=None, public_url=None, send=_smtp_send)` avec `.notify(event)` ; `send(msg, host, port, user, password)` injectable.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_notify_email.py`
```python
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
```

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `backend/app/notify/email.py`
```python
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
```

- [ ] **Step 4: Lancer le test** — PASS (1).

- [ ] **Step 5: Commit**
```bash
git add backend/app/notify/email.py backend/tests/test_notify_email.py
git commit -m "feat(backend): EmailNotifier (SMTP)"
```

---

### Task 3: `TeamsNotifier` (webhook)

**Files:**
- Create: `backend/app/notify/teams.py`
- Test: `backend/tests/test_notify_teams.py`

**Interfaces:**
- Consumes: `format_lines` (T1), `ViolationEvent`.
- Produces: `TeamsNotifier(webhook_url, public_url=None, poster=_urllib_post)` avec `.notify(event)` ; `poster(url, payload: bytes)` injectable.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_notify_teams.py`
```python
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
```

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `backend/app/notify/teams.py`
```python
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
```

- [ ] **Step 4: Lancer le test** — PASS (1).

- [ ] **Step 5: Commit**
```bash
git add backend/app/notify/teams.py backend/tests/test_notify_teams.py
git commit -m "feat(backend): TeamsNotifier (webhook MessageCard)"
```

---

### Task 4: Fabrique — `build_dispatcher(env)`

**Files:**
- Create: `backend/app/notify/factory.py`
- Test: `backend/tests/test_notify_factory.py`

**Interfaces:**
- Consumes: `EmailNotifier` (T2), `TeamsNotifier` (T3), `NotificationDispatcher` (T1).
- Produces: `build_dispatcher(env=os.environ) -> NotificationDispatcher`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_notify_factory.py`
```python
from __future__ import annotations

from app.notify.factory import build_dispatcher


def test_build_dispatcher_selon_env():
    assert len(build_dispatcher({})) == 0                                   # rien -> no-op
    assert len(build_dispatcher({"ARGUS_SMTP_HOST": "h", "ARGUS_SMTP_TO": "a@b"})) == 1
    assert len(build_dispatcher({"ARGUS_TEAMS_WEBHOOK": "https://w"})) == 1
    assert len(build_dispatcher({
        "ARGUS_SMTP_HOST": "h", "ARGUS_SMTP_TO": "a@b",
        "ARGUS_TEAMS_WEBHOOK": "https://w",
    })) == 2
```

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `backend/app/notify/factory.py`
```python
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
```

- [ ] **Step 4: Lancer le test** — PASS (1).

- [ ] **Step 5: Commit**
```bash
git add backend/app/notify/factory.py backend/tests/test_notify_factory.py
git commit -m "feat(backend): notification dispatcher factory from env"
```

---

### Task 5: Câblage WS — dispatch non bloquant

**Files:**
- Modify: `backend/app/api/app.py`
- Test: `backend/tests/test_notify_ws.py`

**Interfaces:**
- Consumes: `build_dispatcher` (T4), `NotificationDispatcher` (T1).
- Produces: `app.state.notifier` (défaut `None`, ouvert au `lifespan`, injectable) ; le handler `/ws/stream` dispatch chaque event.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_notify_ws.py`
```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import BBox, Detection
from app.notify.base import NotificationDispatcher
from app.persistence.journal import Journal


class _StubDetector:
    def __init__(self, dets):
        self._dets = dets

    def detect(self, frame):
        return self._dets

    def reset(self):
        pass


class _Spy:
    def __init__(self):
        self.events = []

    def notify(self, event):
        self.events.append(event)


def test_ws_dispatche_une_notification_sur_infraction():
    spy = _Spy()
    app = create_app()
    app.state.detector = _StubDetector(
        [Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)])
    app.state.decode = lambda b64: b64
    app.state.journal = Journal(":memory:")
    app.state.notifier = NotificationDispatcher([spy])
    client = TestClient(app)
    client.put("/zones", json={"zones": [{"name": "z",
               "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
               "required_ppe": ["helmet"]}]})
    with client.websocket_connect("/ws/stream") as ws:
        ws.send_json({"frame": "F", "timestamp": 0.0}); ws.receive_json()
        ws.send_json({"frame": "F", "timestamp": 3.5}); ws.receive_json()  # >= confirm (3s)
    assert len(spy.events) == 1
    assert spy.events[0].zone == "z"
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_notify_ws.py -q` → FAIL (aucun dispatch).

- [ ] **Step 3: Écrire l'implémentation** — éditer `backend/app/api/app.py`

(a) Dans `lifespan`, après le bloc `snapshots`, ajouter :
```python
        if app.state.notifier is None:
            from app.notify.factory import build_dispatcher

            app.state.notifier = build_dispatcher()
```

(b) Après `app.state.snapshots = None`, ajouter l'init d'état :
```python
    app.state.notifier = None            # remplacé par un dispatcher espion dans les tests
```

(c) Dans le handler `/ws/stream`, après le `try/except` de persistance et **avant**
`await ws.send_json(frame_response(detections, result))`, ajouter :
```python
                for event in result.events:
                    try:
                        await run_in_threadpool(app.state.notifier.notify, event)
                    except Exception:
                        pass  # une panne de notification ne doit pas tuer le flux
```

- [ ] **Step 4: Lancer les tests** — `cd backend && py -3 -m pytest tests/test_notify_ws.py tests/test_api.py tests/test_persistence_ws.py -q`
Expected: PASS (le dispatch + les tests WS existants restent verts : sans notifier injecté, le `lifespan` construit un dispatcher **vide** — env de test sans SMTP/webhook — donc `notify` est un no-op).

- [ ] **Step 5: Commit**
```bash
git add backend/app/api/app.py backend/tests/test_notify_ws.py
git commit -m "feat(backend): dispatch notifications on confirmed WS violation"
```

---

### Task 6: Journal de décisions (notifications)

**Files:**
- Modify: `docs/DECISIONS.md`

**Interfaces:** aucune (documentation).

- [ ] **Step 1: Ajouter l'entrée** en haut de la liste (après l'intro, avant l'entrée `## 2026-08-01 — P3-b …`) :
```markdown
## 2026-08-04 — P3-c : notifier sur chaque infraction confirmée (pas de routage par sévérité serveur)
**Contexte.** La sévérité vit côté front (`localStorage`), jamais côté serveur (décision P3-a).
Router les notifications « par sévérité » exigerait de la réintroduire côté serveur.
**Décision.** On notifie (email + Teams, fan-out webhook-first) sur chaque `ViolationEvent`
confirmé ; le **debounce (3 s) + cooldown (30 s/personne)** du moteur est le filtre anti-flood
(esprit **ISA-18.2**). Envoi non bloquant (`run_in_threadpool`), no-op si non configuré.
**Conséquence.** Aucune duplication du modèle de risque côté serveur. Escalade/astreinte,
acquittement, SMS et passerelle MQTT/OPC-UA→PLC restent en V2.
```

- [ ] **Step 2: Commit**
```bash
git add docs/DECISIONS.md
git commit -m "docs: decision log (P3-c notify on confirmed violation)"
```

---

## Self-Review

**1. Couverture spec (P3-c) :** `Notifier`/`NotificationDispatcher`/`format_lines` ✅ (T1) ; `EmailNotifier` SMTP ✅ (T2) ; `TeamsNotifier` webhook ✅ (T3) ; fabrique env + no-op ✅ (T4) ; câblage WS non bloquant + injection ✅ (T5) ; décision documentée ✅ (T6). Zéro dépendance (`smtplib`/`urllib`) ✅. Sûr sans config (dispatcher vide) ✅.

**2. Placeholders :** aucun — code complet (formatage, SMTP, webhook, fabrique, endpoint WS, tests). L'édition de `app.py` (T5) est ancrée sur le handler P3-b existant (lifespan + bloc persistance).

**3. Cohérence des types :** `ViolationEvent` (domaine) → `format_lines` (T1) → `EmailNotifier`/`TeamsNotifier` (T2, T3) → `NotificationDispatcher` (T1) → `build_dispatcher` (T4) → `app.state.notifier` + dispatch WS (T5). Transports `send`/`poster` injectables, cohérents entre impl. et tests. `app.state.notifier` injecté comme `journal`/`snapshots`. `__len__` sur le dispatcher sert le test de la fabrique (T4).
```
