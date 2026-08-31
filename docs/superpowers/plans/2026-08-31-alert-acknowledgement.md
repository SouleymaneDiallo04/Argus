# V1.5 — Acquittement des alertes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner aux infractions un statut `active → ack → resolved` persisté et pilotable depuis le dashboard.

**Architecture:** Colonne `status` sur `events` + `set_status` + endpoint `POST /events/{id}/status` ; côté front, badge + actions dans le journal et filtre statut.

**Tech Stack:** Python 3.13, FastAPI, SQLite (stdlib) ; Next.js 16, Vitest. Zéro nouvelle dépendance.

## Global Constraints

- `status ∈ {active, ack, resolved}` ; défaut `active` ; transitions libres.
- Migration défensive `ALTER TABLE events ADD COLUMN status TEXT NOT NULL DEFAULT 'active'`.
- **Ack anonyme** (pas de `acked_by` — auth V2). Réutiliser `StatusBadge` + type `AlertStatus`.
- Interpréteur test backend : **`py -3`** ; front : `npm run test` / `npm run build`.
- Suites existantes vertes (backend **108**, frontend **45**). Commits conventionnels, anglais,
  **sans `Co-Authored-By`**. Branche : `feat/alert-ack`.

---

### Task 1: Journal — colonne `status` + `set_status` + filtre

**Files:**
- Modify: `backend/app/persistence/journal.py`
- Test: `backend/tests/test_journal.py` (ajouts)

**Interfaces:**
- Produces: `record_event` (status défaut `active`) ; `set_status(id, status) -> bool` ;
  `events(..., status=None)` et `event()` incluent `status`.

- [ ] **Step 1: Écrire le test qui échoue** — ajouter à `backend/tests/test_journal.py`
```python
def test_event_status_defaults_active_and_set_status():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Z", ["helmet"]), _ts(30))
    row_id = j.events()[0]["id"]
    assert j.events()[0]["status"] == "active"
    assert j.set_status(row_id, "ack") is True
    assert j.event(row_id)["status"] == "ack"
    assert j.set_status(9999, "resolved") is False


def test_events_filter_by_status():
    j = Journal(":memory:")
    j.record_event(_ev(1, "Z", ["helmet"]), _ts(30))
    j.record_event(_ev(2, "Z", ["mask"]), _ts(31))
    second = j.events()[0]["id"]
    j.set_status(second, "resolved")
    assert [e["status"] for e in j.events(status="active")] == ["active"]
    assert [e["status"] for e in j.events(status="resolved")] == ["resolved"]
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_journal.py -q` → FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `backend/app/persistence/journal.py`

(a) Colonne dans `_SCHEMA` (table `events`) — remplacer :
```python
    missing TEXT NOT NULL,
    snapshot TEXT
);
```
par :
```python
    missing TEXT NOT NULL,
    snapshot TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);
```

(b) Migration défensive dans `__init__` — après le `try/except` du `snapshot`, ajouter :
```python
        try:
            self._conn.execute(
                "ALTER TABLE events ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        except sqlite3.OperationalError:
            pass  # colonne déjà présente (DB créée avant V1.5)
```
*(placer ces lignes juste avant `self._conn.commit()`.)*

(c) `set_status` — ajouter la méthode après `record_event` :
```python
    def set_status(self, event_id: int, status: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE events SET status = ? WHERE id = ?", (status, event_id))
            self._conn.commit()
            return cur.rowcount > 0
```

(d) `events()` — signature + SELECT + filtre + dict. Ajouter le paramètre `status=None` à la
signature, la clause, la colonne et la clé :
- signature : `def events(self, *, zone=None, ppe=None, since=None, until=None, camera=None, status=None, limit=100, offset=0)`
- après le bloc `if camera is not None: ...`, ajouter :
```python
        if status is not None:
            clauses.append("status = ?"); params.append(status)
```
- SELECT : ajouter `, status` à la liste des colonnes (`... missing, snapshot, status FROM events`) ;
- dict : ajouter `"status": r["status"]`.

(e) `event()` — SELECT : ajouter `, status` ; dict : ajouter `"status": r["status"]`.

- [ ] **Step 4: Lancer le test** — `cd backend && py -3 -m pytest tests/test_journal.py -q` → PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/persistence/journal.py backend/tests/test_journal.py
git commit -m "feat(backend): event status column + set_status + status filter"
```

---

### Task 2: Endpoint `POST /events/{id}/status` + `GET /events?status`

**Files:**
- Modify: `backend/app/api/app.py`, `backend/app/api/schemas.py`
- Test: `backend/tests/test_status_api.py`

**Interfaces:**
- Consumes: `Journal.set_status`/`event`/`events` (T1).
- Produces: `POST /events/{id}/status` (200/422/404) ; `GET /events?status`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_status_api.py`
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
    app.state.decode = lambda b: b
    app.state.journal = journal
    return TestClient(app)


def _ev(track_id, zone, missing):
    return ViolationEvent(track_id=track_id, zone=zone, missing=frozenset(missing),
                          timestamp=0.0, camera="cam-1")


def test_set_status_ok_invalid_and_missing():
    journal = Journal(":memory:")
    journal.record_event(_ev(1, "Z", ["helmet"]),
                         datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc))
    client = _client(journal)
    eid = client.get("/events").json()["events"][0]["id"]

    ok = client.post(f"/events/{eid}/status", json={"status": "ack"})
    assert ok.status_code == 200 and ok.json()["status"] == "ack"

    assert client.post(f"/events/{eid}/status", json={"status": "bogus"}).status_code == 422
    assert client.post("/events/9999/status", json={"status": "ack"}).status_code == 404


def test_get_events_filter_by_status():
    journal = Journal(":memory:")
    journal.record_event(_ev(1, "Z", ["helmet"]),
                         datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc))
    client = _client(journal)
    assert len(client.get("/events", params={"status": "active"}).json()["events"]) == 1
    assert client.get("/events", params={"status": "resolved"}).json()["events"] == []
```

- [ ] **Step 2: Lancer le test** — `cd backend && py -3 -m pytest tests/test_status_api.py -q` → FAIL.

- [ ] **Step 3: Écrire l'implémentation**

(a) `backend/app/api/schemas.py` — ajouter :
```python
class StatusUpdate(BaseModel):
    status: str
```

(b) `backend/app/api/app.py` :
- import : ajouter `StatusUpdate` à l'import existant `from app.api.schemas import ...`.
- `get_events` : ajouter le paramètre `status: str | None = None` (dans la signature) et le
  passer à `app.state.journal.events(..., status=status, ...)`.
- Ajouter l'endpoint après `get_event_snapshot` (avant les endpoints `/reports/*` ou juste après,
  peu importe, mais avant le websocket) :
```python
    @app.post("/events/{event_id}/status")
    def set_event_status(event_id: int, body: StatusUpdate) -> dict:
        if body.status not in {"active", "ack", "resolved"}:
            raise HTTPException(status_code=422, detail="statut invalide")
        if not app.state.journal.set_status(event_id, body.status):
            raise HTTPException(status_code=404, detail="event introuvable")
        return app.state.journal.event(event_id)
```

- [ ] **Step 4: Lancer le test** — `cd backend && py -3 -m pytest tests/test_status_api.py -q` → PASS (2).

- [ ] **Step 5: Commit**
```bash
git add backend/app/api/app.py backend/app/api/schemas.py backend/tests/test_status_api.py
git commit -m "feat(backend): POST /events/{id}/status + GET /events?status"
```

---

### Task 3: Frontend — `eventsApi` (status + `setEventStatus`)

**Files:**
- Modify: `frontend/lib/eventsApi.ts`
- Test: `frontend/lib/eventsApi.test.ts` (ajout)

**Interfaces:**
- Produces: `ApiEvent.status` ; `getEvents({..., status})` ; `setEventStatus(id, status, fetchFn?)`.

- [ ] **Step 1: Écrire le test qui échoue** — ajouter à `frontend/lib/eventsApi.test.ts`
```ts
import { setEventStatus } from "./eventsApi";

test("setEventStatus poste le statut", async () => {
  let url = "";
  let init: RequestInit | undefined;
  const fetchFn = (async (u: string, i?: RequestInit) => {
    url = u; init = i;
    return { ok: true, status: 200, json: async () => ({}) } as Response;
  }) as typeof fetch;
  await setEventStatus(1, "ack", fetchFn);
  expect(url).toContain("/events/1/status");
  expect(init?.method).toBe("POST");
  expect(JSON.parse(init?.body as string)).toEqual({ status: "ack" });
});
```

- [ ] **Step 2: Lancer le test** — `cd frontend && npx vitest run lib/eventsApi.test.ts` → FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `frontend/lib/eventsApi.ts`
```ts
import { API, qs } from "./http";
import type { AlertStatus } from "@/components/ui/StatusBadge";

export type ApiEvent = {
  id: number; ts: string; stream_ts: number; camera: string;
  zone: string | null; track_id: number; missing: string[]; snapshot: string | null;
  status: AlertStatus;
};

export async function getEvents(
  params: { zone?: string; ppe?: string; since?: string; until?: string;
            status?: string; limit?: number } = {},
  fetchFn: typeof fetch = fetch,
): Promise<ApiEvent[]> {
  const res = await fetchFn(`${API}/events${qs(params)}`);
  if (!res.ok) throw new Error(`GET /events -> ${res.status}`);
  const data = (await res.json()) as { events: ApiEvent[] };
  return data.events ?? [];
}

export async function setEventStatus(
  id: number, status: AlertStatus, fetchFn: typeof fetch = fetch,
): Promise<void> {
  const res = await fetchFn(`${API}/events/${id}/status`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error(`POST /events/${id}/status -> ${res.status}`);
}

export function snapshotUrl(id: number): string {
  return `${API}/events/${id}/snapshot`;
}
```

- [ ] **Step 4: Lancer le test** — PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/lib/eventsApi.ts frontend/lib/eventsApi.test.ts
git commit -m "feat(frontend): eventsApi status field + setEventStatus"
```

---

### Task 4: Frontend — journal (badge + actions) + filtre statut + câblage

**Files:**
- Modify: `frontend/components/dashboard/JournalTable.tsx`, `DashboardFilters.tsx`, `Dashboard.tsx`
- Test: `JournalTable.test.tsx`, `DashboardFilters.test.tsx`, `Dashboard.test.tsx` (ajouts/adapt.)

**Interfaces:**
- Consumes: `setEventStatus` (T3), `StatusBadge`, `AlertStatus`.
- Produces: `JournalTable({events, onSetStatus?})` ; `DashFilters.status` ; `Dashboard` câble tout.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `frontend/components/dashboard/JournalTable.test.tsx` (et ajouter `status: "active"` au
fixture `ev`) :
```tsx
import { fireEvent } from "@testing-library/react";

test("JournalTable montre le statut et remonte les actions", () => {
  const calls: [number, string][] = [];
  render(<JournalTable events={[ev({ status: "active" })]}
                       onSetStatus={(id, s) => calls.push([id, s])} />);
  expect(screen.getByText("Active")).toBeInTheDocument();       // StatusBadge
  fireEvent.click(screen.getByText("Acquitter"));
  fireEvent.click(screen.getByText("Résoudre"));
  expect(calls).toEqual([[1, "ack"], [1, "resolved"]]);
});
```
*(Mettre à jour le fixture existant `ev` pour inclure `status: "active"` par défaut.)*

Ajouter à `frontend/components/dashboard/DashboardFilters.test.tsx` :
```tsx
test("DashboardFilters remonte le statut", () => {
  let last: DashFilters = { zone: "", ppe: "", range: "day", status: "" };
  render(<DashboardFilters filters={last} onChange={(f) => (last = f)} />);
  fireEvent.change(screen.getByLabelText(/statut/i), { target: { value: "ack" } });
  expect(last.status).toBe("ack");
});
```
*(Adapter le fixture `last` du test existant pour inclure `status: ""`.)*

- [ ] **Step 2: Lancer les tests** — FAIL.

- [ ] **Step 3: Écrire l'implémentation**

(a) `JournalTable.tsx` — importer `StatusBadge` + type, ajouter la colonne « Statut » avec badge
et boutons :
```tsx
import { StatusBadge, type AlertStatus } from "@/components/ui/StatusBadge";
```
- en-têtes : ajouter `"Statut"` à la liste.
- signature : `export function JournalTable({ events, onSetStatus }: { events: ApiEvent[]; onSetStatus?: (id: number, status: AlertStatus) => void })`.
- nouvelle cellule en fin de ligne :
```tsx
            <td className="px-2 py-1.5">
              <div className="flex items-center gap-1.5">
                <StatusBadge status={e.status} />
                {onSetStatus && e.status === "active" && (
                  <button onClick={() => onSetStatus(e.id, "ack")}
                          className="rounded border border-line2 px-2 py-0.5 text-[11px] font-bold text-ink2 hover:bg-s2">
                    Acquitter
                  </button>
                )}
                {onSetStatus && e.status !== "resolved" && (
                  <button onClick={() => onSetStatus(e.id, "resolved")}
                          className="rounded border border-line2 px-2 py-0.5 text-[11px] font-bold text-ink2 hover:bg-s2">
                    Résoudre
                  </button>
                )}
              </div>
            </td>
```

(b) `DashboardFilters.tsx` — `DashFilters` gagne `status`, ajouter un select :
```tsx
export type DashFilters = { zone: string; ppe: string; range: "hour" | "day" | "all";
                            status: "" | "active" | "ack" | "resolved" };
```
Ajouter les options + le select (après le select « Période ») :
```tsx
const STATUS: { v: DashFilters["status"]; l: string }[] = [
  { v: "", l: "Tous statuts" },
  { v: "active", l: "Actives" },
  { v: "ack", l: "Acquittées" },
  { v: "resolved", l: "Résolues" },
];
```
```tsx
      <select aria-label="Statut" className={sel} value={filters.status}
              onChange={(e) => set({ status: e.target.value as DashFilters["status"] })}>
        {STATUS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
      </select>
```

(c) `Dashboard.tsx` :
- import : `import { getEvents, setEventStatus, type ApiEvent } from "@/lib/eventsApi";`
- `filters` initial : `{ zone: "", ppe: "", range: "day", status: "" }`.
- dans `refresh`, passer le statut : `loadEvents({ zone, since, ppe: f.ppe || undefined, status: f.status || undefined, limit: 100 })`.
- ajouter la callback d'action et la passer au journal :
```tsx
  const onSetStatus = useCallback(async (id: number, status: "active" | "ack" | "resolved") => {
    try { await setEventStatus(id, status); await refresh(); } catch { /* ignore */ }
  }, [refresh]);
```
```tsx
        <JournalTable events={events} onSetStatus={onSetStatus} />
```

- [ ] **Step 4: Adapter `Dashboard.test.tsx`** — ajouter `status: "active"` aux events du fixture
(l'`ApiEvent` gagne `status`). Le test existant reste sinon inchangé (il vérifie KPI/sections/journal/CSV/PDF).

- [ ] **Step 5: Lancer les tests + build**
Run: `cd frontend && npm run test && npm run build`
Expected: tous verts ; build OK.

- [ ] **Step 6: Commit**
```bash
git add frontend/components/dashboard/JournalTable.tsx frontend/components/dashboard/DashboardFilters.tsx frontend/components/dashboard/Dashboard.tsx frontend/components/dashboard/JournalTable.test.tsx frontend/components/dashboard/DashboardFilters.test.tsx frontend/components/dashboard/Dashboard.test.tsx
git commit -m "feat(frontend): alert status badge + ack/resolve actions + status filter"
```

---

### Task 5: Journal de décisions

**Files:**
- Modify: `docs/DECISIONS.md`

- [ ] **Step 1: Ajouter l'entrée** (en haut, après l'intro)
```markdown
## 2026-08-31 — V1.5 : acquittement des alertes anonyme (identité en V2)
**Contexte.** Cycle de vie des infractions (active/ack/resolved) attendu (ISA-18.2), mais pas
d'authentification en V1.
**Décision.** Le statut est persisté sur l'event et modifiable via `POST /events/{id}/status` ;
l'acquittement est **anonyme** (pas de `acked_by`). Transitions libres entre les trois statuts.
**Conséquence.** L'auth V2 ajoutera l'identité de l'opérateur (qui a acquitté/résolu) et,
si besoin, des transitions contrôlées.
```

- [ ] **Step 2: Commit**
```bash
git add docs/DECISIONS.md
git commit -m "docs: decision log (anonymous alert acknowledgement)"
```

---

## Self-Review

**1. Couverture spec :** colonne `status` + migration + `set_status` + filtre ✅ (T1) ; endpoint
POST status (200/422/404) + GET filter ✅ (T2) ; `setEventStatus` + `ApiEvent.status` ✅ (T3) ;
badge + actions + filtre statut + câblage ✅ (T4) ; décision ✅ (T5). Zéro dépendance ✅.

**2. Placeholders :** aucun — schéma/migration/méthode/endpoint/composants/tests complets. Les
éditions `journal.py` (T1), `app.py`/`schemas.py` (T2) et composants front (T4) sont ancrées.

**3. Cohérence des types :** `status ∈ {active,ack,resolved}` partout (backend validation T2,
`AlertStatus` front T3/T4). `set_status` (T1) → endpoint (T2) → `setEventStatus` (T3) →
`onSetStatus` (T4). `ApiEvent.status` (T3) consommé par `JournalTable`/`StatusBadge` (T4).
`DashFilters.status` (T4) → `getEvents({status})` (T3) → `journal.events(status=…)` (T1).
Fixtures front mis à jour pour le nouveau champ requis `status`.
```
