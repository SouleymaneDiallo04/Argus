# P2-b — Dashboard « Analytique » — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Une route `/dashboard` qui montre le taux de conformité (global/zone/temps) et le journal d'infractions filtrable (avec vignette floutée), en polling ~15 s.

**Architecture:** Clients REST purs (`statsApi`/`eventsApi`) + maths de charts pures (`lib/chart.ts`) + composants de présentation (charts SVG maison, `JournalTable`, `KpiRow`) assemblés dans `Dashboard`, branchés via un `Shell` partagé et une `NavRail` navigante.

**Tech Stack:** Next.js 16 (App Router, client components), TypeScript, SVG maison (zéro lib de charts), Vitest + Testing Library.

## Global Constraints

- **Zéro nouvelle dépendance** (charts en SVG maison).
- Clients REST : pattern `zonesApi` — `API = process.env.NEXT_PUBLIC_ARGUS_API ?? "http://localhost:8000"`, `fetchFn` injectable.
- Types alignés backend : `ApiEvent = {id, ts, stream_ts, camera, zone: string|null, track_id, missing: string[], snapshot: string|null}` ; `Stats = {global, by_zone[], over_time[], violations{total, by_zone}}` avec `rate: number | null`.
- **Sévérité côté front** : `severityFor(riskOf(zone), missing)` (mêmes `lib/priority` + `lib/zoneRisk` que la console live).
- **Polling 15 s**, pause si `document.hidden` ; erreurs réseau avalées (garde les dernières données).
- **Routing réel** : `/` (Live) et `/dashboard` (Analytique) sous un `Shell` commun ; NavRail navigante via `next/link`, actif via **prop** `active`.
- Réutiliser `MetricTile`, `SeverityTag`, `PpeChip`, tokens du design system. Rien de décoratif.
- Composants navigateur (`fetch`, `document`, `setInterval`) → `"use client"`.
- Tests : Vitest + Testing Library ; logique pure en TDD ; `fetch` mocké/injecté. Suite frontend existante (**30**) verte ; `npm run build` OK. Interpréteur test : `npm run test` depuis `frontend/`.
- Commits : préfixe conventionnel, anglais, **sans `Co-Authored-By`**.

---

### Task 1: Clients REST — `statsApi` + `eventsApi`

**Files:**
- Create: `frontend/lib/http.ts`, `frontend/lib/statsApi.ts`, `frontend/lib/eventsApi.ts`
- Test: `frontend/lib/statsApi.test.ts`, `frontend/lib/eventsApi.test.ts`

**Interfaces:**
- Produces: `getStats(params?, fetchFn?) -> Promise<Stats>` ; `getEvents(params?, fetchFn?) -> Promise<ApiEvent[]>` ; `snapshotUrl(id) -> string` ; types `Stats`, `Rate`, `ZoneStat`, `Bucket`, `ApiEvent`.

- [ ] **Step 1: Écrire les tests qui échouent**

`frontend/lib/statsApi.test.ts` :
```ts
import { getStats } from "./statsApi";

test("getStats parse la réponse et passe les filtres en query", async () => {
  let url = "";
  const fetchFn = (async (u: string) => {
    url = u;
    return { ok: true, status: 200, json: async () => ({
      global: { person_frames: 10, compliant_frames: 8, rate: 0.8 },
      by_zone: [], over_time: [], violations: { total: 0, by_zone: {} },
    }) } as Response;
  }) as typeof fetch;
  const s = await getStats({ zone: "Fonderie" }, fetchFn);
  expect(s.global.rate).toBe(0.8);
  expect(url).toContain("/stats?");
  expect(url).toContain("zone=Fonderie");
});
```

`frontend/lib/eventsApi.test.ts` :
```ts
import { getEvents, snapshotUrl } from "./eventsApi";

test("getEvents renvoie la liste et passe les filtres", async () => {
  let url = "";
  const fetchFn = (async (u: string) => {
    url = u;
    return { ok: true, status: 200, json: async () => ({
      events: [{ id: 1, ts: "t", stream_ts: 0, camera: "c", zone: "Z",
                 track_id: 3, missing: ["helmet"], snapshot: "a.jpg" }],
    }) } as Response;
  }) as typeof fetch;
  const ev = await getEvents({ ppe: "helmet", limit: 50 }, fetchFn);
  expect(ev).toHaveLength(1);
  expect(ev[0].snapshot).toBe("a.jpg");
  expect(url).toContain("ppe=helmet");
  expect(url).toContain("limit=50");
});

test("snapshotUrl construit l'URL du snapshot", () => {
  expect(snapshotUrl(7)).toContain("/events/7/snapshot");
});
```

- [ ] **Step 2: Lancer les tests** — `cd frontend && npx vitest run lib/statsApi.test.ts lib/eventsApi.test.ts` → FAIL.

- [ ] **Step 3: Écrire l'implémentation**

`frontend/lib/http.ts` :
```ts
export const API = process.env.NEXT_PUBLIC_ARGUS_API ?? "http://localhost:8000";

export function qs(params: Record<string, string | number | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}
```

`frontend/lib/statsApi.ts` :
```ts
import { API, qs } from "./http";

export type Rate = { person_frames: number; compliant_frames: number; rate: number | null };
export type ZoneStat = Rate & { zone: string };
export type Bucket = Rate & { bucket: string };
export type Stats = {
  global: Rate;
  by_zone: ZoneStat[];
  over_time: Bucket[];
  violations: { total: number; by_zone: Record<string, number> };
};

export async function getStats(
  params: { since?: string; until?: string; zone?: string } = {},
  fetchFn: typeof fetch = fetch,
): Promise<Stats> {
  const res = await fetchFn(`${API}/stats${qs(params)}`);
  if (!res.ok) throw new Error(`GET /stats -> ${res.status}`);
  return (await res.json()) as Stats;
}
```

`frontend/lib/eventsApi.ts` :
```ts
import { API, qs } from "./http";

export type ApiEvent = {
  id: number; ts: string; stream_ts: number; camera: string;
  zone: string | null; track_id: number; missing: string[]; snapshot: string | null;
};

export async function getEvents(
  params: { zone?: string; ppe?: string; since?: string; until?: string; limit?: number } = {},
  fetchFn: typeof fetch = fetch,
): Promise<ApiEvent[]> {
  const res = await fetchFn(`${API}/events${qs(params)}`);
  if (!res.ok) throw new Error(`GET /events -> ${res.status}`);
  const data = (await res.json()) as { events: ApiEvent[] };
  return data.events ?? [];
}

export function snapshotUrl(id: number): string {
  return `${API}/events/${id}/snapshot`;
}
```

- [ ] **Step 4: Lancer les tests** — PASS (3).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/http.ts frontend/lib/statsApi.ts frontend/lib/eventsApi.ts frontend/lib/statsApi.test.ts frontend/lib/eventsApi.test.ts
git commit -m "feat(frontend): stats & events REST clients"
```

---

### Task 2: Maths de charts — `lib/chart.ts`

**Files:**
- Create: `frontend/lib/chart.ts`
- Test: `frontend/lib/chart.test.ts`

**Interfaces:**
- Produces: `scaleY(rate, height) -> number` ; `barWidth(rate|null, maxW) -> number` ; `trendSegments(rates: (number|null)[], width, height) -> {x,y}[][]` (segments continus, saute les `null`).

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/lib/chart.test.ts`
```ts
import { scaleY, barWidth, trendSegments } from "./chart";

test("scaleY mappe rate 0..1 vers height..0", () => {
  expect(scaleY(1, 100)).toBe(0);
  expect(scaleY(0, 100)).toBe(100);
  expect(scaleY(0.5, 100)).toBe(50);
});

test("barWidth proportionnel, clampé, 0 si null", () => {
  expect(barWidth(0.5, 200)).toBe(100);
  expect(barWidth(null, 200)).toBe(0);
  expect(barWidth(2, 200)).toBe(200);
});

test("trendSegments coupe les segments sur les null", () => {
  const segs = trendSegments([0.5, null, 1, 1], 300, 100);
  expect(segs).toHaveLength(2);
  expect(segs[0]).toHaveLength(1);
  expect(segs[1]).toHaveLength(2);
});
```

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `frontend/lib/chart.ts`
```ts
export function scaleY(rate: number, height: number): number {
  const r = Math.max(0, Math.min(1, rate));
  return height - r * height;
}

export function barWidth(rate: number | null, maxW: number): number {
  if (rate === null) return 0;
  return Math.max(0, Math.min(1, rate)) * maxW;
}

export type TrendPoint = { x: number; y: number };

export function trendSegments(
  rates: (number | null)[], width: number, height: number,
): TrendPoint[][] {
  const n = rates.length;
  const segs: TrendPoint[][] = [];
  let cur: TrendPoint[] = [];
  rates.forEach((r, i) => {
    if (r === null) {
      if (cur.length) { segs.push(cur); cur = []; }
      return;
    }
    const x = n === 1 ? 0 : (i / (n - 1)) * width;
    cur.push({ x, y: scaleY(r, height) });
  });
  if (cur.length) segs.push(cur);
  return segs;
}
```

- [ ] **Step 4: Lancer le test** — PASS (3).

- [ ] **Step 5: Commit**
```bash
git add frontend/lib/chart.ts frontend/lib/chart.test.ts
git commit -m "feat(frontend): pure chart scaling helpers"
```

---

### Task 3: Charts SVG — `ConformityTrend` + `ZoneBreakdown`

**Files:**
- Create: `frontend/components/charts/ConformityTrend.tsx`, `frontend/components/charts/ZoneBreakdown.tsx`
- Test: `frontend/components/charts/ConformityTrend.test.tsx`, `frontend/components/charts/ZoneBreakdown.test.tsx`

**Interfaces:**
- Consumes: `trendSegments`/`barWidth` (T2), `Bucket`/`ZoneStat` (T1).
- Produces: `<ConformityTrend data={Bucket[]} />` ; `<ZoneBreakdown data={ZoneStat[]} />`.

- [ ] **Step 1: Écrire les tests qui échouent**

`frontend/components/charts/ConformityTrend.test.tsx` :
```tsx
import { render, screen } from "@testing-library/react";
import { ConformityTrend } from "./ConformityTrend";

const b = (bucket: string, rate: number | null) => ({ bucket, rate, person_frames: 1, compliant_frames: 0 });

test("ConformityTrend rend une polyline par segment continu", () => {
  const { container } = render(
    <ConformityTrend data={[b("14:30", 0.5), b("14:31", null), b("14:32", 1), b("14:33", 1)]} />);
  expect(container.querySelectorAll("polyline")).toHaveLength(2);
});

test("ConformityTrend affiche un vide sans données", () => {
  render(<ConformityTrend data={[]} />);
  expect(screen.getByText(/aucune donnée/i)).toBeInTheDocument();
});
```

`frontend/components/charts/ZoneBreakdown.test.tsx` :
```tsx
import { render, screen } from "@testing-library/react";
import { ZoneBreakdown } from "./ZoneBreakdown";

const z = (zone: string, rate: number | null) => ({ zone, rate, person_frames: 1, compliant_frames: 0 });

test("ZoneBreakdown rend une ligne par zone avec le pourcentage", () => {
  render(<ZoneBreakdown data={[z("Fonderie", 0.8), z("Bureau", 1)]} />);
  expect(screen.getByText("Fonderie")).toBeInTheDocument();
  expect(screen.getByText("80%")).toBeInTheDocument();
  expect(screen.getByText("100%")).toBeInTheDocument();
});
```

- [ ] **Step 2: Lancer les tests** — FAIL.

- [ ] **Step 3: Écrire l'implémentation**

`frontend/components/charts/ConformityTrend.tsx` :
```tsx
import { trendSegments } from "@/lib/chart";
import type { Bucket } from "@/lib/statsApi";

const W = 600;
const H = 120;

export function ConformityTrend({ data }: { data: Bucket[] }) {
  if (data.length === 0) {
    return <div className="grid h-[120px] place-items-center text-[12px] text-ink3">Aucune donnée</div>;
  }
  const segs = trendSegments(data.map((d) => d.rate), W, H);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-[120px] w-full"
         role="img" aria-label="Taux de conformité dans le temps">
      <line x1="0" y1={H} x2={W} y2={H} style={{ stroke: "var(--line)" }} />
      {segs.map((seg, i) => (
        <polyline key={i} fill="none" strokeWidth="2" style={{ stroke: "var(--ok)" }}
                  points={seg.map((p) => `${p.x},${p.y}`).join(" ")} />
      ))}
    </svg>
  );
}
```

`frontend/components/charts/ZoneBreakdown.tsx` :
```tsx
import { barWidth } from "@/lib/chart";
import type { ZoneStat } from "@/lib/statsApi";

function barColor(rate: number | null): string {
  if (rate === null) return "var(--slate)";
  if (rate >= 0.9) return "var(--ok)";
  if (rate >= 0.7) return "var(--warn)";
  return "var(--crit)";
}

export function ZoneBreakdown({ data }: { data: ZoneStat[] }) {
  if (data.length === 0) {
    return <div className="grid h-[80px] place-items-center text-[12px] text-ink3">Aucune zone</div>;
  }
  return (
    <div className="flex flex-col gap-2">
      {data.map((z) => (
        <div key={z.zone} className="grid grid-cols-[110px_1fr_46px] items-center gap-2 text-[12px]">
          <span className="truncate text-ink2">{z.zone}</span>
          <div className="h-3 rounded bg-s2">
            <div className="h-full rounded"
                 style={{ width: `${barWidth(z.rate, 100)}%`, background: barColor(z.rate) }} />
          </div>
          <span className="text-right font-mono tabnum text-ink2">
            {z.rate === null ? "—" : `${Math.round(z.rate * 100)}%`}
          </span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Lancer les tests** — PASS (4).

- [ ] **Step 5: Commit**
```bash
git add frontend/components/charts/
git commit -m "feat(frontend): SVG conformity trend + zone breakdown charts"
```

---

### Task 4: `JournalTable` + `DashboardFilters`

**Files:**
- Create: `frontend/components/dashboard/JournalTable.tsx`, `frontend/components/dashboard/DashboardFilters.tsx`
- Test: `frontend/components/dashboard/JournalTable.test.tsx`, `frontend/components/dashboard/DashboardFilters.test.tsx`

**Interfaces:**
- Consumes: `ApiEvent`/`snapshotUrl` (T1), `severityFor` (`lib/priority`), `riskOf` (`lib/zoneRisk`), `SeverityTag`, `PpeChip`.
- Produces: `<JournalTable events={ApiEvent[]} />` ; type `DashFilters = { zone: string; ppe: string; range: "hour"|"day"|"all" }` ; `<DashboardFilters filters onChange />`.

- [ ] **Step 1: Écrire les tests qui échouent**

`frontend/components/dashboard/JournalTable.test.tsx` :
```tsx
import { render, screen } from "@testing-library/react";
import { JournalTable } from "./JournalTable";
import type { ApiEvent } from "@/lib/eventsApi";

const ev = (over: Partial<ApiEvent>): ApiEvent => ({
  id: 1, ts: "2026-08-04T12:00:00+00:00", stream_ts: 0, camera: "cam-1",
  zone: "Fonderie", track_id: 37, missing: ["helmet"], snapshot: "a.jpg", ...over,
});

test("JournalTable rend une ligne par event avec vignette et sévérité", () => {
  render(<JournalTable events={[ev({})]} />);
  expect(screen.getByText("Fonderie")).toBeInTheDocument();
  expect(screen.getByText("#37")).toBeInTheDocument();
  const img = screen.getByRole("img", { name: /preuve/i });
  expect(img).toHaveAttribute("src", expect.stringContaining("/events/1/snapshot"));
});

test("JournalTable montre un tiret quand pas de snapshot", () => {
  render(<JournalTable events={[ev({ id: 2, snapshot: null })]} />);
  expect(screen.queryByRole("img", { name: /preuve/i })).toBeNull();
});
```

`frontend/components/dashboard/DashboardFilters.test.tsx` :
```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { DashboardFilters, type DashFilters } from "./DashboardFilters";

test("DashboardFilters remonte EPI et plage", () => {
  let last: DashFilters = { zone: "", ppe: "", range: "day" };
  render(<DashboardFilters filters={last} onChange={(f) => (last = f)} />);
  fireEvent.change(screen.getByLabelText(/epi/i), { target: { value: "helmet" } });
  expect(last.ppe).toBe("helmet");
  fireEvent.change(screen.getByLabelText(/période/i), { target: { value: "hour" } });
  expect(last.range).toBe("hour");
});
```

- [ ] **Step 2: Lancer les tests** — FAIL.

- [ ] **Step 3: Écrire l'implémentation**

`frontend/components/dashboard/JournalTable.tsx` :
```tsx
import { SeverityTag } from "@/components/ui/SeverityTag";
import { PpeChip } from "@/components/ui/PpeChip";
import { severityFor } from "@/lib/priority";
import { riskOf } from "@/lib/zoneRisk";
import { snapshotUrl, type ApiEvent } from "@/lib/eventsApi";

function clock(ts: string): string {
  const d = new Date(ts);
  return isNaN(d.getTime()) ? ts : d.toLocaleTimeString("fr-FR");
}

export function JournalTable({ events }: { events: ApiEvent[] }) {
  if (events.length === 0) {
    return <div className="grid place-items-center py-8 text-[12px] text-ink3">Aucune infraction</div>;
  }
  return (
    <table className="w-full border-collapse text-[12px]">
      <thead>
        <tr className="text-left text-ink3">
          {["Preuve", "Heure", "Zone", "Personne", "EPI manquants", "Sévérité"].map((h) => (
            <th key={h} className="px-2 py-1.5 font-semibold">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {events.map((e) => (
          <tr key={e.id} className="border-t border-line">
            <td className="px-2 py-1.5">
              {e.snapshot ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={snapshotUrl(e.id)} alt="preuve floutée"
                     className="h-9 w-14 rounded object-cover" />
              ) : (
                <span className="text-ink3">—</span>
              )}
            </td>
            <td className="px-2 py-1.5 font-mono tabnum text-ink2">{clock(e.ts)}</td>
            <td className="px-2 py-1.5 text-ink">{e.zone ?? "—"}</td>
            <td className="px-2 py-1.5 font-mono tabnum text-ink2">#{e.track_id}</td>
            <td className="px-2 py-1.5">
              <div className="flex flex-wrap gap-1">
                {e.missing.map((m) => <PpeChip key={m} label={m} />)}
              </div>
            </td>
            <td className="px-2 py-1.5">
              <SeverityTag severity={severityFor(riskOf(e.zone), e.missing)} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

`frontend/components/dashboard/DashboardFilters.tsx` :
```tsx
"use client";

export type DashFilters = { zone: string; ppe: string; range: "hour" | "day" | "all" };

const PPE = ["helmet", "safety-vest", "mask", "shoes"];
const RANGES: { v: DashFilters["range"]; l: string }[] = [
  { v: "hour", l: "Dernière heure" },
  { v: "day", l: "Dernier jour" },
  { v: "all", l: "Tout" },
];
const sel = "rounded-lg border border-line bg-s1 px-3 py-1.5 text-[13px] font-semibold text-ink2";

export function DashboardFilters({
  filters, onChange,
}: { filters: DashFilters; onChange: (f: DashFilters) => void }) {
  const set = (patch: Partial<DashFilters>) => onChange({ ...filters, ...patch });
  return (
    <div className="flex items-center gap-2.5">
      <input aria-label="Zone" value={filters.zone} placeholder="Zone…"
             onChange={(e) => set({ zone: e.target.value })}
             className="max-w-[200px] rounded-lg border border-line bg-s1 px-3 py-1.5 text-[13px] text-ink placeholder:text-ink3" />
      <select aria-label="EPI" className={sel} value={filters.ppe}
              onChange={(e) => set({ ppe: e.target.value })}>
        <option value="">Tous EPI</option>
        {PPE.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <select aria-label="Période" className={sel} value={filters.range}
              onChange={(e) => set({ range: e.target.value as DashFilters["range"] })}>
        {RANGES.map((r) => <option key={r.v} value={r.v}>{r.l}</option>)}
      </select>
    </div>
  );
}
```

- [ ] **Step 4: Lancer les tests** — PASS (4).

- [ ] **Step 5: Commit**
```bash
git add frontend/components/dashboard/JournalTable.tsx frontend/components/dashboard/DashboardFilters.tsx frontend/components/dashboard/JournalTable.test.tsx frontend/components/dashboard/DashboardFilters.test.tsx
git commit -m "feat(frontend): journal table + dashboard filters"
```

---

### Task 5: `KpiRow` + `Dashboard` (polling)

**Files:**
- Create: `frontend/components/dashboard/KpiRow.tsx`, `frontend/components/dashboard/Dashboard.tsx`
- Test: `frontend/components/dashboard/Dashboard.test.tsx`

**Interfaces:**
- Consumes: `getStats`/`getEvents` (T1), `KpiRow`, `ConformityTrend` (T3), `ZoneBreakdown` (T3), `JournalTable`/`DashboardFilters` (T4).
- Produces: `<KpiRow stats onLastUpdated />` ; `<Dashboard loadStats? loadEvents? />` (loaders injectables, défauts `getStats`/`getEvents`).

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/components/dashboard/Dashboard.test.tsx`
```tsx
import { render, screen } from "@testing-library/react";
import { Dashboard } from "./Dashboard";
import type { Stats } from "@/lib/statsApi";
import type { ApiEvent } from "@/lib/eventsApi";

const stats: Stats = {
  global: { person_frames: 10, compliant_frames: 9, rate: 0.9 },
  by_zone: [{ zone: "Fonderie", person_frames: 10, compliant_frames: 9, rate: 0.9 }],
  over_time: [{ bucket: "14:30", person_frames: 10, compliant_frames: 9, rate: 0.9 }],
  violations: { total: 2, by_zone: { Fonderie: 2 } },
};
const events: ApiEvent[] = [
  { id: 1, ts: "2026-08-04T12:00:00+00:00", stream_ts: 0, camera: "c",
    zone: "Fonderie", track_id: 37, missing: ["helmet"], snapshot: "a.jpg" },
];

test("Dashboard charge et affiche KPI + sections + journal", async () => {
  render(<Dashboard loadStats={async () => stats} loadEvents={async () => events} />);
  expect(await screen.findByText("90%")).toBeInTheDocument();            // KPI conformité globale
  expect(screen.getByText(/conformité dans le temps/i)).toBeInTheDocument();
  expect(screen.getByText(/conformité par zone/i)).toBeInTheDocument();
  expect(await screen.findByText("#37")).toBeInTheDocument();            // ligne journal
});
```

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation**

`frontend/components/dashboard/KpiRow.tsx` :
```tsx
import { MetricTile } from "@/components/ui/MetricTile";
import type { Stats } from "@/lib/statsApi";

function pct(rate: number | null): string {
  return rate === null ? "—" : `${Math.round(rate * 100)}%`;
}

export function KpiRow({ stats, lastUpdated }: { stats: Stats | null; lastUpdated: Date | null }) {
  const rate = stats ? stats.global.rate : null;
  const tone: "ok" | "warn" | "crit" | "default" =
    rate === null ? "default" : rate >= 0.9 ? "ok" : rate >= 0.7 ? "warn" : "crit";
  return (
    <div className="grid grid-cols-4 gap-2.5">
      <MetricTile label="Conformité globale" value={pct(rate)} tone={tone} />
      <MetricTile label="Infractions" value={String(stats?.violations.total ?? 0)} tone="warn" />
      <MetricTile label="Zones actives" value={String(stats?.by_zone.length ?? 0)} />
      <MetricTile label="Dernière MAJ"
                  value={lastUpdated ? lastUpdated.toLocaleTimeString("fr-FR") : "—"} />
    </div>
  );
}
```

`frontend/components/dashboard/Dashboard.tsx` :
```tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getStats, type Stats } from "@/lib/statsApi";
import { getEvents, type ApiEvent } from "@/lib/eventsApi";
import { KpiRow } from "./KpiRow";
import { ConformityTrend } from "@/components/charts/ConformityTrend";
import { ZoneBreakdown } from "@/components/charts/ZoneBreakdown";
import { JournalTable } from "./JournalTable";
import { DashboardFilters, type DashFilters } from "./DashboardFilters";

const REFRESH_MS = 15000;

function sinceFor(range: DashFilters["range"]): string | undefined {
  if (range === "all") return undefined;
  const ms = range === "hour" ? 3_600_000 : 86_400_000;
  return new Date(Date.now() - ms).toISOString();
}

export function Dashboard({
  loadStats = getStats,
  loadEvents = getEvents,
}: {
  loadStats?: typeof getStats;
  loadEvents?: typeof getEvents;
}) {
  const [filters, setFilters] = useState<DashFilters>({ zone: "", ppe: "", range: "day" });
  const [stats, setStats] = useState<Stats | null>(null);
  const [events, setEvents] = useState<ApiEvent[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const refresh = useCallback(async () => {
    const f = filtersRef.current;
    const since = sinceFor(f.range);
    const zone = f.zone || undefined;
    try {
      const [s, e] = await Promise.all([
        loadStats({ zone, since }),
        loadEvents({ zone, since, ppe: f.ppe || undefined, limit: 100 }),
      ]);
      setStats(s);
      setEvents(e);
      setLastUpdated(new Date());
    } catch {
      /* garde les dernières données */
    }
  }, [loadStats, loadEvents]);

  useEffect(() => { refresh(); }, [refresh, filters]);

  useEffect(() => {
    const id = setInterval(() => { if (!document.hidden) refresh(); }, REFRESH_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const h2 = "mb-2 text-[11px] font-bold uppercase tracking-[.12em] text-ink3";
  const card = "rounded-[10px] border border-line bg-s1 p-3";

  return (
    <div className="flex min-h-0 flex-col gap-3.5 overflow-y-auto p-3.5">
      <DashboardFilters filters={filters} onChange={setFilters} />
      <KpiRow stats={stats} lastUpdated={lastUpdated} />
      <div className="grid grid-cols-2 gap-3.5">
        <section className={card}>
          <h2 className={h2}>Conformité dans le temps</h2>
          <ConformityTrend data={stats?.over_time ?? []} />
        </section>
        <section className={card}>
          <h2 className={h2}>Conformité par zone</h2>
          <ZoneBreakdown data={stats?.by_zone ?? []} />
        </section>
      </div>
      <section className={card}>
        <div className="mb-2 flex items-center justify-between">
          <h2 className={h2 + " mb-0"}>Journal d'infractions</h2>
          <button disabled title="Rapports — P3-d"
                  className="cursor-not-allowed rounded-lg border border-line2 px-3 py-1.5 text-[12px] font-bold text-ink3 opacity-50">
            Exporter
          </button>
        </div>
        <JournalTable events={events} />
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Lancer le test** — PASS (1).

- [ ] **Step 5: Commit**
```bash
git add frontend/components/dashboard/KpiRow.tsx frontend/components/dashboard/Dashboard.tsx frontend/components/dashboard/Dashboard.test.tsx
git commit -m "feat(frontend): dashboard assembly with 15s polling"
```

---

### Task 6: Routing — NavRail navigante + `Shell` + route `/dashboard`

**Files:**
- Modify: `frontend/components/console/NavRail.tsx`, `frontend/app/page.tsx`, `frontend/vitest.setup.ts`
- Create: `frontend/components/console/Shell.tsx`, `frontend/app/dashboard/page.tsx`, `frontend/components/console/NavRail.test.tsx`

**Interfaces:**
- Consumes: `Dashboard` (T5), `VitalStrip`/`Workspace` (existants), `next/link`.
- Produces: `NavRail({ active: "live" | "analytique" })` (navigante) ; `<Shell active>{children}</Shell>` ; route `/dashboard`.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/components/console/NavRail.test.tsx`
```tsx
import { render, screen } from "@testing-library/react";
import { NavRail } from "./NavRail";

test("NavRail lie les routes et surligne l'item actif", () => {
  render(<NavRail active="analytique" />);
  const analytique = screen.getByTitle("Analytique");
  expect(analytique).toHaveAttribute("href", "/dashboard");
  expect(analytique).toHaveAttribute("aria-current", "page");
  expect(screen.getByTitle("Live")).toHaveAttribute("href", "/");
});
```

- [ ] **Step 2: Lancer le test** — FAIL (NavRail actuelle n'a pas de prop `active` ni de liens).

- [ ] **Step 3: Écrire l'implémentation**

(a) `frontend/vitest.setup.ts` — mocker `next/link` en `<a>` (déterministe, sans contexte routeur). Remplacer le contenu par :
```ts
import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";
import React from "react";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) =>
    React.createElement("a", { href, ...rest }, children),
}));
```

(b) `frontend/components/console/NavRail.tsx` — remplacer par :
```tsx
"use client";

import Link from "next/link";
import { Logo } from "@/components/ui/Logo";

type Item = { label: string; href?: string; key?: "live" | "analytique" };

const ITEMS: Item[] = [
  { label: "Live", href: "/", key: "live" },
  { label: "Alertes" },
  { label: "Zones" },
  { label: "Sites" },
  { label: "Analytique", href: "/dashboard", key: "analytique" },
];

export function NavRail({ active }: { active: "live" | "analytique" }) {
  return (
    <nav className="flex w-[60px] flex-col items-center gap-1 border-r border-line bg-[#090B0F] py-3">
      <div className="mb-3 grid h-[34px] w-[34px] place-items-center rounded-lg bg-gradient-to-br from-brand to-[#2560c9] text-white">
        <Logo size={20} color="#fff" />
      </div>
      {ITEMS.map((it) => {
        const isActive = it.key === active;
        const cls = `grid h-10 w-10 place-items-center rounded-[9px] text-[10px] ${
          isActive ? "bg-brand/15 text-brand" : "text-ink3 hover:bg-s2 hover:text-ink"
        }`;
        return it.href ? (
          <Link key={it.label} href={it.href} title={it.label}
                aria-current={isActive ? "page" : undefined} className={cls}>
            {it.label.slice(0, 2)}
          </Link>
        ) : (
          <button key={it.label} title={it.label} className={cls}>{it.label.slice(0, 2)}</button>
        );
      })}
    </nav>
  );
}
```

(c) `frontend/components/console/Shell.tsx` :
```tsx
import type { ReactNode } from "react";
import { NavRail } from "./NavRail";

export function Shell({
  active, children,
}: { active: "live" | "analytique"; children: ReactNode }) {
  return (
    <div className="grid h-dvh grid-cols-[60px_1fr]">
      <NavRail active={active} />
      <div className="grid min-h-0 min-w-0">{children}</div>
    </div>
  );
}
```

(d) `frontend/app/page.tsx` — remplacer par :
```tsx
import { Shell } from "@/components/console/Shell";
import { VitalStrip } from "@/components/console/VitalStrip";
import { Workspace } from "@/components/console/Workspace";

export default function Page() {
  return (
    <Shell active="live">
      <div className="grid min-h-0 grid-rows-[auto_1fr]">
        <VitalStrip />
        <Workspace />
      </div>
    </Shell>
  );
}
```

(e) `frontend/app/dashboard/page.tsx` :
```tsx
import { Shell } from "@/components/console/Shell";
import { Dashboard } from "@/components/dashboard/Dashboard";

export default function DashboardPage() {
  return (
    <Shell active="analytique">
      <Dashboard />
    </Shell>
  );
}
```

- [ ] **Step 4: Lancer les tests + build**

Run: `cd frontend && npm run test && npm run build`
Expected: tous verts (NavRail + suite existante, `console.test` inclus — la page monte toujours le logo, le bandeau vital et le bouton « Webcam ») ; build réussi (route `/dashboard` générée).

- [ ] **Step 5: Commit**
```bash
git add frontend/components/console/NavRail.tsx frontend/components/console/Shell.tsx frontend/app/page.tsx frontend/app/dashboard/page.tsx frontend/vitest.setup.ts frontend/components/console/NavRail.test.tsx
git commit -m "feat(frontend): navigable NavRail + shared Shell + /dashboard route"
```

---

## Self-Review

**1. Couverture spec (P2-b) :** clients `statsApi`/`eventsApi` ✅ (T1) ; charts SVG maison (courbe + barres) ✅ (T2, T3) ; journal filtrable avec vignette floutée + sévérité front ✅ (T4) ; KPI + polling 15 s + pause onglet caché ✅ (T5) ; route `/dashboard` + NavRail navigante + `Shell` partagé ✅ (T6) ; export = stub inerte ✅ (T5). Zéro dépendance ✅.

**2. Placeholders :** aucun — code complet (clients, maths, SVG, composants, route, tests). Le bouton export est explicitement inerte (P3-d).

**3. Cohérence des types :** `ApiEvent`/`Stats`/`Bucket`/`ZoneStat` (T1) consommés par charts (T3), `JournalTable`/`KpiRow` (T4, T5), `Dashboard` (T5). `DashFilters` (T4) produit par `DashboardFilters`, consommé par `Dashboard`. `severityFor(riskOf(zone), missing)` réutilise `lib/priority`+`lib/zoneRisk` (aucune signature nouvelle). `NavRail({active})` (T6) consommé par `Shell` (T6), lui-même par les deux pages. Le mock `next/link` (T6) rend un `<a href>` — cohérent avec l'assertion `toHaveAttribute("href", …)` de `NavRail.test` et neutre pour `console.test`.
```
