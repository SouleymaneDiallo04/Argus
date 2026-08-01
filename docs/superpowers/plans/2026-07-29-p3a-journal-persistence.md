# P3-a — Persistance & journal d'événements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persister les infractions (journal HSE) et des agrégats de conformité en SQLite, et les exposer via `GET /events` et `GET /stats`.

**Architecture:** Un repository pur `Journal` (SQLite, testable en `:memory:`) branché en deux points de `app/api/app.py` : le handler WebSocket **écrit** (non bloquant, via `run_in_threadpool`), deux endpoints REST **lisent**. Aucune logique métier nouvelle : on persiste ce que le pipeline produit déjà.

**Tech Stack:** Python 3.13, FastAPI, `sqlite3` (stdlib — zéro nouvelle dépendance), pytest + Starlette `TestClient`.

## Global Constraints

- **Zéro nouvelle dépendance** — `sqlite3` de la stdlib uniquement.
- **`Journal` injectable en test** exactement comme `app.state.detector` : défaut prod `ARGUS_DB_PATH` (`argus.db`), tests passent `Journal(":memory:")`.
- **Écriture WS non bloquante** : `await run_in_threadpool(app.state.journal.record_frame, result, now)`.
- **Horloge murale serveur UTC** (`datetime.now(timezone.utc)`) comme axe temps ; `stream_ts` conservé pour recouper la vidéo.
- **Pas de sévérité stockée** (dépend du risque de zone, côté front). Backend factuel : zone + EPI manquants.
- **Taux** = `compliant_frames / person_frames`, ou **`null`** si `person_frames == 0` (jamais de division par zéro).
- Observations : agrégats par **fenêtre minute × zone** ; personnes hors zone agrégées sous `zone=""` et **exclues** de `global`/`by_zone`.
- Suite backend existante (**67 tests**) doit rester verte.
- Commits : préfixe conventionnel, anglais, **sans `Co-Authored-By`**.
- Rappel taxonomie EPI : `{helmet, safety-vest, mask, shoes}`.

---

### Task 1: Journal — schéma + journal d'événements (écriture/lecture)

**Files:**
- Create: `backend/app/persistence/__init__.py` (vide), `backend/app/persistence/journal.py`
- Test: `backend/tests/test_journal.py`

**Interfaces:**
- Consumes: `ViolationEvent` (`app.domain.types`).
- Produces: `Journal(db_path=":memory:")` ; `Journal.record_event(event: ViolationEvent, ts: datetime) -> None` ; `Journal.events(*, zone=None, ppe=None, since=None, until=None, camera=None, limit=100, offset=0) -> list[dict]` (plus récent d'abord, dict = `{id, ts, stream_ts, camera, zone, track_id, missing}`).

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_journal.py`

```python
from __future__ import annotations

from datetime import datetime, timezone

from app.domain.types import ViolationEvent
from app.persistence.journal import Journal


def _ev(track_id, zone, missing, stream_ts=0.0, camera="cam-1"):
    return ViolationEvent(track_id=track_id, zone=zone, missing=frozenset(missing),
                          timestamp=stream_ts, camera=camera)


def _ts(minute):
    return datetime(2026, 7, 29, 14, minute, tzinfo=timezone.utc)


def test_record_and_query_events_newest_first():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Fonderie", ["helmet"]), _ts(30))
    j.record_event(_ev(2, "Bureau", ["mask"]), _ts(31))
    rows = j.events()
    assert [r["track_id"] for r in rows] == [2, 1]          # ts DESC
    assert rows[1]["zone"] == "Fonderie"
    assert rows[1]["missing"] == ["helmet"]                 # JSON -> liste triée


def test_events_filter_by_zone_ppe_and_time():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Fonderie", ["helmet", "shoes"]), _ts(30))
    j.record_event(_ev(2, "Bureau", ["mask"]), _ts(31))
    assert [r["track_id"] for r in j.events(zone="Fonderie")] == [1]
    assert [r["track_id"] for r in j.events(ppe="shoes")] == [1]
    assert [r["track_id"] for r in j.events(since="2026-07-29T14:31")] == [2]


def test_events_limit_and_offset():
    j = Journal(":memory:")
    for i in range(5):
        j.record_event(_ev(i, "Z", ["helmet"]), _ts(30 + i))
    assert len(j.events(limit=2)) == 2
    assert [r["track_id"] for r in j.events(limit=2, offset=2)] == [2, 1]
```

- [ ] **Step 2: Lancer le test** — `cd backend && python -m pytest tests/test_journal.py -q`
Expected: FAIL (`ModuleNotFoundError: app.persistence.journal`).

- [ ] **Step 3: Écrire l'implémentation**

`backend/app/persistence/__init__.py` : fichier vide.

`backend/app/persistence/journal.py` :
```python
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime

from app.domain.types import FrameResult, ViolationEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    stream_ts REAL NOT NULL,
    camera TEXT NOT NULL,
    zone TEXT,
    track_id INTEGER NOT NULL,
    missing TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_zone ON events(zone);
CREATE TABLE IF NOT EXISTS observations (
    bucket TEXT NOT NULL,
    zone TEXT NOT NULL,
    person_frames INTEGER NOT NULL DEFAULT 0,
    compliant_frames INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket, zone)
);
"""


class Journal:
    """Repository SQLite du journal d'infractions + agrégats de conformité."""

    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # --- écriture ---
    def record_event(self, event: ViolationEvent, ts: datetime) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (ts, stream_ts, camera, zone, track_id, missing) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts.isoformat(), event.timestamp, event.camera, event.zone,
                 event.track_id, json.dumps(sorted(event.missing))),
            )
            self._conn.commit()

    # --- lecture ---
    def events(self, *, zone=None, ppe=None, since=None, until=None, camera=None,
               limit=100, offset=0) -> list[dict]:
        clauses, params = [], []
        if zone is not None:
            clauses.append("zone = ?"); params.append(zone)
        if ppe is not None:
            clauses.append("missing LIKE ?"); params.append(f'%"{ppe}"%')
        if since is not None:
            clauses.append("ts >= ?"); params.append(since)
        if until is not None:
            clauses.append("ts <= ?"); params.append(until)
        if camera is not None:
            clauses.append("camera = ?"); params.append(camera)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        limit = max(1, min(int(limit), 1000))
        rows = self._conn.execute(
            f"SELECT id, ts, stream_ts, camera, zone, track_id, missing FROM events"
            f"{where} ORDER BY ts DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, int(offset)),
        ).fetchall()
        return [
            {"id": r["id"], "ts": r["ts"], "stream_ts": r["stream_ts"],
             "camera": r["camera"], "zone": r["zone"], "track_id": r["track_id"],
             "missing": json.loads(r["missing"])}
            for r in rows
        ]
```

- [ ] **Step 4: Lancer le test** — `cd backend && python -m pytest tests/test_journal.py -q`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/persistence/__init__.py backend/app/persistence/journal.py backend/tests/test_journal.py
git commit -m "feat(backend): Journal repository — events schema + filtered queries"
```

---

### Task 2: Observations & statistiques de conformité

**Files:**
- Modify: `backend/app/persistence/journal.py`
- Test: `backend/tests/test_journal.py` (ajouts)

**Interfaces:**
- Produces: `Journal.record_observations(bucket: str, zone: str, person_frames: int, compliant_frames: int) -> None` (upsert additif sur `(bucket, zone)`) ; `Journal.stats(*, since=None, until=None, zone=None) -> dict` (`{global, by_zone, over_time, violations}`).

- [ ] **Step 1: Écrire le test qui échoue** — ajouter à `backend/tests/test_journal.py`

```python
def test_record_observations_upsert_is_additive():
    j = Journal(":memory:")
    j.record_observations("2026-07-29T14:30", "Fonderie", 4, 3)
    j.record_observations("2026-07-29T14:30", "Fonderie", 6, 2)   # même clé -> somme
    g = j.stats()["global"]
    assert g == {"person_frames": 10, "compliant_frames": 5, "rate": 0.5}


def test_stats_global_by_zone_over_time_excludes_no_zone():
    j = Journal(":memory:")
    j.record_observations("2026-07-29T14:30", "Fonderie", 10, 7)
    j.record_observations("2026-07-29T14:31", "Fonderie", 5, 5)
    j.record_observations("2026-07-29T14:30", "", 3, 3)           # hors zone -> exclu
    s = j.stats()
    assert s["global"] == {"person_frames": 15, "compliant_frames": 12, "rate": 12 / 15}
    by_zone = {z["zone"]: z for z in s["by_zone"]}
    assert set(by_zone) == {"Fonderie"}                           # "" exclu
    assert by_zone["Fonderie"]["rate"] == 12 / 15
    assert [o["bucket"] for o in s["over_time"]] == ["2026-07-29T14:30", "2026-07-29T14:31"]


def test_stats_rate_null_when_no_observation():
    assert Journal(":memory:").stats()["global"]["rate"] is None


def test_stats_violations_count_from_events():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Fonderie", ["helmet"]), _ts(30))
    j.record_event(_ev(2, "Fonderie", ["mask"]), _ts(31))
    v = j.stats()["violations"]
    assert v["total"] == 2
    assert v["by_zone"]["Fonderie"] == 2
```

- [ ] **Step 2: Lancer le test** — `cd backend && python -m pytest tests/test_journal.py -q`
Expected: FAIL (`AttributeError: 'Journal' object has no attribute 'record_observations'`).

- [ ] **Step 3: Écrire l'implémentation** — ajouter à `backend/app/persistence/journal.py`

Ajouter la fonction utilitaire au niveau module (après `_SCHEMA`) :
```python
def _rate_row(pf: int, cf: int) -> dict:
    return {"person_frames": pf, "compliant_frames": cf,
            "rate": (cf / pf) if pf else None}
```

Ajouter ces méthodes à la classe `Journal` (après `record_event`) :
```python
    def record_observations(self, bucket: str, zone: str,
                            person_frames: int, compliant_frames: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO observations (bucket, zone, person_frames, compliant_frames) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(bucket, zone) DO UPDATE SET "
                "  person_frames = person_frames + excluded.person_frames, "
                "  compliant_frames = compliant_frames + excluded.compliant_frames",
                (bucket, zone, person_frames, compliant_frames),
            )
            self._conn.commit()

    def stats(self, *, since=None, until=None, zone=None) -> dict:
        obs_clauses, obs_params = [], []
        if zone is not None:
            obs_clauses.append("zone = ?"); obs_params.append(zone)
        else:
            obs_clauses.append("zone <> ''")                      # exclut hors-zone
        if since is not None:
            obs_clauses.append("bucket >= ?"); obs_params.append(since[:16])
        if until is not None:
            obs_clauses.append("bucket <= ?"); obs_params.append(until[:16])
        obs_where = " WHERE " + " AND ".join(obs_clauses)

        g = self._conn.execute(
            f"SELECT COALESCE(SUM(person_frames), 0) pf, "
            f"COALESCE(SUM(compliant_frames), 0) cf FROM observations{obs_where}",
            obs_params,
        ).fetchone()
        global_stat = _rate_row(g["pf"], g["cf"])

        by_zone = [
            {"zone": r["zone"], **_rate_row(r["pf"], r["cf"])}
            for r in self._conn.execute(
                f"SELECT zone, SUM(person_frames) pf, SUM(compliant_frames) cf "
                f"FROM observations{obs_where} GROUP BY zone ORDER BY zone", obs_params,
            ).fetchall()
        ]
        over_time = [
            {"bucket": r["bucket"], **_rate_row(r["pf"], r["cf"])}
            for r in self._conn.execute(
                f"SELECT bucket, SUM(person_frames) pf, SUM(compliant_frames) cf "
                f"FROM observations{obs_where} GROUP BY bucket ORDER BY bucket", obs_params,
            ).fetchall()
        ]

        ev_clauses, ev_params = [], []
        if zone is not None:
            ev_clauses.append("zone = ?"); ev_params.append(zone)
        if since is not None:
            ev_clauses.append("ts >= ?"); ev_params.append(since)
        if until is not None:
            ev_clauses.append("ts <= ?"); ev_params.append(until)
        ev_where = (" WHERE " + " AND ".join(ev_clauses)) if ev_clauses else ""
        total = self._conn.execute(
            f"SELECT COUNT(*) n FROM events{ev_where}", ev_params).fetchone()["n"]
        by_zone_v = {
            r["zone"]: r["n"]
            for r in self._conn.execute(
                f"SELECT zone, COUNT(*) n FROM events{ev_where} GROUP BY zone", ev_params,
            ).fetchall()
        }
        return {"global": global_stat, "by_zone": by_zone,
                "over_time": over_time,
                "violations": {"total": total, "by_zone": by_zone_v}}
```

- [ ] **Step 4: Lancer le test** — `cd backend && python -m pytest tests/test_journal.py -q`
Expected: PASS (7).

- [ ] **Step 5: Commit**

```bash
git add backend/app/persistence/journal.py backend/tests/test_journal.py
git commit -m "feat(backend): conformity observations upsert + stats aggregation"
```

---

### Task 3: `record_frame` — persistance d'un FrameResult

**Files:**
- Modify: `backend/app/persistence/journal.py`
- Test: `backend/tests/test_journal.py` (ajouts)

**Interfaces:**
- Consumes: `FrameResult`, `ComplianceResult` (via `result.results`), `ViolationEvent` (via `result.events`).
- Produces: `Journal.record_frame(result: FrameResult, now: datetime) -> None` — insère chaque event (avec `now` comme `ts`), puis upsert les observations groupées par zone (`bucket = now` tronqué à la minute ; personnes hors zone sous `zone=""`).

- [ ] **Step 1: Écrire le test qui échoue** — ajouter à `backend/tests/test_journal.py`

```python
from app.domain.types import ComplianceResult, FrameResult


def _cr(track_id, zone, compliant, missing=()):
    return ComplianceResult(track_id=track_id, zone=zone, required=frozenset(),
                            present=frozenset(), missing=frozenset(missing),
                            compliant=compliant)


def test_record_frame_persists_events_and_observations():
    j = Journal(":memory:")
    result = FrameResult(
        results=[_cr(1, "Fonderie", False, ["helmet"]),
                 _cr(2, "Fonderie", True),
                 _cr(3, None, True)],                 # hors zone
        events=[_ev(1, "Fonderie", ["helmet"])],
    )
    j.record_frame(result, _ts(30))
    assert len(j.events()) == 1                        # l'event est journalisé
    fonderie = {z["zone"]: z for z in j.stats()["by_zone"]}["Fonderie"]
    assert fonderie["person_frames"] == 2              # persons 1 & 2 (zone nommée)
    assert fonderie["compliant_frames"] == 1           # seul le 2 est conforme
    # la personne hors zone est agrégée sous "" (exclue du global/by_zone)
    assert j.stats()["global"]["person_frames"] == 2
```

- [ ] **Step 2: Lancer le test** — `cd backend && python -m pytest tests/test_journal.py -q`
Expected: FAIL (`AttributeError: ... 'record_frame'`).

- [ ] **Step 3: Écrire l'implémentation** — ajouter la méthode à la classe `Journal` (après `record_observations`)

```python
    def record_frame(self, result: FrameResult, now: datetime) -> None:
        for event in result.events:
            self.record_event(event, now)
        bucket = now.strftime("%Y-%m-%dT%H:%M")
        counts: dict[str, list[int]] = {}
        for r in result.results:
            c = counts.setdefault(r.zone or "", [0, 0])
            c[0] += 1
            if r.compliant:
                c[1] += 1
        for zone, (pf, cf) in counts.items():
            self.record_observations(bucket, zone, pf, cf)
```

- [ ] **Step 4: Lancer le test** — `cd backend && python -m pytest tests/test_journal.py -q`
Expected: PASS (8).

- [ ] **Step 5: Commit**

```bash
git add backend/app/persistence/journal.py backend/tests/test_journal.py
git commit -m "feat(backend): Journal.record_frame persists a FrameResult"
```

---

### Task 4: Câblage WS — persistance non bloquante + isolation des tests

**Files:**
- Modify: `backend/app/api/app.py`
- Create: `backend/tests/conftest.py`, `backend/.gitignore`
- Test: `backend/tests/test_persistence_ws.py`

**Interfaces:**
- Consumes: `Journal` (Task 1-3), `FramePipeline.process` renvoyant `(detections, FrameResult)`.
- Produces: `app.state.journal` (défaut `None`, ouvert au `lifespan` depuis `ARGUS_DB_PATH`, injectable). Le handler `/ws/stream` persiste chaque frame.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_persistence_ws.py`

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import BBox, Detection
from app.persistence.journal import Journal


class _StubDetector:
    def __init__(self, dets):
        self._dets = dets

    def detect(self, frame):
        return self._dets

    def reset(self):
        pass


def _client(journal):
    app = create_app()
    app.state.detector = _StubDetector(
        [Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=1)])
    app.state.decode = lambda b64: b64
    app.state.journal = journal
    return TestClient(app)


def test_ws_flux_persists_event_and_observations():
    journal = Journal(":memory:")
    client = _client(journal)
    client.put("/zones", json={"zones": [{"name": "z",
               "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
               "required_ppe": ["helmet"]}]})
    with client.websocket_connect("/ws/stream") as ws:
        ws.send_json({"frame": "F", "timestamp": 0.0}); ws.receive_json()
        ws.send_json({"frame": "F", "timestamp": 3.5}); ws.receive_json()  # >= confirm (3s)
    events = journal.events()
    assert len(events) == 1                       # une infraction confirmée
    assert events[0]["zone"] == "z"
    assert events[0]["missing"] == ["helmet"]
    g = journal.stats()["global"]
    assert g["person_frames"] == 2                # 2 frames, 1 personne chacune
    assert g["compliant_frames"] == 0
    assert g["rate"] == 0.0
```

- [ ] **Step 2: Lancer le test** — `cd backend && python -m pytest tests/test_persistence_ws.py -q`
Expected: FAIL (`app.state.journal` non utilisé par le handler ; aucune ligne persistée).

- [ ] **Step 3: Écrire l'implémentation**

`backend/tests/conftest.py` (empêche la création d'un vrai `argus.db` pendant les tests qui n'injectent pas de Journal — le défaut devient `:memory:`) :
```python
import pytest


@pytest.fixture(autouse=True)
def _ephemeral_db(monkeypatch):
    monkeypatch.setenv("ARGUS_DB_PATH", ":memory:")
```

`backend/.gitignore` :
```
argus.db
argus.db-wal
argus.db-shm
```

Modifier `backend/app/api/app.py` :

Ajouter aux imports (haut du fichier) :
```python
from datetime import datetime, timezone

from fastapi.concurrency import run_in_threadpool
```

Dans `lifespan`, après le bloc detector, ouvrir le Journal :
```python
        if app.state.journal is None:
            from app.persistence.journal import Journal

            app.state.journal = Journal(os.environ.get("ARGUS_DB_PATH", "argus.db"))
```

Après `app.state.detector = None`, initialiser l'état :
```python
    app.state.journal = None             # remplacé par un Journal(":memory:") dans les tests
```

Dans le handler `/ws/stream`, après le `try/except` de `pipeline.process` et **avant** `await ws.send_json(frame_response(...))`, persister (sans jamais interrompre le flux live) :
```python
                try:
                    await run_in_threadpool(
                        app.state.journal.record_frame, result, datetime.now(timezone.utc))
                except Exception:
                    pass  # une panne de persistance ne doit pas tuer le flux
                await ws.send_json(frame_response(detections, result))
```

- [ ] **Step 4: Lancer les tests** — `cd backend && python -m pytest tests/test_persistence_ws.py tests/test_api.py tests/test_cors.py -q`
Expected: PASS (le test de persistance + les tests WS/API/CORS existants restent verts, aucun `argus.db` créé).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/app.py backend/tests/conftest.py backend/tests/test_persistence_ws.py backend/.gitignore
git commit -m "feat(backend): persist each WS frame to the journal (non-blocking)"
```

---

### Task 5: Endpoint `GET /events`

**Files:**
- Modify: `backend/app/api/app.py`
- Test: `backend/tests/test_events_api.py`

**Interfaces:**
- Consumes: `Journal.events(...)`.
- Produces: `GET /events?zone&ppe&since&until&camera&limit&offset` → `{"events": [...]}`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_events_api.py`

```python
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.types import ViolationEvent
from app.persistence.journal import Journal


def _client(journal):
    app = create_app()
    app.state.detector = object()
    app.state.decode = lambda b64: b64
    app.state.journal = journal
    return TestClient(app)


def _ev(track_id, zone, missing):
    return ViolationEvent(track_id=track_id, zone=zone, missing=frozenset(missing),
                          timestamp=0.0, camera="cam-1")


def test_get_events_orders_and_filters():
    journal = Journal(":memory:")
    journal.record_event(_ev(1, "Fonderie", ["helmet"]),
                         datetime(2026, 7, 29, 14, 30, tzinfo=timezone.utc))
    journal.record_event(_ev(2, "Bureau", ["mask"]),
                         datetime(2026, 7, 29, 14, 31, tzinfo=timezone.utc))
    client = _client(journal)

    allev = client.get("/events").json()["events"]
    assert [e["track_id"] for e in allev] == [2, 1]           # plus récent d'abord

    fonderie = client.get("/events", params={"zone": "Fonderie"}).json()["events"]
    assert len(fonderie) == 1 and fonderie[0]["missing"] == ["helmet"]

    helmet = client.get("/events", params={"ppe": "helmet"}).json()["events"]
    assert [e["track_id"] for e in helmet] == [1]
```

- [ ] **Step 2: Lancer le test** — `cd backend && python -m pytest tests/test_events_api.py -q`
Expected: FAIL (404 — route absente).

- [ ] **Step 3: Écrire l'implémentation** — ajouter dans `create_app` (après `put_zones`, avant le handler websocket)

```python
    @app.get("/events")
    def get_events(
        zone: str | None = None,
        ppe: str | None = None,
        since: str | None = None,
        until: str | None = None,
        camera: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        return {"events": app.state.journal.events(
            zone=zone, ppe=ppe, since=since, until=until,
            camera=camera, limit=limit, offset=offset)}
```

- [ ] **Step 4: Lancer le test** — `cd backend && python -m pytest tests/test_events_api.py -q`
Expected: PASS (1).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/app.py backend/tests/test_events_api.py
git commit -m "feat(backend): GET /events — filtered violation journal"
```

---

### Task 6: Endpoint `GET /stats`

**Files:**
- Modify: `backend/app/api/app.py`
- Test: `backend/tests/test_stats_api.py`

**Interfaces:**
- Consumes: `Journal.stats(...)`.
- Produces: `GET /stats?since&until&zone` → `{global, by_zone, over_time, violations}`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_stats_api.py`

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.persistence.journal import Journal


def _client(journal):
    app = create_app()
    app.state.detector = object()
    app.state.decode = lambda b64: b64
    app.state.journal = journal
    return TestClient(app)


def test_get_stats_computes_rate():
    journal = Journal(":memory:")
    journal.record_observations("2026-07-29T14:30", "Fonderie", 10, 7)
    journal.record_observations("2026-07-29T14:31", "Fonderie", 5, 5)
    s = _client(journal).get("/stats").json()
    assert s["global"] == {"person_frames": 15, "compliant_frames": 12, "rate": 12 / 15}
    assert len(s["over_time"]) == 2
    assert {z["zone"]: z["rate"] for z in s["by_zone"]}["Fonderie"] == 12 / 15


def test_get_stats_rate_null_when_empty():
    s = _client(Journal(":memory:")).get("/stats").json()
    assert s["global"]["rate"] is None
```

- [ ] **Step 2: Lancer le test** — `cd backend && python -m pytest tests/test_stats_api.py -q`
Expected: FAIL (404 — route absente).

- [ ] **Step 3: Écrire l'implémentation** — ajouter dans `create_app` (après `get_events`)

```python
    @app.get("/stats")
    def get_stats(
        since: str | None = None,
        until: str | None = None,
        zone: str | None = None,
    ) -> dict:
        return app.state.journal.stats(since=since, until=until, zone=zone)
```

- [ ] **Step 4: Lancer le test** — `cd backend && python -m pytest tests/test_stats_api.py -q`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/app.py backend/tests/test_stats_api.py
git commit -m "feat(backend): GET /stats — conformity rate global/zone/time"
```

---

### Task 7: Journal de décisions (`DECISIONS.md`)

**Files:**
- Create: `docs/DECISIONS.md`

**Interfaces:** aucune (documentation).

- [ ] **Step 1: Créer `docs/DECISIONS.md`**

```markdown
# Journal des décisions — Argus

Registre des décisions d'architecture non évidentes (ADR léger). Le plus récent en haut.

## 2026-07-29 — P3-a : sémantique temps du journal = horloge murale serveur
**Contexte.** Le journal d'infractions et les agrégats de conformité ont besoin d'un axe temps.
Le client envoie un `timestamp` **relatif au flux** (repart de 0 à chaque connexion).
**Décision.** L'axe principal est l'**horloge murale serveur (UTC)** : c'est ce qu'un
déploiement réel (caméras live/RTSP) consigne, et c'est stable entre sessions. Le
`stream_ts` du flux est conservé en colonne pour recouper la timeline vidéo.
**Conséquence.** Sur une vidéo uploadée de démo, toutes les infractions tombent dans
« maintenant » — acceptable : le système consigne *quand il observe*.

## 2026-07-29 — P3-a : la sévérité n'est pas persistée
**Contexte.** La sévérité d'une alerte dépend du **risque de zone**, choisi côté front
et stocké en `localStorage` (P2-a), jamais envoyé au backend.
**Décision.** Le backend reste **factuel** : il persiste zone + EPI manquants. La sévérité
est recalculée à l'affichage (`severityFor`).
**Conséquence.** Séparation front/back nette ; le journal ne dépend pas d'un réglage front.

## 2026-07-15 — V1 : exclusion de `gloves` / `glasses`
Objets minuscules et déformables (pire précision de la littérature) + données publiques
rares : le coût d'un modèle honnête dépasse la valeur démonstrative. Réintroduction en V2
via active-learning ciblé. (cf. `argus-design.md` §3.)
```

- [ ] **Step 2: Commit**

```bash
git add docs/DECISIONS.md
git commit -m "docs: decision log (P3-a time semantics + no stored severity)"
```

---

## Self-Review

**1. Couverture spec (P3-a) :** table `events` + `observations` ✅ (T1, T2) ; `record_frame` depuis un `FrameResult` ✅ (T3) ; persistance WS non bloquante + injection ✅ (T4) ; `GET /events` filtrable ✅ (T5) ; `GET /stats` taux global/zone/temps + `null` ✅ (T6) ; `DECISIONS.md` (horloge murale + pas de sévérité) ✅ (T7). Zéro nouvelle dépendance ✅ (sqlite3 stdlib). Suite existante préservée : vérifiée en T4 (test_api/test_cors) et globalement à la clôture.

**2. Placeholders :** aucun — chaque étape contient le code complet (schéma, requêtes SQL, endpoints, tests). Les modifications de `app.py` (T4-T6) sont décrites par éditions ciblées (imports, bloc lifespan, init state, endpoints) plutôt que par réécriture, pour éviter la divergence avec le fichier existant.

**3. Cohérence des types :** `Journal(db_path)` (T1) → `record_event`/`events` (T1), `record_observations`/`stats` (T2), `record_frame` (T3) ; consommé par `app.state.journal` dans `app.py` (T4) et les endpoints (T5, T6). `ViolationEvent`/`FrameResult`/`ComplianceResult` réutilisés tels quels (aucun changement de domaine). Les clés de dict renvoyées par `events()` et `stats()` sont identiques entre repository et endpoints (les endpoints passent le dict tel quel). `_rate_row` produit partout `{person_frames, compliant_frames, rate}`.
```
