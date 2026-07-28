# P2-a.2 — Pipeline live (vidéo → WS → overlays + roster + alertes) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre la console vivante : capter une source vidéo (webcam ou fichier), échantillonner les frames vers le WebSocket P1b, et afficher en direct les overlays de détection, le roster de conformité et la file d'alertes priorisée.

**Architecture:** Logique pure testable (types, priorisation, dérivation d'état live, géométrie d'overlay, client WS) + composants clients (`"use client"`) pour la vidéo/canvas/hook. Les fondations P2-a.1 (design system, composants, shell) sont réutilisées.

**Tech Stack:** Next.js 16 (App Router, composants clients), TypeScript, Canvas 2D, WebSocket natif, Vitest + Testing Library.

## Global Constraints

- **Fondations P2-a.1 = acquises** (branche partant de `main` post-PR #5) : tokens, `Severity`, `SeverityTag`, `AlertRow`, `AlertsPanel`, `MetricTile`, etc. Réutiliser, ne pas dupliquer.
- **Contrat WS P1b** (inchangé) : envoi `{ frame: <base64 jpeg>, timestamp: <number> }` → réception `{ detections:[{cls,bbox:[x1,y1,x2,y2],confidence,track_id}], results:[{track_id,zone,required,present,missing,compliant}], events:[{track_id,zone,missing,timestamp,camera}] }`. La frame envoyée est **le base64 seul** (sans préfixe `data:`).
- **Priorisation = concern front** : sévérité = f(risque de zone, EPI manquant). Le risque de zone vit côté front (défaut par nom de zone) — aucun changement backend.
- **Composants navigateur** (`video`, `canvas`, `getUserMedia`, `WebSocket`, hooks) → directive `"use client"` en tête de fichier. La logique pure reste hors React (testable en jsdom).
- **Tests** : Vitest + Testing Library ; logique pure en TDD ; le client WS testé avec un **faux WebSocket injecté** (pas de vrai backend). Canvas/`getUserMedia` non testés en unité (jsdom limité) — garder ces couches minces.
- URL du service : `NEXT_PUBLIC_ARGUS_WS` (défaut `ws://localhost:8000/ws/stream`), `NEXT_PUBLIC_ARGUS_API` (défaut `http://localhost:8000`).
- Commits : préfixe conventionnel, anglais, **sans `Co-Authored-By`**. Lancer les tests via `npm run test` (ou `npx vitest run <file>`) depuis `frontend/`.

---

### Task 1: Types WS + priorisation

**Files:**
- Modify: `frontend/lib/types.ts`
- Create: `frontend/lib/priority.ts`
- Test: `frontend/lib/priority.test.ts`

**Interfaces:**
- Produces: types `Detection`, `ComplianceResult`, `ViolationEvent`, `FrameResponse`, `FrameMessage` ; type `ZoneRisk = "high" | "medium" | "low"` ; `severityFor(risk, missing) -> Severity`.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/lib/priority.test.ts`

```ts
import { severityFor } from "./priority";

test("casque manquant en zone à haut risque = critique", () => {
  expect(severityFor("high", ["casque"])).toBe("crit");
});
test("gilet en zone à haut risque = élevé", () => {
  expect(severityFor("high", ["gilet"])).toBe("high");
});
test("masque en zone bureau (faible) = faible", () => {
  expect(severityFor("low", ["masque"])).toBe("low");
});
test("casque en zone à risque moyen = élevé", () => {
  expect(severityFor("medium", ["casque"])).toBe("high");
});
test("prend le pire EPI manquant", () => {
  expect(severityFor("high", ["masque", "casque"])).toBe("crit");
});
```

- [ ] **Step 2: Lancer le test** — `cd frontend && npx vitest run lib/priority.test.ts` → FAIL (module absent).

- [ ] **Step 3: Écrire l'implémentation**

Ajouter à `frontend/lib/types.ts` (après le type `Alert` existant) :
```ts
export type Detection = {
  cls: string;
  bbox: [number, number, number, number];
  confidence: number;
  track_id: number | null;
};
export type ComplianceResult = {
  track_id: number | null;
  zone: string | null;
  required: string[];
  present: string[];
  missing: string[];
  compliant: boolean;
};
export type ViolationEvent = {
  track_id: number | null;
  zone: string | null;
  missing: string[];
  timestamp: number;
  camera: string;
};
export type FrameResponse = {
  detections: Detection[];
  results: ComplianceResult[];
  events: ViolationEvent[];
};
export type FrameMessage = { frame: string; timestamp: number };
```

`frontend/lib/priority.ts` :
```ts
import type { Severity } from "@/components/ui/severity";

export type ZoneRisk = "high" | "medium" | "low";

// Poids par EPI : casque le plus critique, masque le moins.
const PPE_WEIGHT: Record<string, number> = {
  casque: 3, helmet: 3,
  gilet: 2, "safety-vest": 2, shoes: 2,
  masque: 1, mask: 1,
};
const RISK_WEIGHT: Record<ZoneRisk, number> = { high: 3, medium: 2, low: 1 };

export function severityFor(risk: ZoneRisk, missing: string[]): Severity {
  const worstPpe = missing.reduce((m, p) => Math.max(m, PPE_WEIGHT[p] ?? 1), 0);
  const score = RISK_WEIGHT[risk] * worstPpe;
  if (score >= 8) return "crit";
  if (score >= 5) return "high";
  if (score >= 3) return "med";
  return "low";
}
```

- [ ] **Step 4: Lancer le test** — `npx vitest run lib/priority.test.ts` → PASS (5).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/priority.ts frontend/lib/priority.test.ts
git commit -m "feat(frontend): WS types + zone-risk x PPE severity prioritization"
```

---

### Task 2: Dérivation d'état live (roster + alertes)

**Files:**
- Create: `frontend/lib/live.ts`
- Test: `frontend/lib/live.test.ts`

**Interfaces:**
- Consumes: `ComplianceResult`, `ViolationEvent`, `Alert` (types) ; `severityFor`, `ZoneRisk` (Task 1).
- Produces: type `RosterEntry` ; `rosterFromResults(results) -> RosterEntry[]` ; `alertFromEvent(ev, riskOf) -> Alert` ; `formatClock(seconds) -> "mm:ss"`.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/lib/live.test.ts`

```ts
import { rosterFromResults, alertFromEvent, formatClock } from "./live";
import type { ComplianceResult, ViolationEvent } from "@/lib/types";

test("formatClock formate en mm:ss", () => {
  expect(formatClock(0)).toBe("00:00");
  expect(formatClock(75.4)).toBe("01:15");
});

test("rosterFromResults ne garde que les personnes suivies", () => {
  const results: ComplianceResult[] = [
    { track_id: 7, zone: "z", required: ["casque"], present: [], missing: ["casque"], compliant: false },
    { track_id: null, zone: null, required: [], present: [], missing: [], compliant: true },
  ];
  const roster = rosterFromResults(results);
  expect(roster).toHaveLength(1);
  expect(roster[0]).toMatchObject({ trackId: 7, compliant: false, missing: ["casque"] });
});

test("alertFromEvent applique le risque de zone à la sévérité", () => {
  const ev: ViolationEvent = { track_id: 37, zone: "Fonderie", missing: ["casque"], timestamp: 12, camera: "cam-1" };
  const alert = alertFromEvent(ev, () => "high");
  expect(alert.severity).toBe("crit");
  expect(alert.personId).toBe("#37");
  expect(alert.time).toBe("00:12");
  expect(alert.zone).toBe("Fonderie");
  expect(alert.missing).toEqual(["casque"]);
  expect(alert.status).toBe("active");
});
```

- [ ] **Step 2: Lancer le test** — `npx vitest run lib/live.test.ts` → FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `frontend/lib/live.ts`

```ts
import type { Alert, ComplianceResult, ViolationEvent } from "@/lib/types";
import { severityFor, ZoneRisk } from "./priority";

export type RosterEntry = {
  trackId: number;
  zone: string | null;
  missing: string[];
  compliant: boolean;
};

export function formatClock(seconds: number): string {
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function rosterFromResults(results: ComplianceResult[]): RosterEntry[] {
  return results
    .filter((r): r is ComplianceResult & { track_id: number } => r.track_id != null)
    .map((r) => ({ trackId: r.track_id, zone: r.zone, missing: r.missing, compliant: r.compliant }));
}

export function alertFromEvent(ev: ViolationEvent, riskOf: (zone: string | null) => ZoneRisk): Alert {
  return {
    id: `${ev.track_id}-${ev.timestamp}`,
    severity: severityFor(riskOf(ev.zone), ev.missing),
    time: formatClock(ev.timestamp),
    zone: ev.zone ?? "—",
    personId: `#${ev.track_id}`,
    missing: ev.missing,
    status: "active",
  };
}
```

- [ ] **Step 4: Lancer le test** — PASS (3).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/live.ts frontend/lib/live.test.ts
git commit -m "feat(frontend): live-state derivation (roster + alerts from WS payload)"
```

---

### Task 3: Géométrie & couleur des overlays

**Files:**
- Create: `frontend/lib/overlay.ts`
- Test: `frontend/lib/overlay.test.ts`

**Interfaces:**
- Consumes: `Detection`, `ComplianceResult`.
- Produces: type `Box` ; `detectionsToBoxes(detections, results, scaleX, scaleY) -> Box[]` (personne verte si conforme / rouge sinon, EPI ambre ; coords mises à l'échelle).

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/lib/overlay.test.ts`

```ts
import { detectionsToBoxes } from "./overlay";
import type { Detection, ComplianceResult } from "@/lib/types";

const person = (id: number): Detection => ({ cls: "person", bbox: [10, 20, 30, 60], confidence: 0.9, track_id: id });

test("met la boîte à l'échelle et colore une personne non conforme en rouge", () => {
  const results: ComplianceResult[] = [
    { track_id: 1, zone: "z", required: ["casque"], present: [], missing: ["casque"], compliant: false },
  ];
  const [box] = detectionsToBoxes([person(1)], results, 2, 3);
  expect(box).toMatchObject({ x: 20, y: 60, w: 40, h: 120 });
  expect(box.color).toBe("#F0464B");
  expect(box.label).toBe("#1");
});

test("personne conforme en vert, EPI en ambre", () => {
  const results: ComplianceResult[] = [
    { track_id: 2, zone: "z", required: [], present: [], missing: [], compliant: true },
  ];
  const dets: Detection[] = [person(2), { cls: "casque", bbox: [12, 22, 20, 30], confidence: 0.8, track_id: null }];
  const boxes = detectionsToBoxes(dets, results, 1, 1);
  expect(boxes[0].color).toBe("#31C46F");
  expect(boxes[1].color).toBe("#c9a227");
  expect(boxes[1].label).toBe("casque");
});
```

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `frontend/lib/overlay.ts`

```ts
import type { ComplianceResult, Detection } from "@/lib/types";

export type Box = { x: number; y: number; w: number; h: number; color: string; label: string };

const COLOR = { ok: "#31C46F", bad: "#F0464B", ppe: "#c9a227" };

export function detectionsToBoxes(
  detections: Detection[],
  results: ComplianceResult[],
  scaleX: number,
  scaleY: number
): Box[] {
  const compliantById = new Map<number, boolean>();
  for (const r of results) if (r.track_id != null) compliantById.set(r.track_id, r.compliant);

  return detections.map((d) => {
    const [x1, y1, x2, y2] = d.bbox;
    const isPerson = d.cls === "person";
    let color = COLOR.ppe;
    if (isPerson) {
      const compliant = d.track_id != null ? compliantById.get(d.track_id) : undefined;
      color = compliant === false ? COLOR.bad : COLOR.ok;
    }
    return {
      x: x1 * scaleX,
      y: y1 * scaleY,
      w: (x2 - x1) * scaleX,
      h: (y2 - y1) * scaleY,
      color,
      label: isPerson ? `#${d.track_id ?? "?"}` : d.cls,
    };
  });
}
```

- [ ] **Step 4: Lancer le test** — PASS (2).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/overlay.ts frontend/lib/overlay.test.ts
git commit -m "feat(frontend): overlay geometry + compliance colors"
```

---

### Task 4: Client WebSocket (testable)

**Files:**
- Create: `frontend/lib/streamClient.ts`
- Test: `frontend/lib/streamClient.test.ts`

**Interfaces:**
- Consumes: `FrameResponse`.
- Produces: `class StreamClient(url, handlers, factory?)` avec `.connect()`, `.send(frame, timestamp)`, `.close()`. `factory` (défaut `new WebSocket(url)`) est injectable pour les tests.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/lib/streamClient.test.ts`

```ts
import { StreamClient } from "./streamClient";

class FakeWS {
  static instances: FakeWS[] = [];
  readyState = 1; // OPEN
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  constructor(public url: string) { FakeWS.instances.push(this); }
  send(s: string) { this.sent.push(s); }
  close() { this.readyState = 3; this.onclose?.(); }
  emit(data: unknown) { this.onmessage?.({ data: JSON.stringify(data) }); }
}

test("send sérialise frame+timestamp quand la socket est ouverte", () => {
  let fake!: FakeWS;
  const c = new StreamClient("ws://x", { onMessage: () => {} }, (u) => (fake = new FakeWS(u)) as unknown as WebSocket);
  c.connect();
  c.send("BASE64", 1.5);
  expect(JSON.parse(fake.sent[0])).toEqual({ frame: "BASE64", timestamp: 1.5 });
});

test("onMessage reçoit un FrameResponse et ignore les {error}", () => {
  let fake!: FakeWS;
  const received: unknown[] = [];
  const c = new StreamClient("ws://x", { onMessage: (r) => received.push(r) }, (u) => (fake = new FakeWS(u)) as unknown as WebSocket);
  c.connect();
  fake.emit({ error: "frame illisible" });
  fake.emit({ detections: [], results: [], events: [] });
  expect(received).toHaveLength(1);
  expect(received[0]).toEqual({ detections: [], results: [], events: [] });
});
```

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `frontend/lib/streamClient.ts`

```ts
import type { FrameResponse } from "@/lib/types";

type Handlers = {
  onMessage: (r: FrameResponse) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (e: unknown) => void;
};
type WSFactory = (url: string) => WebSocket;

export class StreamClient {
  private ws: WebSocket | null = null;

  constructor(
    private url: string,
    private handlers: Handlers,
    private factory: WSFactory = (u) => new WebSocket(u)
  ) {}

  connect() {
    const ws = this.factory(this.url);
    this.ws = ws;
    ws.onopen = () => this.handlers.onOpen?.();
    ws.onclose = () => this.handlers.onClose?.();
    ws.onerror = (e) => this.handlers.onError?.(e);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data as string);
        if (data && typeof data === "object" && "detections" in data) {
          this.handlers.onMessage(data as FrameResponse);
        }
      } catch {
        /* trame non-JSON : ignorée */
      }
    };
  }

  send(frame: string, timestamp: number) {
    if (this.ws && this.ws.readyState === 1 /* OPEN */) {
      this.ws.send(JSON.stringify({ frame, timestamp }));
    }
  }

  close() {
    this.ws?.close();
    this.ws = null;
  }
}
```

- [ ] **Step 4: Lancer le test** — PASS (2).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/streamClient.ts frontend/lib/streamClient.test.ts
git commit -m "feat(frontend): injectable WebSocket stream client"
```

---

### Task 5: Sampler de frames + hook useLiveStream

**Files:**
- Create: `frontend/lib/sampler.ts`, `frontend/hooks/useLiveStream.ts`
- Test: `frontend/hooks/useLiveStream.test.tsx`

**Interfaces:**
- Consumes: `StreamClient` (Task 4), `FrameResponse`.
- Produces: `grabFrame(video, canvas, quality?) -> string | null` (base64 sans préfixe) ; hook `useLiveStream()` → `{ status, response, sendFrame(video, canvas) }` (client).

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/hooks/useLiveStream.test.tsx`

```tsx
import { renderHook, act } from "@testing-library/react";
import { useLiveStream } from "./useLiveStream";

// jsdom n'a pas WebSocket : on en fournit un faux global inerte.
beforeAll(() => {
  // @ts-expect-error test shim
  globalThis.WebSocket = class {
    readyState = 0;
    onopen: (() => void) | null = null;
    onclose: (() => void) | null = null;
    onerror: (() => void) | null = null;
    onmessage: (() => void) | null = null;
    send() {}
    close() {}
  };
});

test("useLiveStream démarre en 'connecting' et expose une API", () => {
  const { result } = renderHook(() => useLiveStream());
  expect(result.current.status).toBe("connecting");
  expect(typeof result.current.sendFrame).toBe("function");
  act(() => result.current.stop());
});
```

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation**

`frontend/lib/sampler.ts` :
```ts
// Dessine la frame courante de la vidéo sur un canvas et renvoie le JPEG base64 (sans préfixe data:).
export function grabFrame(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  quality = 0.6
): string | null {
  const w = video.videoWidth;
  const h = video.videoHeight;
  if (!w || !h) return null;
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(video, 0, 0, w, h);
  const url = canvas.toDataURL("image/jpeg", quality);
  return url.split(",")[1] ?? null;
}
```

`frontend/hooks/useLiveStream.ts` :
```ts
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { StreamClient } from "@/lib/streamClient";
import { grabFrame } from "@/lib/sampler";
import type { FrameResponse } from "@/lib/types";

const WS_URL = process.env.NEXT_PUBLIC_ARGUS_WS ?? "ws://localhost:8000/ws/stream";

export type StreamStatus = "connecting" | "open" | "closed";

export function useLiveStream() {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const [response, setResponse] = useState<FrameResponse | null>(null);
  const clientRef = useRef<StreamClient | null>(null);
  const startRef = useRef<number>(Date.now());

  useEffect(() => {
    const client = new StreamClient(WS_URL, {
      onMessage: setResponse,
      onOpen: () => setStatus("open"),
      onClose: () => setStatus("closed"),
      onError: () => setStatus("closed"),
    });
    clientRef.current = client;
    client.connect();
    return () => client.close();
  }, []);

  const sendFrame = useCallback((video: HTMLVideoElement, canvas: HTMLCanvasElement) => {
    const frame = grabFrame(video, canvas);
    if (frame) clientRef.current?.send(frame, (Date.now() - startRef.current) / 1000);
  }, []);

  const stop = useCallback(() => clientRef.current?.close(), []);

  return { status, response, sendFrame, stop };
}
```

- [ ] **Step 4: Lancer le test** — PASS (1).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/sampler.ts frontend/hooks/useLiveStream.ts frontend/hooks/useLiveStream.test.tsx
git commit -m "feat(frontend): frame sampler + useLiveStream hook"
```

---

### Task 6: VideoStage + Roster + Workspace (câblage live dans la console)

**Files:**
- Create: `frontend/components/console/Roster.tsx`, `frontend/components/console/VideoStage.tsx`, `frontend/components/console/Workspace.tsx`, `frontend/lib/zoneRisk.ts`
- Modify: `frontend/app/page.tsx`
- Test: `frontend/components/console/Roster.test.tsx`

**Interfaces:**
- Consumes: `useLiveStream` (Task 5), `detectionsToBoxes` (Task 3), `rosterFromResults`/`alertFromEvent` (Task 2), `AlertsPanel`/`MetricTile`/`PpeChip`/`StatusBadge` (P2-a.1).
- Produces: `riskOf(zone) -> ZoneRisk` (défaut par nom) ; `<Roster entries>` ; `<VideoStage>` (source + overlays, client) ; `<Workspace>` (état live, client).

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/components/console/Roster.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { Roster } from "./Roster";

test("Roster affiche l'ID, le statut et les EPI manquants", () => {
  render(
    <Roster
      entries={[
        { trackId: 8, zone: "z", missing: [], compliant: true },
        { trackId: 37, zone: "z", missing: ["casque", "shoes"], compliant: false },
      ]}
    />
  );
  expect(screen.getByText("#08")).toBeInTheDocument();
  expect(screen.getByText("#37")).toBeInTheDocument();
  expect(screen.getByText("casque")).toBeInTheDocument();
  expect(screen.getAllByText(/conforme|✓/i).length).toBeGreaterThan(0);
});
```

- [ ] **Step 2: Lancer le test** — FAIL.

- [ ] **Step 3: Écrire l'implémentation**

`frontend/lib/zoneRisk.ts` :
```ts
import type { ZoneRisk } from "./priority";

// V1 : risque déduit du nom de zone (réglable dans l'éditeur de zones en P2-a.3).
const HIGH = ["fonderie", "coulée", "cariste", "presse"];
const LOW = ["bureau", "mezzanine", "accueil"];

export function riskOf(zone: string | null): ZoneRisk {
  const z = (zone ?? "").toLowerCase();
  if (HIGH.some((k) => z.includes(k))) return "high";
  if (LOW.some((k) => z.includes(k))) return "low";
  return "medium";
}
```

`frontend/components/console/Roster.tsx` :
```tsx
import type { RosterEntry } from "@/lib/live";
import { PpeChip } from "@/components/ui/PpeChip";

export function Roster({ entries }: { entries: RosterEntry[] }) {
  return (
    <div className="flex min-h-0 flex-col rounded-[10px] border border-line bg-s1">
      <div className="flex items-center gap-2.5 border-b border-line px-3.5 py-2.5">
        <h2 className="text-[14px] font-bold">Conformité · en direct</h2>
        <span className="rounded-full bg-s2 px-2 py-0.5 font-mono text-[11px] font-bold text-ink3 tabnum">
          {entries.length} suivis
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-1.5">
        {entries.length === 0 ? (
          <div className="grid place-items-center py-10 text-[13px] text-ink3">Aucune personne détectée</div>
        ) : (
          entries.map((e) => (
            <div key={e.trackId} className="flex items-center gap-3 rounded-md px-2.5 py-2 hover:bg-s2">
              <span className="w-11 flex-none rounded-md border border-line bg-s2 py-1 text-center font-mono text-[13px] font-bold text-ink2 tabnum">
                #{String(e.trackId).padStart(2, "0")}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold">Personne {e.trackId}</div>
                {e.missing.length > 0 ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {e.missing.map((m) => <PpeChip key={m} label={m} />)}
                  </div>
                ) : null}
              </div>
              <span
                className={`flex-none rounded-full px-2.5 py-1 text-[11px] font-bold ${
                  e.compliant ? "bg-ok/15 text-ok" : "bg-crit/15 text-crit"
                }`}
              >
                {e.compliant ? "✓ conforme" : `✗ ${e.missing.length}`}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

`frontend/components/console/VideoStage.tsx` :
```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { detectionsToBoxes } from "@/lib/overlay";
import type { FrameResponse } from "@/lib/types";

export function VideoStage({
  response,
  onFrame,
}: {
  response: FrameResponse | null;
  onFrame: (video: HTMLVideoElement, canvas: HTMLCanvasElement) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const sampleCanvas = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const [source, setSource] = useState<"none" | "webcam" | "file">("none");

  // échantillonnage périodique (~7 i/s) tant qu'une source joue
  useEffect(() => {
    if (source === "none") return;
    const id = setInterval(() => {
      const v = videoRef.current, c = sampleCanvas.current;
      if (v && c && v.readyState >= 2) onFrame(v, c);
    }, 140);
    return () => clearInterval(id);
  }, [source, onFrame]);

  // dessin des overlays à chaque réponse
  useEffect(() => {
    const v = videoRef.current, o = overlayRef.current;
    if (!v || !o || !response) return;
    o.width = v.clientWidth;
    o.height = v.clientHeight;
    const ctx = o.getContext("2d");
    if (!ctx || !v.videoWidth) return;
    ctx.clearRect(0, 0, o.width, o.height);
    const boxes = detectionsToBoxes(response.detections, response.results, o.width / v.videoWidth, o.height / v.videoHeight);
    ctx.lineWidth = 2;
    ctx.font = "12px ui-monospace, monospace";
    for (const b of boxes) {
      ctx.strokeStyle = b.color;
      ctx.strokeRect(b.x, b.y, b.w, b.h);
      ctx.fillStyle = b.color;
      ctx.fillRect(b.x, b.y - 15, ctx.measureText(b.label).width + 10, 15);
      ctx.fillStyle = "#04140c";
      ctx.fillText(b.label, b.x + 5, b.y - 4);
    }
  }, [response]);

  async function useWebcam() {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setSource("webcam");
    }
  }
  function useFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file && videoRef.current) {
      videoRef.current.srcObject = null;
      videoRef.current.src = URL.createObjectURL(file);
      videoRef.current.play();
      setSource("file");
    }
  }

  return (
    <div className="relative flex-1 overflow-hidden rounded-[10px] border border-line2 bg-[#06080d]">
      <video ref={videoRef} className="h-full w-full object-contain" muted playsInline />
      <canvas ref={overlayRef} className="pointer-events-none absolute inset-0 h-full w-full" />
      <canvas ref={sampleCanvas} className="hidden" />
      {source === "none" ? (
        <div className="absolute inset-0 grid place-items-center gap-3">
          <div className="flex gap-2.5">
            <button onClick={useWebcam} className="rounded-lg bg-brand px-4 py-2 text-[13px] font-bold text-white">
              Webcam
            </button>
            <label className="cursor-pointer rounded-lg border border-line2 px-4 py-2 text-[13px] font-bold text-ink hover:bg-s2">
              Charger une vidéo
              <input type="file" accept="video/*" className="hidden" onChange={useFile} />
            </label>
          </div>
        </div>
      ) : null}
    </div>
  );
}
```

`frontend/components/console/Workspace.tsx` :
```tsx
"use client";

import { useMemo } from "react";
import { useLiveStream } from "@/hooks/useLiveStream";
import { rosterFromResults, alertFromEvent } from "@/lib/live";
import { riskOf } from "@/lib/zoneRisk";
import { VideoStage } from "./VideoStage";
import { Roster } from "./Roster";
import { AlertsPanel } from "./AlertsPanel";
import { MetricTile } from "@/components/ui/MetricTile";
import type { Alert } from "@/lib/types";

export function Workspace() {
  const { response, sendFrame, status } = useLiveStream();

  const roster = useMemo(() => (response ? rosterFromResults(response.results) : []), [response]);
  const alerts: Alert[] = useMemo(
    () => (response ? response.events.map((e) => alertFromEvent(e, riskOf)) : []),
    [response]
  );
  const nonCompliant = roster.filter((r) => !r.compliant).length;

  return (
    <div className="grid min-h-0 grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] gap-3.5 overflow-hidden p-3.5">
      <div className="flex min-h-0 flex-col gap-3.5">
        <VideoStage response={response} onFrame={sendFrame} />
        <div className="grid grid-cols-4 gap-2.5">
          <MetricTile label="Personnes" value={String(roster.length)} />
          <MetricTile label="Non conformes" value={String(nonCompliant)} tone="crit" />
          <MetricTile label="Alertes" value={String(alerts.length)} tone="warn" />
          <MetricTile label="Service" value={status === "open" ? "OK" : "…"} tone={status === "open" ? "ok" : "default"} />
        </div>
      </div>
      <div className="grid min-h-0 grid-rows-2 gap-3.5">
        <Roster entries={roster} />
        <AlertsPanel alerts={alerts} />
      </div>
    </div>
  );
}
```

`frontend/app/page.tsx` — remplacer le bloc workspace statique par `<Workspace />` :
```tsx
import { NavRail } from "@/components/console/NavRail";
import { VitalStrip } from "@/components/console/VitalStrip";
import { FilterBar } from "@/components/console/FilterBar";
import { Workspace } from "@/components/console/Workspace";

export default function Page() {
  return (
    <div className="grid h-dvh grid-cols-[60px_1fr]">
      <NavRail />
      <div className="grid min-w-0 grid-rows-[auto_auto_1fr]">
        <VitalStrip />
        <FilterBar />
        <Workspace />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Lancer le test Roster** — `npx vitest run components/console/Roster.test.tsx` → PASS.

- [ ] **Step 5: Suite complète + build**

Run: `cd frontend && npm run test && npm run build`
Expected: tous les tests verts ; build réussi. *(Note : `mock.ts` et `console.test.tsx` de P2-a.1 ne sont plus référencés par la page live ; si `console.test.tsx` échoue car la page a changé, l'adapter pour vérifier la présence de `NavRail`/`VitalStrip`/`FilterBar` + un contrôle de source « Webcam ».)*

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/zoneRisk.ts frontend/components/console/Roster.tsx frontend/components/console/VideoStage.tsx frontend/components/console/Workspace.tsx frontend/app/page.tsx frontend/components/console/Roster.test.tsx frontend/app/console.test.tsx
git commit -m "feat(frontend): live workspace (VideoStage overlays + live Roster + alerts)"
```

---

## Self-Review

**1. Couverture spec (P2-a.2) :** source webcam + upload ✅ (Task 6 VideoStage) ; échantillonnage → WS ✅ (Task 5 sampler/hook, Task 4 client) ; overlays détection (personne vert/rouge, EPI) ✅ (Task 3 + VideoStage) ; roster live ✅ (Task 2 + Roster) ; file d'alertes live priorisée sévérité×risque ✅ (Task 1 priority + Task 2 alertFromEvent + AlertsPanel réutilisé) ; câblage console ✅ (Task 6 Workspace/page). Filtres/recherche & éditeur de zones = **P2-a.3** (hors périmètre).

**2. Placeholders :** aucun — code complet. Les couches canvas/`getUserMedia`/WebSocket sont volontairement minces et non unit-testées (jsdom) ; la logique pure sous-jacente (priority/live/overlay/streamClient) est en TDD.

**3. Cohérence des types :** `Detection/ComplianceResult/ViolationEvent/FrameResponse` (Task 1) consommés par `overlay` (T3), `live` (T2), `streamClient` (T4), `useLiveStream` (T5), `VideoStage`/`Workspace` (T6) ; `Severity` (P2-a.1) produit par `severityFor` (T1) → `alertFromEvent` (T2) → `Alert` → `AlertsPanel` (P2-a.1) ; `RosterEntry` (T2) → `Roster` (T6) ; `riskOf` (T6) injecté dans `alertFromEvent`. `StreamClient` (T4) enveloppé par `useLiveStream` (T5), consommé par `Workspace` (T6).
