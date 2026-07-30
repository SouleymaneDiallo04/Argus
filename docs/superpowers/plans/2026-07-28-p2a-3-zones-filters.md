# P2-a.3 — Éditeur de zones & filtres — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compléter P2-a : un éditeur de zones (dessin de polygones sur la vidéo + EPI requis + risque) qui persiste via `PUT /zones`, l'affichage des zones existantes, et des filtres/recherche live sur le roster et les alertes.

**Architecture:** Logique pure testable (client REST `/zones`, store de risque localStorage, filtres) + composants clients (`ZoneEditor`, `FilterBar` fonctionnelle) câblés dans le `Workspace` P2-a.2.

**Tech Stack:** Next.js 16 (composants clients), TypeScript, Canvas 2D, `fetch`, `localStorage`, Vitest + Testing Library.

## Global Constraints

- **Acquis P2-a.1/.2** (branche depuis `main` post-PR #6) : design system, `Severity`, `Alert`, `RosterEntry`, `ZoneRisk`/`riskOf`, `VideoStage`, `Workspace`, `FilterBar` (statique), `Roster`, `AlertsPanel`. Réutiliser.
- **Contrat REST P1b** : `GET /zones` → `{ zones:[{name, polygon:[[x,y]...], required_ppe:[...]}] }` ; `PUT /zones` remplace la config (même schéma, 422 si invalide — polygone ≥ 3 points, `required_ppe ⊆ {helmet, safety-vest, mask, shoes}`). Le **risque de zone reste côté front** (`localStorage`), jamais envoyé au backend.
- **Composants navigateur** (`canvas`, `fetch`, `localStorage`) → `"use client"`. Logique pure hors React (testable jsdom).
- API : `NEXT_PUBLIC_ARGUS_API` (défaut `http://localhost:8000`). Le CORS backend (P2-a.1) autorise `GET/PUT /zones`.
- **Tests** : Vitest + Testing Library ; logique pure en TDD ; `fetch`/`localStorage` mockés ou jsdom. Lancer via `npm run test` depuis `frontend/`.
- Commits : préfixe conventionnel, anglais, **sans `Co-Authored-By`**.

Rappel taxonomie EPI backend : `{helmet, safety-vest, mask, shoes}`.

---

### Task 1: Client REST /zones + store de risque

**Files:**
- Create: `frontend/lib/zonesApi.ts`, `frontend/lib/zoneRiskStore.ts`
- Test: `frontend/lib/zonesApi.test.ts`

**Interfaces:**
- Produces: types `ApiZone = { name; polygon: [number,number][]; required_ppe: string[] }` ; `getZones(fetchFn?) -> Promise<ApiZone[]>` ; `putZones(zones, fetchFn?) -> Promise<void>` ; `getZoneRisk(name) -> ZoneRisk | undefined` ; `setZoneRisk(name, risk)`.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/lib/zonesApi.test.ts`

```ts
import { getZones, putZones } from "./zonesApi";
import { getZoneRisk, setZoneRisk } from "./zoneRiskStore";

function mockFetch(body: unknown, ok = true, status = 200) {
  return async () => ({ ok, status, json: async () => body }) as Response;
}

test("getZones renvoie la liste de zones", async () => {
  const zones = await getZones(mockFetch({ zones: [{ name: "z", polygon: [[0, 0], [10, 0], [10, 10]], required_ppe: ["helmet"] }] }) as typeof fetch);
  expect(zones).toHaveLength(1);
  expect(zones[0].name).toBe("z");
});

test("putZones envoie un PUT et rejette sur erreur HTTP", async () => {
  let captured: RequestInit | undefined;
  const fetchFn = (async (_url: string, init?: RequestInit) => {
    captured = init;
    return { ok: true, status: 200, json: async () => ({}) } as Response;
  }) as typeof fetch;
  await putZones([{ name: "z", polygon: [[0, 0], [10, 0], [10, 10]], required_ppe: ["helmet"] }], fetchFn);
  expect(captured?.method).toBe("PUT");
  expect(JSON.parse(captured?.body as string)).toEqual({
    zones: [{ name: "z", polygon: [[0, 0], [10, 0], [10, 10]], required_ppe: ["helmet"] }],
  });
  await expect(putZones([], mockFetch({}, false, 422) as typeof fetch)).rejects.toThrow();
});

test("zoneRiskStore persiste le risque par nom", () => {
  setZoneRisk("Fonderie", "high");
  expect(getZoneRisk("Fonderie")).toBe("high");
  expect(getZoneRisk("Inconnue")).toBeUndefined();
});
```

- [ ] **Step 2: Lancer le test** — `cd frontend && npx vitest run lib/zonesApi.test.ts` → FAIL.

- [ ] **Step 3: Écrire l'implémentation**

`frontend/lib/zonesApi.ts` :
```ts
export type ApiZone = { name: string; polygon: [number, number][]; required_ppe: string[] };
type ZonesConfig = { zones: ApiZone[] };

const API = process.env.NEXT_PUBLIC_ARGUS_API ?? "http://localhost:8000";

export async function getZones(fetchFn: typeof fetch = fetch): Promise<ApiZone[]> {
  const res = await fetchFn(`${API}/zones`);
  if (!res.ok) throw new Error(`GET /zones -> ${res.status}`);
  const data = (await res.json()) as ZonesConfig;
  return data.zones ?? [];
}

export async function putZones(zones: ApiZone[], fetchFn: typeof fetch = fetch): Promise<void> {
  const res = await fetchFn(`${API}/zones`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ zones }),
  });
  if (!res.ok) throw new Error(`PUT /zones -> ${res.status}`);
}
```

`frontend/lib/zoneRiskStore.ts` :
```ts
import type { ZoneRisk } from "./priority";

const KEY = "argus.zoneRisk";
type Store = Record<string, ZoneRisk>;

function read(): Store {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Store;
  } catch {
    return {};
  }
}

export function getZoneRisk(name: string): ZoneRisk | undefined {
  return read()[name];
}

export function setZoneRisk(name: string, risk: ZoneRisk): void {
  const s = read();
  s[name] = risk;
  localStorage.setItem(KEY, JSON.stringify(s));
}
```

- [ ] **Step 4: Lancer le test** — PASS (3).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/zonesApi.ts frontend/lib/zoneRiskStore.ts frontend/lib/zonesApi.test.ts
git commit -m "feat(frontend): /zones REST client + zone-risk localStorage store"
```

---

### Task 2: Filtres (roster + alertes)

**Files:**
- Create: `frontend/lib/filters.ts`
- Test: `frontend/lib/filters.test.ts`

**Interfaces:**
- Consumes: `Alert`, `RosterEntry`.
- Produces: type `Filters = { zone?: string; ppe?: string; status?: Alert["status"]; query?: string }` ; `filterRoster(roster, f)` ; `filterAlerts(alerts, f)`.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/lib/filters.test.ts`

```ts
import { filterRoster, filterAlerts } from "./filters";
import type { RosterEntry } from "@/lib/live";
import type { Alert } from "@/lib/types";

const roster: RosterEntry[] = [
  { trackId: 37, zone: "Fonderie", missing: ["casque"], compliant: false },
  { trackId: 8, zone: "Bureau", missing: [], compliant: true },
];

test("filterRoster filtre par EPI manquant et par recherche d'ID", () => {
  expect(filterRoster(roster, { ppe: "casque" }).map((r) => r.trackId)).toEqual([37]);
  expect(filterRoster(roster, { query: "#8" }).map((r) => r.trackId)).toEqual([8]);
});

test("filterAlerts filtre par statut et par zone", () => {
  const alerts: Alert[] = [
    { id: "a", severity: "crit", time: "00:01", zone: "Fonderie", personId: "#37", missing: ["casque"], status: "active" },
    { id: "b", severity: "low", time: "00:02", zone: "Bureau", personId: "#8", missing: ["masque"], status: "resolved" },
  ];
  expect(filterAlerts(alerts, { status: "active" }).map((a) => a.id)).toEqual(["a"]);
  expect(filterAlerts(alerts, { zone: "bureau" }).map((a) => a.id)).toEqual(["b"]);
});
```

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `frontend/lib/filters.ts`

```ts
import type { Alert } from "./types";
import type { RosterEntry } from "./live";

export type Filters = { zone?: string; ppe?: string; status?: Alert["status"]; query?: string };

const idMatches = (id: string | number, q?: string) =>
  !q || String(id).includes(q.replace("#", ""));
const zoneMatches = (zone: string | null, z?: string) =>
  !z || (zone ?? "").toLowerCase().includes(z.toLowerCase());

export function filterRoster(roster: RosterEntry[], f: Filters): RosterEntry[] {
  return roster.filter(
    (r) => (!f.ppe || r.missing.includes(f.ppe)) && zoneMatches(r.zone, f.zone) && idMatches(r.trackId, f.query)
  );
}

export function filterAlerts(alerts: Alert[], f: Filters): Alert[] {
  return alerts.filter(
    (a) =>
      (!f.status || a.status === f.status) &&
      (!f.ppe || a.missing.includes(f.ppe)) &&
      zoneMatches(a.zone, f.zone) &&
      idMatches(a.personId, f.query)
  );
}
```

- [ ] **Step 4: Lancer le test** — PASS (2).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/filters.ts frontend/lib/filters.test.ts
git commit -m "feat(frontend): client-side filters for roster and alerts"
```

---

### Task 3: FilterBar fonctionnelle

**Files:**
- Modify: `frontend/components/console/FilterBar.tsx`
- Test: `frontend/components/console/FilterBar.test.tsx`

**Interfaces:**
- Consumes: `Filters` (Task 2).
- Produces: `<FilterBar filters onChange onEditZones? />` — recherche + selects zone/EPI/statut ; chaque changement appelle `onChange(nextFilters)`.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/components/console/FilterBar.test.tsx`

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { FilterBar } from "./FilterBar";

test("FilterBar remonte la recherche et le filtre EPI", () => {
  let last: Record<string, unknown> = {};
  render(<FilterBar filters={{}} onChange={(f) => (last = f)} />);
  fireEvent.change(screen.getByLabelText(/rechercher/i), { target: { value: "#37" } });
  expect(last).toMatchObject({ query: "#37" });
  fireEvent.change(screen.getByLabelText(/epi/i), { target: { value: "casque" } });
  expect(last).toMatchObject({ ppe: "casque" });
});
```

- [ ] **Step 2: Lancer le test** — FAIL (FilterBar actuelle n'a pas ces props/labels).

- [ ] **Step 3: Écrire l'implémentation** — remplacer `frontend/components/console/FilterBar.tsx`

```tsx
"use client";

import type { Filters } from "@/lib/filters";

const PPE = ["helmet", "safety-vest", "mask", "shoes"];
const STATUS: { v: string; l: string }[] = [
  { v: "", l: "Tous statuts" },
  { v: "active", l: "Actives" },
  { v: "ack", l: "Acquittées" },
  { v: "resolved", l: "Résolues" },
];

export function FilterBar({
  filters,
  onChange,
  onEditZones,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
  onEditZones?: () => void;
}) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  const selCls = "rounded-lg border border-line bg-s1 px-3 py-1.5 text-[13px] font-semibold text-ink2";

  return (
    <div className="flex items-center gap-2.5 border-b border-line bg-bg px-4 py-2.5">
      <div className="flex items-center gap-2.5 rounded-lg border border-line2 bg-s2 px-3 py-1.5 font-bold">
        <span className="h-1.5 w-1.5 rounded-full bg-ok" />
        Meknès-Nord
      </div>
      <input
        aria-label="Rechercher"
        value={filters.query ?? ""}
        onChange={(e) => set({ query: e.target.value || undefined })}
        className="min-w-0 max-w-[300px] flex-1 rounded-lg border border-line bg-s1 px-3 py-1.5 text-[13px] text-ink placeholder:text-ink3"
        placeholder="Rechercher un ID (ex. #37)…"
      />
      <select aria-label="EPI" className={selCls} value={filters.ppe ?? ""} onChange={(e) => set({ ppe: e.target.value || undefined })}>
        <option value="">Tous EPI</option>
        {PPE.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <select aria-label="Statut" className={selCls} value={filters.status ?? ""} onChange={(e) => set({ status: (e.target.value || undefined) as Filters["status"] })}>
        {STATUS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
      </select>
      <div className="flex-1" />
      {onEditZones ? (
        <button onClick={onEditZones} className="rounded-lg border border-line2 px-3 py-1.5 font-bold text-ink hover:bg-s2">
          Éditer les zones
        </button>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Lancer le test** — PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/console/FilterBar.tsx frontend/components/console/FilterBar.test.tsx
git commit -m "feat(frontend): functional FilterBar (search + PPE/status filters)"
```

---

### Task 4: Éditeur de zones (dessin + persistance)

**Files:**
- Create: `frontend/lib/zoneGeometry.ts`, `frontend/components/console/ZoneEditor.tsx`
- Test: `frontend/lib/zoneGeometry.test.ts`

**Interfaces:**
- Consumes: `ApiZone`/`putZones` (Task 1), `setZoneRisk` (Task 1), `ZoneRisk`.
- Produces: `toFramePolygon(points, scaleX, scaleY) -> [number,number][]` (arrondi entier) ; `buildZoneModel(name, framePolygon, ppe) -> ApiZone` ; `<ZoneEditor videoWidth videoHeight onSaved onCancel />` (client).

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/lib/zoneGeometry.test.ts`

```ts
import { toFramePolygon, buildZoneModel } from "./zoneGeometry";

test("toFramePolygon convertit les points d'affichage en coords frame (entiers)", () => {
  expect(toFramePolygon([[10, 20], [30, 40]], 2, 3)).toEqual([[20, 60], [60, 120]]);
});

test("buildZoneModel construit une ApiZone valide", () => {
  const z = buildZoneModel("Coulée", [[0, 0], [10, 0], [10, 10]], ["helmet", "shoes"]);
  expect(z).toEqual({ name: "Coulée", polygon: [[0, 0], [10, 0], [10, 10]], required_ppe: ["helmet", "shoes"] });
});
```

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation**

`frontend/lib/zoneGeometry.ts` :
```ts
import type { ApiZone } from "./zonesApi";

export function toFramePolygon(points: [number, number][], scaleX: number, scaleY: number): [number, number][] {
  return points.map(([x, y]) => [Math.round(x * scaleX), Math.round(y * scaleY)]);
}

export function buildZoneModel(name: string, framePolygon: [number, number][], ppe: string[]): ApiZone {
  return { name, polygon: framePolygon, required_ppe: ppe };
}
```

`frontend/components/console/ZoneEditor.tsx` :
```tsx
"use client";

import { useRef, useState } from "react";
import { putZones, type ApiZone } from "@/lib/zonesApi";
import { setZoneRisk } from "@/lib/zoneRiskStore";
import { toFramePolygon, buildZoneModel } from "@/lib/zoneGeometry";
import type { ZoneRisk } from "@/lib/priority";

const PPE = ["helmet", "safety-vest", "mask", "shoes"];

export function ZoneEditor({
  videoWidth,
  videoHeight,
  existing,
  onSaved,
  onCancel,
}: {
  videoWidth: number;
  videoHeight: number;
  existing: ApiZone[];
  onSaved: () => void;
  onCancel: () => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [points, setPoints] = useState<[number, number][]>([]);
  const [name, setName] = useState("");
  const [ppe, setPpe] = useState<string[]>(["helmet", "safety-vest"]);
  const [risk, setRisk] = useState<ZoneRisk>("high");
  const [saving, setSaving] = useState(false);

  function addPoint(e: React.MouseEvent) {
    const rect = boxRef.current?.getBoundingClientRect();
    if (!rect) return;
    setPoints((p) => [...p, [e.clientX - rect.left, e.clientY - rect.top]]);
  }
  function togglePpe(x: string) {
    setPpe((cur) => (cur.includes(x) ? cur.filter((p) => p !== x) : [...cur, x]));
  }

  async function save() {
    if (points.length < 3 || !name.trim() || !boxRef.current) return;
    setSaving(true);
    try {
      const rect = boxRef.current.getBoundingClientRect();
      const poly = toFramePolygon(points, (videoWidth || rect.width) / rect.width, (videoHeight || rect.height) / rect.height);
      const zone = buildZoneModel(name.trim(), poly, ppe);
      await putZones([...existing, zone]);
      setZoneRisk(zone.name, risk);
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  const path = points.map(([x, y]) => `${x},${y}`).join(" ");

  return (
    <div className="absolute inset-0 z-10 flex">
      <div ref={boxRef} onClick={addPoint} className="relative flex-1 cursor-crosshair bg-black/40">
        <svg className="pointer-events-none absolute inset-0 h-full w-full">
          {points.length > 0 && (
            <polygon points={path} fill="rgba(59,130,246,.15)" stroke="#3B82F6" strokeWidth="2" strokeDasharray="6 4" />
          )}
          {points.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r="4" fill="#3B82F6" />
          ))}
        </svg>
        <div className="pointer-events-none absolute left-3 top-3 rounded bg-black/70 px-2.5 py-1 text-[12px] text-ink2">
          Clique pour poser les sommets ({points.length})
        </div>
      </div>
      <aside className="w-72 flex-none border-l border-line bg-s1 p-4">
        <h3 className="mb-3 text-[13px] font-bold">Nouvelle zone</h3>
        <label className="mb-1 block text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">Nom</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="ex. Fonderie·Coulée"
          className="mb-4 w-full rounded-lg border border-line bg-s2 px-3 py-1.5 text-[13px] text-ink" />
        <div className="mb-1 text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">EPI requis</div>
        <div className="mb-4 flex flex-wrap gap-1.5">
          {PPE.map((p) => (
            <button key={p} onClick={() => togglePpe(p)}
              className={`rounded-md px-2.5 py-1 text-[12px] font-semibold ${ppe.includes(p) ? "bg-brand/20 text-brand" : "bg-s2 text-ink3"}`}>
              {p}
            </button>
          ))}
        </div>
        <div className="mb-1 text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">Risque</div>
        <div className="mb-5 flex gap-1.5">
          {(["low", "medium", "high"] as ZoneRisk[]).map((r) => (
            <button key={r} onClick={() => setRisk(r)}
              className={`flex-1 rounded-md py-1.5 text-[12px] font-bold ${risk === r ? "bg-warn/20 text-warn" : "bg-s2 text-ink3"}`}>
              {r === "low" ? "Faible" : r === "medium" ? "Moyen" : "Élevé"}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <button disabled={saving || points.length < 3 || !name.trim()} onClick={save}
            className="flex-1 rounded-lg bg-brand px-3 py-2 text-[13px] font-bold text-white disabled:opacity-40">
            {saving ? "…" : "Enregistrer"}
          </button>
          <button onClick={onCancel} className="rounded-lg border border-line2 px-3 py-2 text-[13px] font-bold text-ink hover:bg-s2">
            Annuler
          </button>
        </div>
        <button onClick={() => setPoints([])} className="mt-3 text-[12px] text-ink3 hover:text-ink">Effacer le tracé</button>
      </aside>
    </div>
  );
}
```

- [ ] **Step 4: Lancer le test** — `npx vitest run lib/zoneGeometry.test.ts` → PASS (2).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/zoneGeometry.ts frontend/components/console/ZoneEditor.tsx frontend/lib/zoneGeometry.test.ts
git commit -m "feat(frontend): zone editor (polygon drawing + PPE/risk + PUT /zones)"
```

---

### Task 5: Câblage — filtres + zones dans le Workspace

**Files:**
- Modify: `frontend/components/console/Workspace.tsx`, `frontend/components/console/VideoStage.tsx`, `frontend/app/page.tsx`
- Test: `frontend/components/console/Workspace.test.tsx`

**Interfaces:**
- Consumes: `FilterBar` (T3), `filterRoster`/`filterAlerts` (T2), `getZones` (T1), `ZoneEditor` (T4).
- Produces: `Workspace` gère l'état des filtres + le mode éditeur + charge/affiche les zones existantes. `VideoStage` accepte `zones` (dessine les polygones existants) et `editing` + `onSaved`/`onCancel`.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/components/console/Workspace.test.tsx`

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { Workspace } from "./Workspace";

beforeAll(() => {
  // @ts-expect-error shim WS
  globalThis.WebSocket = class { readyState = 0; onopen = null; onclose = null; onerror = null; onmessage = null; send() {} close() {} };
  // fetch mock : GET /zones vide
  globalThis.fetch = (async () => ({ ok: true, status: 200, json: async () => ({ zones: [] }) })) as typeof fetch;
});

test("Workspace affiche la barre de filtres et ouvre l'éditeur de zones", () => {
  render(<Workspace />);
  expect(screen.getByLabelText(/rechercher/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /éditer les zones/i }));
  expect(screen.getByText(/Nouvelle zone/i)).toBeInTheDocument();
});
```
*(Note : `FilterBar` vit désormais dans le `Workspace`. Retirer `<FilterBar />` de `app/page.tsx` — voir Step 3. Adapter `console.test.tsx` si besoin : la barre de filtres n'est plus un enfant direct de la page mais du Workspace, donc les requêtes `getByLabelText(/rechercher/i)` restent trouvables au rendu de la page.)*

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation**

Remplacer `frontend/components/console/Workspace.tsx` :
```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useLiveStream } from "@/hooks/useLiveStream";
import { rosterFromResults, alertFromEvent } from "@/lib/live";
import { riskOf } from "@/lib/zoneRisk";
import { filterRoster, filterAlerts, type Filters } from "@/lib/filters";
import { getZones, type ApiZone } from "@/lib/zonesApi";
import { VideoStage } from "./VideoStage";
import { Roster } from "./Roster";
import { AlertsPanel } from "./AlertsPanel";
import { FilterBar } from "./FilterBar";
import { MetricTile } from "@/components/ui/MetricTile";
import type { Alert } from "@/lib/types";

export function Workspace() {
  const { response, sendFrame, status } = useLiveStream();
  const [filters, setFilters] = useState<Filters>({});
  const [editing, setEditing] = useState(false);
  const [zones, setZones] = useState<ApiZone[]>([]);

  const loadZones = () => getZones().then(setZones).catch(() => {});
  useEffect(() => { loadZones(); }, []);

  const roster = useMemo(() => (response ? rosterFromResults(response.results) : []), [response]);
  const alerts: Alert[] = useMemo(
    () => (response ? response.events.map((e) => alertFromEvent(e, riskOf)) : []),
    [response]
  );
  const shownRoster = useMemo(() => filterRoster(roster, filters), [roster, filters]);
  const shownAlerts = useMemo(() => filterAlerts(alerts, filters), [alerts, filters]);
  const nonCompliant = shownRoster.filter((r) => !r.compliant).length;

  return (
    <div className="grid min-h-0 grid-rows-[auto_1fr]">
      <FilterBar filters={filters} onChange={setFilters} onEditZones={() => setEditing(true)} />
      <div className="grid min-h-0 grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] gap-3.5 overflow-hidden p-3.5">
        <div className="flex min-h-0 flex-col gap-3.5">
          <VideoStage
            response={response}
            onFrame={sendFrame}
            zones={zones}
            editing={editing}
            onSaved={() => { setEditing(false); loadZones(); }}
            onCancel={() => setEditing(false)}
          />
          <div className="grid grid-cols-4 gap-2.5">
            <MetricTile label="Personnes" value={String(shownRoster.length)} />
            <MetricTile label="Non conformes" value={String(nonCompliant)} tone="crit" />
            <MetricTile label="Alertes" value={String(shownAlerts.length)} tone="warn" />
            <MetricTile label="Service" value={status === "open" ? "OK" : "…"} tone={status === "open" ? "ok" : "default"} />
          </div>
        </div>
        <div className="grid min-h-0 grid-rows-2 gap-3.5">
          <Roster entries={shownRoster} />
          <AlertsPanel alerts={shownAlerts} />
        </div>
      </div>
    </div>
  );
}
```

Modifier `frontend/components/console/VideoStage.tsx` — étendre la signature et dessiner les zones + intégrer l'éditeur. Remplacer la signature et le `return` :

Nouvelle signature (props) :
```tsx
import { ZoneEditor } from "./ZoneEditor";
import type { ApiZone } from "@/lib/zonesApi";

export function VideoStage({
  response,
  onFrame,
  zones = [],
  editing = false,
  onSaved,
  onCancel,
}: {
  response: FrameResponse | null;
  onFrame: (video: HTMLVideoElement, canvas: HTMLCanvasElement) => void;
  zones?: ApiZone[];
  editing?: boolean;
  onSaved?: () => void;
  onCancel?: () => void;
}) {
```

Dans l'effet de dessin des overlays, après avoir dessiné les boîtes, ajouter le tracé des zones existantes (en coords frame → écran) :
```tsx
    // zones existantes (coords frame -> écran)
    for (const z of zones) {
      ctx.strokeStyle = "rgba(59,130,246,.7)";
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      z.polygon.forEach(([px, py], i) => {
        const x = px * (o.width / v.videoWidth), y = py * (o.height / v.videoHeight);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.stroke();
      ctx.setLineDash([]);
    }
```
*(placer ce bloc juste avant la fin de l'effet `useEffect([response])`, et ajouter `zones` aux dépendances de cet effet : `}, [response, zones]);`)*

Ajouter l'éditeur dans le `return`, juste avant la fermeture du conteneur racine (`</div>`), après le bloc `source === "none"` :
```tsx
      {editing && videoRef.current ? (
        <ZoneEditor
          videoWidth={videoRef.current.videoWidth}
          videoHeight={videoRef.current.videoHeight}
          existing={zones}
          onSaved={() => onSaved?.()}
          onCancel={() => onCancel?.()}
        />
      ) : null}
```

Modifier `frontend/app/page.tsx` — retirer `<FilterBar />` (désormais dans le Workspace) :
```tsx
import { NavRail } from "@/components/console/NavRail";
import { VitalStrip } from "@/components/console/VitalStrip";
import { Workspace } from "@/components/console/Workspace";

export default function Page() {
  return (
    <div className="grid h-dvh grid-cols-[60px_1fr]">
      <NavRail />
      <div className="grid min-w-0 grid-rows-[auto_1fr]">
        <VitalStrip />
        <Workspace />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Lancer les tests + build**

Run: `cd frontend && npm run test && npm run build`
Expected: tous verts (adapter `console.test.tsx` si l'assertion sur la source échoue — la page monte le Workspace qui monte VideoStage, donc le bouton « Webcam » et le champ « Rechercher » sont présents) ; build réussi.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/console/Workspace.tsx frontend/components/console/VideoStage.tsx frontend/app/page.tsx frontend/components/console/Workspace.test.tsx frontend/app/console.test.tsx
git commit -m "feat(frontend): wire filters + zone editor + existing zones into console"
```

---

## Self-Review

**1. Couverture spec (P2-a.3) :** éditeur de zones (dessin polygones + EPI requis + risque) ✅ (Task 4 ZoneEditor) ; persistance `PUT /zones` + risque en `localStorage` ✅ (Task 1 + 4) ; affichage des zones existantes ✅ (Task 5 VideoStage) ; filtres/recherche live (zone/EPI/statut/ID) ✅ (Task 2 + 3 + 5). Cela clôt le périmètre **P2-a** (le dashboard historique reste P2-b, après P3).

**2. Placeholders :** aucun — code complet. Les modifications de `VideoStage` (Task 5) sont décrites précisément (signature, bloc de dessin des zones + dépendance `zones`, insertion de `ZoneEditor`) plutôt que réécrites en entier pour éviter la divergence avec le fichier P2-a.2 ; l'implémenteur applique ces éditions ciblées.

**3. Cohérence des types :** `ApiZone` (T1) consommé par `zoneGeometry`/`ZoneEditor` (T4), `VideoStage`/`Workspace` (T5) ; `Filters` (T2) produit par `FilterBar` (T3) et consommé par `filterRoster`/`filterAlerts` (T2) dans `Workspace` (T5) ; `ZoneRisk` (P2-a.2) utilisé par `zoneRiskStore` (T1) et `ZoneEditor` (T4) ; `RosterEntry`/`Alert` réutilisés. Le risque de zone ne transite jamais par l'API (séparation front/back respectée).
