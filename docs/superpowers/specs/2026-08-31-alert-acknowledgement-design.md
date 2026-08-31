# V1.5 — Acquittement des alertes (ISA-18.2) — Design

**Date :** 2026-08-31
**Phase :** V1.5 (durcissement) — premier incrément.
**Dépend de :** P3-a (journal), P2-b (dashboard). Tout mergé sur `main`.
**Statut :** validé

## 1. Objectif

Donner aux infractions un **cycle de vie opérateur** — `active → ack (acquittée) → resolved
(résolue)` — persisté côté serveur et pilotable depuis le dashboard. Comble le manque
d'acquittement relevé en P3-c (esprit **ISA-18.2**).

## 2. Décisions de conception (validées)

- **Statut persisté** sur les events (`active` par défaut). Un seul endpoint de mise à jour
  `POST /events/{id}/status`.
- **Transitions libres** entre les trois statuts (pas de machine à états stricte en V1.5).
- **Acquittement anonyme** : pas d'auth en V1 → pas de `acked_by`. L'identité de l'opérateur
  viendra avec l'auth V2. Documenté.
- Réutilise `StatusBadge` (front) et le concept `AlertStatus` déjà présents (P2-a).

## 3. Périmètre

**Dans ce sous-projet :**
- Backend : colonne `status` + `set_status` + filtre + endpoint + GET param.
- Frontend : `setEventStatus`, badge + actions dans `JournalTable`, filtre statut, câblage.

**Hors périmètre :** identité opérateur (V2 auth), transitions strictes, notification sur ack,
acquittement groupé (bulk) → plus tard.

## 4. Backend

### `Journal` (`app/persistence/journal.py`)
- **Schéma `events`** : `status TEXT NOT NULL DEFAULT 'active'` (ajouté au `CREATE` **et**
  migration défensive `ALTER TABLE events ADD COLUMN status TEXT NOT NULL DEFAULT 'active'`).
- `record_event(...)` : insère `status='active'` (les nouveaux events sont actifs).
- `set_status(event_id: int, status: str) -> bool` : `UPDATE events SET status=? WHERE id=?` ;
  renvoie `True` si une ligne a été modifiée. Sous le lock d'écriture.
- `events()` et `event()` : incluent `status` dans le SELECT et le dict retourné ; `events()`
  gagne un filtre `status` (clause `status = ?`).

### API (`app/api/app.py`, `app/api/schemas.py`)
- `class StatusUpdate(BaseModel): status: str` (schemas).
- **`POST /events/{event_id}/status`** body `{status}` :
  - `status not in {"active","ack","resolved"}` → **422** ;
  - `journal.set_status(id, status)` → si `False` (id inconnu) → **404** ;
  - sinon renvoie `journal.event(id)` (l'event à jour).
- **`GET /events`** : nouveau paramètre `status` transmis à `journal.events(...)`.

## 5. Frontend

### `lib/eventsApi.ts`
- `ApiEvent` gagne `status: "active" | "ack" | "resolved"`.
- `setEventStatus(id, status, fetchFn=fetch) -> Promise<void>` : `POST ${API}/events/${id}/status`
  (JSON `{status}`), rejette sur erreur HTTP.
- `getEvents(params)` accepte `status`.

### `components/dashboard/JournalTable.tsx`
- Nouvelle colonne **Statut** = `<StatusBadge status={e.status} />`.
- Actions par ligne : **Acquitter** (si `status !== "ack"` et `!== "resolved"`… c.-à-d. si
  `active`) et **Résoudre** (si `status !== "resolved"`). Chaque clic appelle
  `onSetStatus(id, next)` (prop remontée au `Dashboard`).
- Signature : `JournalTable({ events, onSetStatus })` ; `onSetStatus` optionnel (compat).

### `components/dashboard/DashboardFilters.tsx`
- `DashFilters` gagne `status: "" | "active" | "ack" | "resolved"`.
- Un `<select aria-label="Statut">` (Tous / Actives / Acquittées / Résolues).

### `components/dashboard/Dashboard.tsx`
- `filters` initial gagne `status: ""` ; `getEvents` reçoit `status`.
- `onSetStatus(id, status)` = `await setEventStatus(id, status); refresh()`.

## 6. Fichiers

```
backend/app/persistence/journal.py     # status: colonne + record + set_status + reads/filter
backend/app/api/app.py                  # POST /events/{id}/status ; GET /events?status
backend/app/api/schemas.py              # StatusUpdate
backend/tests/test_journal.py           # ajouts set_status + filtre status
backend/tests/test_status_api.py        # endpoint (200/422/404) + GET filter
frontend/lib/eventsApi.ts (+ .test.ts)  # status + setEventStatus
frontend/components/dashboard/JournalTable.tsx (+ .test.tsx)
frontend/components/dashboard/DashboardFilters.tsx (+ .test.tsx)
frontend/components/dashboard/Dashboard.tsx (+ .test.tsx)
docs/DECISIONS.md                       # ack anonyme
```

## 7. Tests (TDD)

- **Journal** : `record_event` → `status "active"` ; `set_status(id, "ack")` → `event(id).status
  == "ack"` et `True` ; id inconnu → `False` ; `events(status="active")` filtre.
- **`test_status_api`** : `POST /events/{id}/status {"status":"ack"}` → 200 + event à `ack` ;
  statut invalide → 422 ; id inconnu → 404 ; `GET /events?status=active` filtre.
- **Frontend** : `setEventStatus` construit `POST /events/1/status` ; `JournalTable` rend le
  badge + les boutons contextuels, un clic appelle `onSetStatus(id, "ack"|"resolved")` ;
  `DashboardFilters` remonte le statut.
- Suites existantes vertes (backend **108**, frontend **45**) ; `npm run build` OK.

## 8. Critères d'acceptation

1. Un event nouvellement créé est `active` ; `POST /events/{id}/status` le fait passer à
   `ack` puis `resolved` (persisté).
2. Le dashboard affiche le statut et permet Acquitter / Résoudre par ligne, avec refresh.
3. Le filtre statut restreint le journal.
4. Statut invalide → 422 ; id inconnu → 404.
5. Zéro nouvelle dépendance ; suites existantes vertes.
