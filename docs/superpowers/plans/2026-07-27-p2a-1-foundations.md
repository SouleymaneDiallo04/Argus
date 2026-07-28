# P2-a.1 — Fondations & Design System (Argus Ops Console) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Poser les fondations du frontend « Argus Ops Console » — scaffold Next.js, design tokens, composants réutilisables du design system, shell de console statique (données mock) — et ajouter le CORS au backend. Livrable : la console s'affiche (statique) et le design system est testé.

**Architecture:** App Next.js (App Router, TypeScript) dans `frontend/`, Tailwind + tokens CSS du design system, composants présentationnels typés, tests Vitest + Testing Library. Le backend P1b gagne un middleware CORS.

**Tech Stack:** Next.js 15 (App Router), TypeScript, Tailwind CSS, next/font (IBM Plex), Vitest + @testing-library/react + jsdom ; FastAPI CORSMiddleware côté backend.

## Global Constraints

- **Design system = source de vérité** (spec `docs/superpowers/specs/2026-07-27-p2a-frontend-console-design.md`). Palette graphite + sémantique ISO **stricte** : `#0B0D12` fond, surfaces `#111419/#161A22`, texte `#EDEFF4/#98A0B2/#5E6779` ; **bleu obligation** `#3B82F6` ; **critique** `#F0464B`, **attention** `#F5A524`, **conforme** `#31C46F`, **neutre** `#6B7488`. La couleur encode un rôle — **jamais décorative**.
- **Typo** : IBM Plex Sans (UI) + IBM Plex Mono (données, `tabular-nums`) via `next/font/google` (auto-hébergé au build, aucune requête externe au runtime).
- **Composants** présentationnels, props typées, classes Tailwind mappées aux tokens ; **traitement identique partout** (pas de one-off).
- **Accessibilité** : focus visible, `tabular-nums` sur les données, couleur jamais seule (tag texte + forme).
- **Tests** : Vitest + @testing-library/react (jsdom). Aucune dépendance à un backend réel.
- Commits : préfixe conventionnel, anglais, **sans `Co-Authored-By`** ni ligne "Generated with".
- Windows : `npm` fonctionne ; le backend garde `py -m pytest` depuis `backend/`.

Contrat backend consommé plus tard (P2-a.2/.3), rappelé ici pour les types partagés :
`WS { frame, timestamp } -> { detections:[{cls,bbox:[x1,y1,x2,y2],confidence,track_id}], results:[{track_id,zone,required,present,missing,compliant}], events:[{track_id,zone,missing,timestamp,camera}] }` ; `GET/PUT /zones { zones:[{name,polygon:[[x,y]...],required_ppe:[...]}] }`.

---

### Task 1: CORS backend (accès navigateur au REST des zones)

**Files:**
- Modify: `backend/app/api/app.py`
- Test: `backend/tests/test_cors.py`

**Interfaces:**
- Produces: l'app FastAPI renvoie les en-têtes CORS ; origines via env `ARGUS_CORS_ORIGINS` (CSV), défaut `http://localhost:3000`.

- [ ] **Step 1: Écrire le test qui échoue** — `backend/tests/test_cors.py`

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app


def _client():
    app = create_app()
    app.state.detector = object()   # stub : évite le chargement du modèle au démarrage
    app.state.decode = lambda b64: b64
    return TestClient(app)


def test_zones_get_has_cors_header_for_allowed_origin():
    resp = _client().get("/zones", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_preflight_put_zones_allowed():
    resp = _client().options(
        "/zones",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && py -m pytest tests/test_cors.py -v`
Expected: FAIL — pas d'en-tête `access-control-allow-origin`.

- [ ] **Step 3: Écrire l'implémentation** — dans `backend/app/api/app.py`, ajouter le middleware au début de `create_app()`.

Ajouter l'import en tête de fichier :
```python
from fastapi.middleware.cors import CORSMiddleware
```

Dans `create_app()`, juste après `app = FastAPI(title="Argus", lifespan=lifespan)` :
```python
    origins = [o.strip() for o in os.environ.get(
        "ARGUS_CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```
(`os` est déjà importé dans `app.py`.)

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && py -m pytest tests/test_cors.py -v` puis `py -m pytest -q`
Expected: PASS (2 nouveaux) ; suite backend toujours verte.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/app.py backend/tests/test_cors.py
git commit -m "feat(api): CORS middleware for browser access to /zones"
```

---

### Task 2: Scaffold Next.js + Tailwind + tokens + Vitest

**Files:**
- Create: `frontend/` (app Next.js) — `package.json`, `next.config.mjs`, `tsconfig.json`, `postcss.config.mjs`, `tailwind.config.ts`, `vitest.config.ts`, `vitest.setup.ts`, `app/layout.tsx`, `app/globals.css`, `app/page.tsx`
- Test: `frontend/app/smoke.test.tsx`

**Interfaces:**
- Produces: app Next.js qui build ; tokens du design system en variables CSS + thème Tailwind ; runner de tests Vitest opérationnel.

- [ ] **Step 1: Créer l'app Next.js (non-interactif)**

Run (depuis la racine du repo) :
```bash
npx create-next-app@latest frontend --ts --tailwind --app --eslint --no-src-dir --import-alias "@/*" --use-npm --yes
```
Expected: dossier `frontend/` créé avec Next.js + TS + Tailwind + App Router.

- [ ] **Step 2: Ajouter les dépendances de test**

Run:
```bash
cd frontend && npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

- [ ] **Step 3: Config Vitest** — `frontend/vitest.config.ts`

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
  },
  resolve: {
    alias: { "@": fileURLToPath(new URL("./", import.meta.url)) },
  },
});
```

`frontend/vitest.setup.ts` :
```ts
import "@testing-library/jest-dom/vitest";
```

Dans `frontend/package.json`, ajouter au bloc `scripts` : `"test": "vitest run"`.

- [ ] **Step 4: Tokens du design system** — remplacer `frontend/app/globals.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg: #0B0D12;
  --s1: #111419; --s2: #161A22; --s3: #1D222C;
  --line: rgba(255,255,255,.065); --line2: rgba(255,255,255,.11);
  --ink: #EDEFF4; --ink2: #98A0B2; --ink3: #5E6779;
  --brand: #3B82F6;           /* obligation ISO / interactif */
  --crit: #F0464B; --warn: #F5A524; --ok: #31C46F; --slate: #6B7488;
}

html, body { height: 100%; }
body { background: var(--bg); color: var(--ink); }
.tabnum { font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }
```

- [ ] **Step 5: Thème Tailwind** — `frontend/tailwind.config.ts` : étendre `theme.extend.colors` pour exposer les tokens.

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)", s1: "var(--s1)", s2: "var(--s2)", s3: "var(--s3)",
        line: "var(--line)", line2: "var(--line2)",
        ink: "var(--ink)", ink2: "var(--ink2)", ink3: "var(--ink3)",
        brand: "var(--brand)",
        crit: "var(--crit)", warn: "var(--warn)", ok: "var(--ok)", slate: "var(--slate)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
```

- [ ] **Step 6: Fonts + layout** — `frontend/app/layout.tsx`

```tsx
import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const sans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-sans" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-mono" });

export const metadata: Metadata = { title: "Argus — Ops Console", description: "Supervision HSE temps réel" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`${sans.variable} ${mono.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
```

- [ ] **Step 7: Page placeholder** — `frontend/app/page.tsx`

```tsx
export default function Page() {
  return <main className="grid min-h-dvh place-items-center text-ink2">Argus Ops Console</main>;
}
```

- [ ] **Step 8: Test smoke** — `frontend/app/smoke.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import Page from "./page";

test("la page racine rend le nom de la console", () => {
  render(<Page />);
  expect(screen.getByText(/Argus Ops Console/i)).toBeInTheDocument();
});
```

- [ ] **Step 9: Vérifier build + test**

Run:
```bash
cd frontend && npm run test && npm run build
```
Expected: test PASS ; build Next.js réussi.

- [ ] **Step 10: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Next.js + Tailwind design tokens + Vitest"
```

---

### Task 3: Composants primitifs — SeverityTag, StatusBadge, PpeChip

**Files:**
- Create: `frontend/components/ui/severity.ts`, `frontend/components/ui/SeverityTag.tsx`, `frontend/components/ui/StatusBadge.tsx`, `frontend/components/ui/PpeChip.tsx`
- Test: `frontend/components/ui/primitives.test.tsx`

**Interfaces:**
- Produces: type `Severity = "crit" | "high" | "med" | "low"` + `SEVERITY_LABEL` ; `<SeverityTag severity>` ; type `AlertStatus = "active" | "ack" | "resolved"` + `<StatusBadge status>` ; `<PpeChip label />`.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/components/ui/primitives.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { SeverityTag } from "./SeverityTag";
import { StatusBadge } from "./StatusBadge";
import { PpeChip } from "./PpeChip";

test("SeverityTag affiche le libellé FR et porte la couleur de rôle", () => {
  render(<SeverityTag severity="crit" />);
  const el = screen.getByText("CRITIQUE");
  expect(el).toBeInTheDocument();
  expect(el.className).toMatch(/crit/);
});

test("StatusBadge affiche les 3 états", () => {
  const { rerender } = render(<StatusBadge status="active" />);
  expect(screen.getByText("Active")).toBeInTheDocument();
  rerender(<StatusBadge status="ack" />);
  expect(screen.getByText("Acquittée")).toBeInTheDocument();
  rerender(<StatusBadge status="resolved" />);
  expect(screen.getByText("Résolue")).toBeInTheDocument();
});

test("PpeChip affiche l'EPI", () => {
  render(<PpeChip label="casque" />);
  expect(screen.getByText("casque")).toBeInTheDocument();
});
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd frontend && npx vitest run components/ui/primitives.test.tsx`
Expected: FAIL — modules introuvables.

- [ ] **Step 3: Écrire l'implémentation**

`frontend/components/ui/severity.ts` :
```ts
export type Severity = "crit" | "high" | "med" | "low";
export const SEVERITY_LABEL: Record<Severity, string> = {
  crit: "CRITIQUE", high: "ÉLEVÉ", med: "MOYEN", low: "FAIBLE",
};
export const SEVERITY_ORDER: Severity[] = ["crit", "high", "med", "low"];
```

`frontend/components/ui/SeverityTag.tsx` :
```tsx
import { Severity, SEVERITY_LABEL } from "./severity";

const CLS: Record<Severity, string> = {
  crit: "bg-crit/15 text-crit",
  high: "bg-warn/15 text-warn",
  med: "bg-brand/15 text-brand",
  low: "bg-slate/15 text-slate",
};

export function SeverityTag({ severity }: { severity: Severity }) {
  return (
    <span className={`inline-flex items-center rounded-[5px] px-1.5 py-1 font-mono text-[10px] font-bold tracking-wide ${CLS[severity]}`}>
      {SEVERITY_LABEL[severity]}
    </span>
  );
}
```

`frontend/components/ui/StatusBadge.tsx` :
```tsx
export type AlertStatus = "active" | "ack" | "resolved";
const CFG: Record<AlertStatus, { label: string; cls: string }> = {
  active: { label: "Active", cls: "bg-crit/15 text-crit" },
  ack: { label: "Acquittée", cls: "bg-warn/15 text-warn" },
  resolved: { label: "Résolue", cls: "bg-ok/15 text-ok" },
};

export function StatusBadge({ status }: { status: AlertStatus }) {
  const c = CFG[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10.5px] font-bold ${c.cls}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {c.label}
    </span>
  );
}
```

`frontend/components/ui/PpeChip.tsx` :
```tsx
export function PpeChip({ label, missing = true }: { label: string; missing?: boolean }) {
  return (
    <span className={`rounded px-1.5 py-[3px] font-mono text-[10px] font-semibold ${missing ? "bg-crit/15 text-crit" : "bg-ok/15 text-ok"}`}>
      {label}
    </span>
  );
}
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd frontend && npx vitest run components/ui/primitives.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/severity.ts frontend/components/ui/SeverityTag.tsx frontend/components/ui/StatusBadge.tsx frontend/components/ui/PpeChip.tsx frontend/components/ui/primitives.test.tsx
git commit -m "feat(frontend): design-system primitives (SeverityTag, StatusBadge, PpeChip)"
```

---

### Task 4: Composants composés — Logo, MetricTile, AlertRow

**Files:**
- Create: `frontend/components/ui/Logo.tsx`, `frontend/components/ui/MetricTile.tsx`, `frontend/components/ui/AlertRow.tsx`, `frontend/lib/types.ts`
- Test: `frontend/components/ui/composed.test.tsx`

**Interfaces:**
- Consumes: `Severity` (Task 3), `AlertStatus` (Task 3), `SeverityTag`, `StatusBadge`, `PpeChip`.
- Produces: type `Alert = { id: string; severity: Severity; time: string; zone: string; personId: string; missing: string[]; status: AlertStatus }` ; `<Logo size?>` (SVG Objectif-Œil) ; `<MetricTile label value delta? tone?>` ; `<AlertRow alert>`.

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/components/ui/composed.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { Logo } from "./Logo";
import { MetricTile } from "./MetricTile";
import { AlertRow } from "./AlertRow";
import type { Alert } from "@/lib/types";

test("Logo rend un SVG avec un rôle/label accessible", () => {
  render(<Logo />);
  expect(screen.getByLabelText(/argus/i)).toBeInTheDocument();
});

test("MetricTile affiche libellé et valeur", () => {
  render(<MetricTile label="Critiques actives" value="3" tone="crit" />);
  expect(screen.getByText("Critiques actives")).toBeInTheDocument();
  expect(screen.getByText("3")).toBeInTheDocument();
});

test("AlertRow affiche sévérité, zone, ID et EPI manquants", () => {
  const a: Alert = { id: "1", severity: "crit", time: "00:12", zone: "Fonderie·Coulée", personId: "#37", missing: ["casque", "shoes"], status: "active" };
  render(<table><tbody><AlertRow alert={a} /></tbody></table>);
  expect(screen.getByText("CRITIQUE")).toBeInTheDocument();
  expect(screen.getByText("Fonderie·Coulée")).toBeInTheDocument();
  expect(screen.getByText("#37")).toBeInTheDocument();
  expect(screen.getByText("casque")).toBeInTheDocument();
  expect(screen.getByText("Active")).toBeInTheDocument();
});
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd frontend && npx vitest run components/ui/composed.test.tsx`
Expected: FAIL — modules introuvables.

- [ ] **Step 3: Écrire l'implémentation**

`frontend/lib/types.ts` :
```ts
import type { Severity } from "@/components/ui/severity";
import type { AlertStatus } from "@/components/ui/StatusBadge";

export type Alert = {
  id: string;
  severity: Severity;
  time: string;
  zone: string;
  personId: string;
  missing: string[];
  status: AlertStatus;
};
```

`frontend/components/ui/Logo.tsx` (marque « Objectif-Œil ») :
```tsx
export function Logo({ size = 24, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" role="img" aria-label="Argus">
      <path d="M3 24Q24 6 45 24Q24 42 3 24Z" stroke={color} strokeWidth="2.6" />
      <polygon points="24,14 32,18.8 32,29.2 24,34 16,29.2 16,18.8" stroke={color} strokeWidth="2" />
      <circle cx="24" cy="24" r="3.4" fill={color} />
    </svg>
  );
}
```

`frontend/components/ui/MetricTile.tsx` :
```tsx
const TONE: Record<string, string> = { crit: "text-crit", ok: "text-ok", warn: "text-warn", default: "text-ink" };

export function MetricTile({ label, value, delta, tone = "default" }: {
  label: string; value: string; delta?: string; tone?: keyof typeof TONE;
}) {
  return (
    <div className="rounded-[9px] border border-line bg-s1 px-3 py-2.5">
      <div className="mb-1.5 text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">{label}</div>
      <b className={`font-mono text-[21px] leading-none tabnum ${TONE[tone] ?? TONE.default}`}>{value}</b>
      {delta ? <span className="ml-1.5 font-mono text-[11px] text-ink2 tabnum">{delta}</span> : null}
    </div>
  );
}
```

`frontend/components/ui/AlertRow.tsx` :
```tsx
import type { Alert } from "@/lib/types";
import { SeverityTag } from "./SeverityTag";
import { StatusBadge } from "./StatusBadge";
import { PpeChip } from "./PpeChip";

const SPINE: Record<string, string> = { crit: "bg-crit", high: "bg-warn", med: "bg-brand", low: "bg-slate" };

export function AlertRow({ alert }: { alert: Alert }) {
  return (
    <tr className="group relative border-b border-line hover:bg-s2">
      <td className="relative py-2.5 pl-4 pr-2">
        <span className={`absolute left-0 top-0 h-full w-[3px] ${SPINE[alert.severity]}`} aria-hidden />
        <SeverityTag severity={alert.severity} />
      </td>
      <td className="px-2 font-mono text-[12px] text-ink3 tabnum">{alert.time}</td>
      <td className="px-2">
        <div className="text-[12.5px] font-semibold">{alert.zone}</div>
        <div className="mt-1 flex flex-wrap gap-1">
          {alert.missing.map((m) => <PpeChip key={m} label={m} />)}
        </div>
      </td>
      <td className="px-2 font-mono text-[13px] font-bold text-ink2 tabnum">{alert.personId}</td>
      <td className="py-2.5 pr-4 text-right"><StatusBadge status={alert.status} /></td>
    </tr>
  );
}
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd frontend && npx vitest run components/ui/composed.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/components/ui/Logo.tsx frontend/components/ui/MetricTile.tsx frontend/components/ui/AlertRow.tsx frontend/components/ui/composed.test.tsx
git commit -m "feat(frontend): Logo, MetricTile, AlertRow components"
```

---

### Task 5: Shell de console statique (NavRail, VitalStrip, FilterBar) + page

**Files:**
- Create: `frontend/components/console/NavRail.tsx`, `frontend/components/console/VitalStrip.tsx`, `frontend/components/console/FilterBar.tsx`, `frontend/components/console/AlertsPanel.tsx`, `frontend/lib/mock.ts`
- Modify: `frontend/app/page.tsx`
- Test: `frontend/app/console.test.tsx`

**Interfaces:**
- Consumes: `Logo`, `MetricTile`, `AlertRow`, `Alert` (Task 4), `SEVERITY_ORDER` (Task 3).
- Produces: la page `/` compose le shell Ops Console avec des données mock (`MOCK_ALERTS`).

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/app/console.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import Page from "./page";

test("la console affiche le bandeau vital, les filtres et la file d'alertes", () => {
  render(<Page />);
  expect(screen.getByRole("img", { name: /argus/i })).toBeInTheDocument();
  expect(screen.getByText(/Conformité/i)).toBeInTheDocument();
  expect(screen.getByText(/File d'alertes/i)).toBeInTheDocument();
  // au moins une ligne d'alerte mock rendue
  expect(screen.getAllByText(/CRITIQUE|ÉLEVÉ|MOYEN|FAIBLE/).length).toBeGreaterThan(0);
});
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd frontend && npx vitest run app/console.test.tsx`
Expected: FAIL — la page est le placeholder.

- [ ] **Step 3: Écrire l'implémentation**

`frontend/lib/mock.ts` :
```ts
import type { Alert } from "./types";

export const MOCK_ALERTS: Alert[] = [
  { id: "1", severity: "crit", time: "00:12", zone: "Fonderie·Coulée", personId: "#37", missing: ["casque", "shoes"], status: "active" },
  { id: "2", severity: "crit", time: "00:31", zone: "Fonderie·Coulée", personId: "#56", missing: ["casque"], status: "active" },
  { id: "3", severity: "crit", time: "01:48", zone: "Cariste·Allée 4", personId: "#72", missing: ["gilet"], status: "active" },
  { id: "4", severity: "high", time: "00:34", zone: "Cariste·Allée 4", personId: "#98", missing: ["gilet"], status: "ack" },
  { id: "5", severity: "high", time: "02:05", zone: "Ligne 3·Presse", personId: "#12", missing: ["shoes"], status: "active" },
  { id: "6", severity: "med", time: "03:10", zone: "Entrée chantier", personId: "#01", missing: ["shoes"], status: "ack" },
  { id: "7", severity: "med", time: "03:55", zone: "Atelier B·Soudure", personId: "#23", missing: ["masque"], status: "active" },
  { id: "8", severity: "low", time: "05:02", zone: "Bureau·Mezzanine", personId: "#19", missing: ["masque"], status: "active" },
];
```

`frontend/components/console/NavRail.tsx` :
```tsx
import { Logo } from "@/components/ui/Logo";

export function NavRail() {
  return (
    <nav className="flex w-[60px] flex-col items-center gap-1 border-r border-line bg-[#090B0F] py-3">
      <div className="mb-3 grid h-[34px] w-[34px] place-items-center rounded-lg bg-gradient-to-br from-brand to-[#2560c9] text-white">
        <Logo size={20} color="#fff" />
      </div>
      {["Live", "Alertes", "Zones", "Sites", "Analytique"].map((n, i) => (
        <button key={n} title={n}
          className={`grid h-10 w-10 place-items-center rounded-[9px] text-[10px] ${i === 0 ? "bg-brand/15 text-brand" : "text-ink3 hover:bg-s2 hover:text-ink"}`}>
          {n.slice(0, 2)}
        </button>
      ))}
    </nav>
  );
}
```

`frontend/components/console/VitalStrip.tsx` :
```tsx
export function VitalStrip() {
  return (
    <section className="grid grid-cols-[auto_1fr_auto] items-center gap-6 border-b border-line bg-s1 px-5 py-3.5">
      <div>
        <div className="mb-1.5 text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">Conformité · Site Meknès-Nord</div>
        <div className="flex items-baseline gap-2.5">
          <span className="font-mono text-[34px] font-bold leading-none tabnum">87.4%</span>
          <span className="font-mono text-[12px] font-bold text-ok tabnum">▲ 2.1</span>
        </div>
      </div>
      <div />
      <div className="flex items-center gap-2.5">
        {[["Critique", "3", "text-crit"], ["Attention", "6", "text-warn"], ["Conformes", "41", "text-ok"]].map(([l, v, c]) => (
          <div key={l} className="flex min-w-[74px] flex-col items-end gap-1 rounded-lg border border-line bg-s2 px-3 py-1.5">
            <span className="text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">{l}</span>
            <b className={`font-mono text-[20px] leading-none tabnum ${c}`}>{v}</b>
          </div>
        ))}
      </div>
    </section>
  );
}
```

`frontend/components/console/FilterBar.tsx` :
```tsx
export function FilterBar() {
  return (
    <div className="flex items-center gap-2.5 border-b border-line bg-bg px-4 py-2.5">
      <div className="flex items-center gap-2.5 rounded-lg border border-line2 bg-s2 px-3 py-1.5 font-bold">
        <span className="h-1.5 w-1.5 rounded-full bg-ok" />Meknès-Nord
      </div>
      <input aria-label="Rechercher"
        className="min-w-0 flex-1 max-w-[320px] rounded-lg border border-line bg-s1 px-3 py-1.5 text-[13px] text-ink placeholder:text-ink3"
        placeholder="Rechercher un ID, une zone…" />
      {["Zone", "EPI", "Période", "Statut"].map((f) => (
        <button key={f} className="rounded-lg border border-line bg-s1 px-3 py-1.5 font-semibold text-ink2 hover:text-ink">{f}</button>
      ))}
    </div>
  );
}
```

`frontend/components/console/AlertsPanel.tsx` :
```tsx
import { AlertRow } from "@/components/ui/AlertRow";
import { SEVERITY_ORDER } from "@/components/ui/severity";
import type { Alert } from "@/lib/types";

export function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  const sorted = [...alerts].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
  );
  const crit = alerts.filter((a) => a.severity === "crit").length;
  return (
    <div className="flex min-h-0 flex-col rounded-[10px] border border-line bg-s1">
      <div className="flex items-center gap-2.5 border-b border-line px-3.5 py-2.5">
        <h2 className="text-[14px] font-bold">File d&apos;alertes</h2>
        <span className="rounded-full bg-crit/15 px-2 py-0.5 font-mono text-[11px] font-bold text-crit tabnum">{crit} critiques</span>
      </div>
      <div className="grid grid-cols-[88px_52px_1fr_46px_96px] gap-2.5 border-b border-line px-3.5 py-1.5 text-[10px] font-bold uppercase tracking-[.1em] text-ink3">
        <div>Sévérité</div><div>Temps</div><div>Localisation · manque</div><div>ID</div><div className="text-right">Statut</div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full">
          <colgroup><col className="w-[88px]" /><col className="w-[52px]" /><col /><col className="w-[46px]" /><col className="w-[96px]" /></colgroup>
          <tbody>{sorted.map((a) => <AlertRow key={a.id} alert={a} />)}</tbody>
        </table>
      </div>
    </div>
  );
}
```

`frontend/app/page.tsx` :
```tsx
import { NavRail } from "@/components/console/NavRail";
import { VitalStrip } from "@/components/console/VitalStrip";
import { FilterBar } from "@/components/console/FilterBar";
import { AlertsPanel } from "@/components/console/AlertsPanel";
import { MetricTile } from "@/components/ui/MetricTile";
import { MOCK_ALERTS } from "@/lib/mock";

export default function Page() {
  return (
    <div className="grid h-dvh grid-cols-[60px_1fr]">
      <NavRail />
      <div className="grid min-w-0 grid-rows-[auto_auto_1fr]">
        <VitalStrip />
        <FilterBar />
        <div className="grid min-h-0 grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] gap-3.5 overflow-hidden p-3.5">
          <div className="flex flex-col gap-3.5">
            <div className="grid flex-1 place-items-center rounded-[10px] border border-line2 bg-[#06080d] text-ink3">
              Flux vidéo · (P2-a.2)
            </div>
            <div className="grid grid-cols-4 gap-2.5">
              <MetricTile label="Personnes / site" value="44" delta="+3" />
              <MetricTile label="Critiques actives" value="3" tone="crit" />
              <MetricTile label="Acquit. moy." value="1:12" />
              <MetricTile label="Conformité 24 h" value="91.2%" tone="ok" />
            </div>
          </div>
          <AlertsPanel alerts={MOCK_ALERTS} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd frontend && npx vitest run app/console.test.tsx`
Expected: PASS.

- [ ] **Step 5: Lancer toute la suite front + build**

Run: `cd frontend && npm run test && npm run build`
Expected: tous les tests verts ; build réussi.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/console frontend/lib/mock.ts frontend/app/page.tsx frontend/app/console.test.tsx
git commit -m "feat(frontend): static Ops Console shell (NavRail, VitalStrip, FilterBar, AlertsPanel)"
```

---

## Self-Review

**1. Couverture spec :** CORS backend ✅ (Task 1) ; scaffold + tokens design system ✅ (Task 2) ; composants réutilisables `SeverityTag/StatusBadge/PpeChip/Logo/MetricTile/AlertRow` ✅ (Tasks 3-4, traitement unique) ; shell Ops Console (rail/bandeau vital/filtres/file d'alertes priorisée par sévérité) ✅ (Task 5) ; typo IBM Plex + `tabular-nums` ✅ ; palette ISO stricte via tokens ✅. Live/overlays/zones/upload = **hors P2-a.1** (→ P2-a.2/.3), le placeholder « Flux vidéo · (P2-a.2) » le matérialise.

**2. Placeholders (au sens plan) :** aucun — code complet à chaque étape. (Le bloc « Flux vidéo » de l'UI est un état volontaire de P2-a.1, pas un TODO de plan.)

**3. Cohérence des types :** `Severity`/`SEVERITY_ORDER` (Task 3) consommés par `AlertRow` + `AlertsPanel` (tri) ; `AlertStatus` (Task 3) → `Alert` (Task 4) → `AlertRow`/`AlertsPanel`/`mock` (Tasks 4-5) ; `Logo`/`MetricTile`/`AlertRow` (Task 4) consommés par le shell (Task 5). Tokens Tailwind (`crit/warn/ok/brand/slate/ink…`) définis en Task 2 et utilisés partout ensuite. Alias `@/*` posé au scaffold.
