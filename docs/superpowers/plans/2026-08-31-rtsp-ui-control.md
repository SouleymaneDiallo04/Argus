# V1.5 — Contrôle RTSP depuis l'UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Piloter le flux RTSP (démarrer/arrêter/statut) depuis un bandeau en haut du dashboard.

**Architecture:** `sourcesApi` (client REST) + `RtspControl` (composant client avec polling) intégré au `Dashboard`. Frontend seul — backend déjà en place.

**Tech Stack:** Next.js 16 (client), TypeScript, Vitest. Zéro nouvelle dépendance.

## Global Constraints

- Pattern `zonesApi` : `API = NEXT_PUBLIC_ARGUS_API` (via `lib/http`), `fetchFn` injectable.
- Composant `"use client"` (fetch, `document`, `setInterval`). Loaders injectables pour les tests.
- Source unique (démarrer remplace). Réutiliser tokens du design system.
- Front : `npm run test` / `npm run build`. Suites existantes (**48**) vertes. Commits
  conventionnels, anglais, **sans `Co-Authored-By`**. Branche : `feat/rtsp-ui`.

---

### Task 1: Client REST `sourcesApi`

**Files:**
- Create: `frontend/lib/sourcesApi.ts`, `frontend/lib/sourcesApi.test.ts`

**Interfaces:**
- Produces: type `RtspStatus` ; `startRtsp(url, fetchFn?)`, `stopRtsp(fetchFn?)`, `rtspStatus(fetchFn?)`.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/lib/sourcesApi.test.ts`
```ts
import { startRtsp, stopRtsp, rtspStatus } from "./sourcesApi";

test("startRtsp poste l'URL", async () => {
  let url = ""; let init: RequestInit | undefined;
  const fetchFn = (async (u: string, i?: RequestInit) => {
    url = u; init = i;
    return { ok: true, status: 200, json: async () => ({ running: true, url: "rtsp://x", frames: 0 }) } as Response;
  }) as typeof fetch;
  const st = await startRtsp("rtsp://x", fetchFn);
  expect(url).toContain("/sources/rtsp");
  expect(init?.method).toBe("POST");
  expect(JSON.parse(init?.body as string)).toEqual({ url: "rtsp://x" });
  expect(st.running).toBe(true);
});

test("stopRtsp fait un DELETE", async () => {
  let method = "";
  const fetchFn = (async (_u: string, i?: RequestInit) => {
    method = i?.method ?? "GET";
    return { ok: true, status: 200, json: async () => ({}) } as Response;
  }) as typeof fetch;
  await stopRtsp(fetchFn);
  expect(method).toBe("DELETE");
});

test("rtspStatus parse le statut", async () => {
  const fetchFn = (async () => ({ ok: true, status: 200, json: async () => ({ running: false }) }) as Response) as typeof fetch;
  expect((await rtspStatus(fetchFn)).running).toBe(false);
});
```

- [ ] **Step 2: Lancer le test** — `cd frontend && npx vitest run lib/sourcesApi.test.ts` → FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `frontend/lib/sourcesApi.ts`
```ts
import { API } from "./http";

export type RtspStatus = {
  running: boolean; url?: string; frames?: number; error?: string | null;
};

export async function startRtsp(url: string, fetchFn: typeof fetch = fetch): Promise<RtspStatus> {
  const res = await fetchFn(`${API}/sources/rtsp`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(`POST /sources/rtsp -> ${res.status}`);
  return (await res.json()) as RtspStatus;
}

export async function stopRtsp(fetchFn: typeof fetch = fetch): Promise<void> {
  const res = await fetchFn(`${API}/sources/rtsp`, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE /sources/rtsp -> ${res.status}`);
}

export async function rtspStatus(fetchFn: typeof fetch = fetch): Promise<RtspStatus> {
  const res = await fetchFn(`${API}/sources/rtsp`);
  if (!res.ok) throw new Error(`GET /sources/rtsp -> ${res.status}`);
  return (await res.json()) as RtspStatus;
}
```

- [ ] **Step 4: Lancer le test** — PASS (3).

- [ ] **Step 5: Commit**
```bash
git add frontend/lib/sourcesApi.ts frontend/lib/sourcesApi.test.ts
git commit -m "feat(frontend): RTSP sources REST client"
```

---

### Task 2: Composant `RtspControl`

**Files:**
- Create: `frontend/components/dashboard/RtspControl.tsx`, `frontend/components/dashboard/RtspControl.test.tsx`

**Interfaces:**
- Consumes: `sourcesApi` (T1).
- Produces: `RtspControl({ loadStatus?, doStart?, doStop? })`.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/components/dashboard/RtspControl.test.tsx`
```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RtspControl } from "./RtspControl";
import type { RtspStatus } from "@/lib/sourcesApi";

test("RtspControl affiche le champ et démarre le flux", async () => {
  let started = "";
  const doStart = async (url: string) => { started = url; return { running: true, url } as RtspStatus; };
  render(<RtspControl loadStatus={async () => ({ running: false })}
                      doStart={doStart} doStop={async () => {}} />);
  const input = await screen.findByLabelText(/url rtsp/i);
  fireEvent.change(input, { target: { value: "rtsp://cam" } });
  fireEvent.click(screen.getByRole("button", { name: /démarrer/i }));
  await waitFor(() => expect(started).toBe("rtsp://cam"));
});

test("RtspControl affiche 'En cours' et le bouton Arrêter quand actif", async () => {
  render(<RtspControl loadStatus={async () => ({ running: true, url: "rtsp://cam", frames: 12 })}
                      doStart={async () => ({ running: true })} doStop={async () => {}} />);
  expect(await screen.findByText(/en cours/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /arrêter/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Lancer le test** — `cd frontend && npx vitest run components/dashboard/RtspControl.test.tsx` → FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `frontend/components/dashboard/RtspControl.tsx`
```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { startRtsp, stopRtsp, rtspStatus, type RtspStatus } from "@/lib/sourcesApi";

const POLL_MS = 5000;

export function RtspControl({
  loadStatus = rtspStatus, doStart = startRtsp, doStop = stopRtsp,
}: {
  loadStatus?: typeof rtspStatus; doStart?: typeof startRtsp; doStop?: typeof stopRtsp;
}) {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<RtspStatus>({ running: false });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setStatus(await loadStatus()); } catch { /* garde le dernier statut */ }
  }, [loadStatus]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = setInterval(() => { if (!document.hidden) load(); }, POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  async function start() {
    if (!url.trim()) return;
    setBusy(true);
    try { setStatus(await doStart(url.trim())); } catch { /* ignore */ } finally { setBusy(false); }
  }
  async function stop() {
    setBusy(true);
    try { await doStop(); } catch { /* ignore */ } finally { setBusy(false); await load(); }
  }

  const btn = "rounded-lg px-3 py-1.5 text-[12px] font-bold";
  return (
    <div className="flex items-center gap-2.5 rounded-[10px] border border-line bg-s1 px-3 py-2">
      <span className="text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">Source RTSP</span>
      <input aria-label="URL RTSP" value={url} placeholder="rtsp://caméra/flux"
             onChange={(e) => setUrl(e.target.value)}
             className="min-w-0 flex-1 rounded-lg border border-line bg-s2 px-3 py-1.5 text-[13px] text-ink placeholder:text-ink3" />
      {status.running ? (
        <button onClick={stop} disabled={busy} className={`${btn} border border-line2 text-ink hover:bg-s2`}>Arrêter</button>
      ) : (
        <button onClick={start} disabled={busy} className={`${btn} bg-brand text-white disabled:opacity-40`}>Démarrer</button>
      )}
      <span className="flex items-center gap-1.5 text-[12px] text-ink2">
        <span className={`h-1.5 w-1.5 rounded-full ${status.running ? "bg-ok" : "bg-slate"}`} />
        {status.running
          ? `En cours · ${status.frames ?? 0} frames`
          : "Arrêté"}
      </span>
      {status.error ? <span className="text-[12px] text-crit">{status.error}</span> : null}
    </div>
  );
}
```

- [ ] **Step 4: Lancer le test** — PASS (2).

- [ ] **Step 5: Commit**
```bash
git add frontend/components/dashboard/RtspControl.tsx frontend/components/dashboard/RtspControl.test.tsx
git commit -m "feat(frontend): RtspControl — start/stop/status widget"
```

---

### Task 3: Intégration au `Dashboard`

**Files:**
- Modify: `frontend/components/dashboard/Dashboard.tsx`

- [ ] **Step 1: Ajouter le composant** — `frontend/components/dashboard/Dashboard.tsx`

Ajouter l'import :
```tsx
import { RtspControl } from "./RtspControl";
```
Insérer `<RtspControl />` en tête du conteneur, avant `<DashboardFilters …>` :
```tsx
    <div className="flex min-h-0 flex-col gap-3.5 overflow-y-auto p-3.5">
      <RtspControl />
      <DashboardFilters filters={filters} onChange={setFilters} />
```

- [ ] **Step 2: Lancer les tests + build**
Run: `cd frontend && npm run test && npm run build`
Expected: tous verts (le `Dashboard.test` monte `RtspControl` qui appelle `rtspStatus` via le
vrai `fetch` — avalé par le `try/catch`, aucun impact sur les assertions) ; build OK.

- [ ] **Step 3: Commit**
```bash
git add frontend/components/dashboard/Dashboard.tsx
git commit -m "feat(frontend): mount RTSP control in the dashboard"
```

---

## Self-Review

**1. Couverture spec :** `sourcesApi` (start/stop/status) ✅ (T1) ; `RtspControl` (champ +
Démarrer/Arrêter + statut + polling) ✅ (T2) ; intégration dashboard ✅ (T3). Zéro dépendance ✅.

**2. Placeholders :** aucun — client, composant, intégration, tests complets.

**3. Cohérence des types :** `RtspStatus` (T1) consommé par `RtspControl` (T2) ; loaders
injectables (`loadStatus`/`doStart`/`doStop`) avec défauts `rtspStatus`/`startRtsp`/`stopRtsp`
(T1). `RtspControl` monté sans props dans le `Dashboard` (T3) → utilise les défauts (vrai
`fetch`). Note : `Dashboard.test` déclenche `rtspStatus()` réel, avalé par le `try/catch` du
`load` — pas d'assertion impactée.
```
