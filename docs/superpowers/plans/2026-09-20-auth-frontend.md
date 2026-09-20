# V2 — Auth + rôles (frontend) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Login UI + envoi du token + protection des routes + gating par rôle, complétant le backend auth.

**Architecture:** helpers token + `authFetch` (http) → `authApi` (login/me) → `AuthProvider`/`useAuth` (layout) → `Shell` redirige si non connecté + page `/login` → gating par rôle dans Dashboard/Workspace/NavRail.

**Tech Stack:** Next.js 16 (client), TypeScript, Vitest. Zéro nouvelle dépendance.

## Global Constraints

- Token en `localStorage` (`argus.token`), envoyé par `authFetch` (Bearer). Writes protégés
  (`setEventStatus`, `putZones`, `startRtsp`, `stopRtsp`) en `authFetch` par défaut ; reads en `fetch`.
- **Opt-in transparent** : `/auth/me` = 200 sans token quand l'auth backend est désactivée →
  l'app s'affiche sans login.
- **Contexte `useAuth` par défaut** (hors provider) = `{user:null, ready:true}` (tests unitaires
  ne cassent pas). Redirection : `Shell` via `next/router` mocké en test.
- Rôles : `admin` (zones, RTSP) ; `hse`+`admin` (ack). Front : `npm run test` / `npm run build`.
  Suites existantes (**53**) vertes. Commits conventionnels, anglais, **sans `Co-Authored-By`**.
  Branche : `feat/auth-frontend`.

---

### Task 1: `http` — helpers token + `authFetch`

**Files:**
- Modify: `frontend/lib/http.ts`
- Test: `frontend/lib/http.test.ts`

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/lib/http.test.ts`
```ts
import { getToken, setToken, clearToken, authFetch } from "./http";

test("token helpers persistent en localStorage", () => {
  clearToken();
  expect(getToken()).toBeNull();
  setToken("abc");
  expect(getToken()).toBe("abc");
  clearToken();
  expect(getToken()).toBeNull();
});

test("authFetch ajoute le header Bearer si token présent", async () => {
  setToken("tok");
  let seen: Headers | undefined;
  const orig = global.fetch;
  global.fetch = (async (_u: string, i?: RequestInit) => {
    seen = new Headers(i?.headers); return { ok: true } as Response;
  }) as typeof fetch;
  await authFetch("http://x");
  expect(seen?.get("authorization")).toBe("Bearer tok");
  global.fetch = orig;
  clearToken();
});
```

- [ ] **Step 2: Lancer** — `cd frontend && npx vitest run lib/http.test.ts` → FAIL.

- [ ] **Step 3: Écrire l'implémentation** — ajouter à `frontend/lib/http.ts` (après `qs`)
```ts
const TOKEN_KEY = "argus.token";

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(t: string): void {
  try { localStorage.setItem(TOKEN_KEY, t); } catch { /* ignore */ }
}
export function clearToken(): void {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
}
export function authFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}
```

- [ ] **Step 4: Lancer** — PASS (2).

- [ ] **Step 5: Commit**
```bash
git add frontend/lib/http.ts frontend/lib/http.test.ts
git commit -m "feat(frontend): token storage + authFetch wrapper"
```

---

### Task 2: `authApi` (login + me)

**Files:**
- Create: `frontend/lib/authApi.ts`, `frontend/lib/authApi.test.ts`

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/lib/authApi.test.ts`
```ts
import { login, me } from "./authApi";

test("login poste les identifiants", async () => {
  let url = ""; let init: RequestInit | undefined;
  const f = (async (u: string, i?: RequestInit) => {
    url = u; init = i;
    return { ok: true, status: 200, json: async () => ({ access_token: "t", role: "admin" }) } as Response;
  }) as typeof fetch;
  const r = await login("a", "b", f);
  expect(url).toContain("/auth/login");
  expect(init?.method).toBe("POST");
  expect(JSON.parse(init?.body as string)).toEqual({ username: "a", password: "b" });
  expect(r.role).toBe("admin");
});

test("me lit /auth/me", async () => {
  const f = (async () => ({ ok: true, status: 200, json: async () => ({ username: "a", role: "hse" }) }) as Response) as typeof fetch;
  expect((await me(f)).role).toBe("hse");
});
```

- [ ] **Step 2: Lancer** — FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `frontend/lib/authApi.ts`
```ts
import { API, authFetch } from "./http";

export type AuthUser = { username: string; role: string };

export async function login(
  username: string, password: string, fetchFn: typeof fetch = fetch,
): Promise<{ access_token: string; role: string }> {
  const res = await fetchFn(`${API}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(`login -> ${res.status}`);
  return (await res.json()) as { access_token: string; role: string };
}

export async function me(fetchFn: typeof fetch = authFetch): Promise<AuthUser> {
  const res = await fetchFn(`${API}/auth/me`);
  if (!res.ok) throw new Error(`me -> ${res.status}`);
  return (await res.json()) as AuthUser;
}
```

- [ ] **Step 4: Lancer** — PASS (2).

- [ ] **Step 5: Commit**
```bash
git add frontend/lib/authApi.ts frontend/lib/authApi.test.ts
git commit -m "feat(frontend): authApi login + me"
```

---

### Task 3: `AuthProvider` + `useAuth`

**Files:**
- Create: `frontend/components/auth/AuthProvider.tsx`, `frontend/components/auth/AuthProvider.test.tsx`

- [ ] **Step 1: Écrire le test qui échoue** — `frontend/components/auth/AuthProvider.test.tsx`
```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "./AuthProvider";

function Probe() {
  const { user, ready, login, logout } = useAuth();
  return (
    <div>
      <span>ready:{String(ready)}</span>
      <span>user:{user?.username ?? "none"}</span>
      <button onClick={() => login("a", "b")}>login</button>
      <button onClick={logout}>logout</button>
    </div>
  );
}

test("AuthProvider charge le user puis logout le vide", async () => {
  render(<AuthProvider loadMe={async () => ({ username: "alice", role: "admin" })}
                       doLogin={async () => ({ access_token: "t", role: "admin" })}>
    <Probe /></AuthProvider>);
  expect(await screen.findByText("user:alice")).toBeInTheDocument();
  fireEvent.click(screen.getByText("logout"));
  await waitFor(() => expect(screen.getByText("user:none")).toBeInTheDocument());
});

test("AuthProvider met user à null si me échoue", async () => {
  render(<AuthProvider loadMe={async () => { throw new Error("401"); }}
                       doLogin={async () => ({ access_token: "t", role: "admin" })}>
    <Probe /></AuthProvider>);
  await waitFor(() => expect(screen.getByText("user:none")).toBeInTheDocument());
  expect(screen.getByText("ready:true")).toBeInTheDocument();
});
```

- [ ] **Step 2: Lancer** — FAIL.

- [ ] **Step 3: Écrire l'implémentation** — `frontend/components/auth/AuthProvider.tsx`
```tsx
"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { login as apiLogin, me as apiMe, type AuthUser } from "@/lib/authApi";
import { setToken, clearToken } from "@/lib/http";

type AuthCtx = {
  user: AuthUser | null; ready: boolean;
  login: (u: string, p: string) => Promise<void>; logout: () => void;
};

const Ctx = createContext<AuthCtx>({
  user: null, ready: true, login: async () => {}, logout: () => {},
});

export function useAuth(): AuthCtx {
  return useContext(Ctx);
}

export function AuthProvider({
  children, loadMe = apiMe, doLogin = apiLogin,
}: {
  children: React.ReactNode; loadMe?: typeof apiMe; doLogin?: typeof apiLogin;
}) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try { setUser(await loadMe()); } catch { setUser(null); } finally { setReady(true); }
  }, [loadMe]);

  useEffect(() => { refresh(); }, [refresh]);

  const login = useCallback(async (u: string, p: string) => {
    const { access_token } = await doLogin(u, p);
    setToken(access_token);
    await refresh();
  }, [doLogin, refresh]);

  const logout = useCallback(() => { clearToken(); setUser(null); }, []);

  return <Ctx.Provider value={{ user, ready, login, logout }}>{children}</Ctx.Provider>;
}
```

- [ ] **Step 4: Lancer** — PASS (2).

- [ ] **Step 5: Commit**
```bash
git add frontend/components/auth/AuthProvider.tsx frontend/components/auth/AuthProvider.test.tsx
git commit -m "feat(frontend): AuthProvider + useAuth context"
```

---

### Task 4: Protection des routes — `Shell` + `/login` + layout

**Files:**
- Modify: `frontend/vitest.setup.ts`, `frontend/components/console/Shell.tsx`, `frontend/app/layout.tsx`, `frontend/app/console.test.tsx`
- Create: `frontend/app/login/page.tsx`, `frontend/components/console/Shell.test.tsx`

- [ ] **Step 1: Écrire les tests qui échouent** — `frontend/components/console/Shell.test.tsx`
```tsx
import { vi } from "vitest";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import { render, screen, waitFor } from "@testing-library/react";
import { Shell } from "./Shell";
import { AuthProvider } from "@/components/auth/AuthProvider";

test("Shell redirige vers /login si non connecté", async () => {
  render(<AuthProvider loadMe={async () => { throw new Error("401"); }}>
    <Shell active="live"><div>contenu</div></Shell></AuthProvider>);
  await waitFor(() => expect(push).toHaveBeenCalledWith("/login"));
});

test("Shell rend le contenu si connecté", async () => {
  render(<AuthProvider loadMe={async () => ({ username: "a", role: "admin" })}>
    <Shell active="live"><div>contenu</div></Shell></AuthProvider>);
  expect(await screen.findByText("contenu")).toBeInTheDocument();
});
```

- [ ] **Step 2: Lancer** — `cd frontend && npx vitest run components/console/Shell.test.tsx` → FAIL.

- [ ] **Step 3: Écrire l'implémentation**

(a) `frontend/vitest.setup.ts` — ajouter un mock global de `next/navigation` (après le mock
`next/link` existant) :
```ts
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: () => {}, replace: () => {}, refresh: () => {} }),
  usePathname: () => "/",
}));
```

(b) `frontend/components/console/Shell.tsx` — remplacer par :
```tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { NavRail } from "./NavRail";
import { useAuth } from "@/components/auth/AuthProvider";

export function Shell({
  active, children,
}: { active: "live" | "analytique"; children: React.ReactNode }) {
  const { user, ready } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (ready && !user) router.push("/login");
  }, [ready, user, router]);
  if (!ready || !user) return null;
  return (
    <div className="grid h-dvh grid-cols-[60px_1fr]">
      <NavRail active={active} />
      <div className="grid min-h-0 min-w-0">{children}</div>
    </div>
  );
}
```

(c) `frontend/app/login/page.tsx` :
```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try { await login(username, password); router.push("/"); }
    catch { setError("Identifiants invalides"); }
  }

  const field = "mb-2 w-full rounded-lg border border-line bg-s2 px-3 py-2 text-[13px] text-ink placeholder:text-ink3";
  return (
    <div className="grid h-dvh place-items-center bg-bg">
      <form onSubmit={submit} className="w-80 rounded-[12px] border border-line bg-s1 p-6">
        <h1 className="mb-4 text-[15px] font-bold">Argus — Connexion</h1>
        <input aria-label="Utilisateur" value={username} placeholder="Utilisateur"
               onChange={(e) => setUsername(e.target.value)} className={field} />
        <input aria-label="Mot de passe" type="password" value={password} placeholder="Mot de passe"
               onChange={(e) => setPassword(e.target.value)} className={field + " mb-3"} />
        {error ? <p className="mb-2 text-[12px] text-crit">{error}</p> : null}
        <button type="submit" className="w-full rounded-lg bg-brand px-3 py-2 text-[13px] font-bold text-white">
          Se connecter
        </button>
      </form>
    </div>
  );
}
```

(d) `frontend/app/layout.tsx` — envelopper `{children}` :
```tsx
import { AuthProvider } from "@/components/auth/AuthProvider";
```
```tsx
      <body className="min-h-full font-sans"><AuthProvider>{children}</AuthProvider></body>
```

(e) `frontend/app/console.test.tsx` — envelopper `Page` dans un `AuthProvider` admin injecté et
passer les assertions en asynchrone (le `Shell` rend après `loadMe`). Remplacer le corps du test :
```tsx
import { AuthProvider } from "@/components/auth/AuthProvider";
// ...
test("la console rend le shell + le sélecteur de source vidéo", async () => {
  render(
    <AuthProvider loadMe={async () => ({ username: "admin", role: "admin" })}>
      <Page />
    </AuthProvider>,
  );
  expect(await screen.findByRole("img", { name: /argus/i })).toBeInTheDocument();
  expect(screen.getByText(/Conformité · Site/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /webcam/i })).toBeInTheDocument();
});
```
*(garder le shim WebSocket + le mock `fetch` existants dans `beforeAll`.)*

- [ ] **Step 4: Lancer les tests** — `cd frontend && npm run test`
Expected: `Shell.test` + `console.test` verts ; suite entière verte.

- [ ] **Step 5: Commit**
```bash
git add frontend/vitest.setup.ts frontend/components/console/Shell.tsx frontend/components/console/Shell.test.tsx frontend/app/login/page.tsx frontend/app/layout.tsx frontend/app/console.test.tsx
git commit -m "feat(frontend): auth-gated Shell + /login page + provider in layout"
```

---

### Task 5: Gating par rôle + token sur les writes

**Files:**
- Modify: `frontend/lib/eventsApi.ts`, `frontend/lib/zonesApi.ts`, `frontend/lib/sourcesApi.ts`,
  `frontend/components/dashboard/Dashboard.tsx`, `frontend/components/console/Workspace.tsx`,
  `frontend/components/console/NavRail.tsx`
- Test: `frontend/components/dashboard/Dashboard.test.tsx` (ajout), `frontend/components/console/Workspace.test.tsx` (adapt.)

- [ ] **Step 1: Écrire / adapter les tests**

Ajouter à `frontend/components/dashboard/Dashboard.test.tsx` (après le test existant) :
```tsx
import { AuthProvider } from "@/components/auth/AuthProvider";

test("Dashboard masque le contrôle RTSP pour un rôle non-admin", async () => {
  render(<AuthProvider loadMe={async () => ({ username: "op", role: "hse" })}>
    <Dashboard loadStats={async () => stats} loadEvents={async () => events} />
  </AuthProvider>);
  await screen.findByText("#37");
  expect(screen.queryByLabelText(/url rtsp/i)).toBeNull();
});

test("Dashboard montre le contrôle RTSP pour un admin", async () => {
  render(<AuthProvider loadMe={async () => ({ username: "boss", role: "admin" })}>
    <Dashboard loadStats={async () => stats} loadEvents={async () => events} />
  </AuthProvider>);
  expect(await screen.findByLabelText(/url rtsp/i)).toBeInTheDocument();
});
```

Adapter `frontend/components/console/Workspace.test.tsx` — envelopper le rendu dans un
`AuthProvider` admin (sinon « Éditer les zones » est masqué) :
```tsx
import { AuthProvider } from "@/components/auth/AuthProvider";
// dans le test, remplacer render(<Workspace />) par :
render(<AuthProvider loadMe={async () => ({ username: "admin", role: "admin" })}><Workspace /></AuthProvider>);
// et rendre l'assertion du bouton asynchrone : await screen.findByRole("button", { name: /éditer les zones/i })
```

- [ ] **Step 2: Lancer** — FAIL (gating pas encore implémenté / RtspControl toujours présent).

- [ ] **Step 3: Écrire l'implémentation**

(a) `authFetch` par défaut sur les writes :
- `frontend/lib/eventsApi.ts` : `import { API, qs, authFetch } from "./http";` et
  `setEventStatus(id, status, fetchFn: typeof fetch = authFetch)`.
- `frontend/lib/zonesApi.ts` : importer `authFetch` et `putZones(zones, fetchFn: typeof fetch = authFetch)`.
- `frontend/lib/sourcesApi.ts` : importer `authFetch` et
  `startRtsp(url, fetchFn: typeof fetch = authFetch)`, `stopRtsp(fetchFn: typeof fetch = authFetch)`.
  *(`getEvents`/`getStats`/`getZones`/`rtspStatus` restent en `fetch`.)*

(b) `frontend/components/dashboard/Dashboard.tsx` :
```tsx
import { useAuth } from "@/components/auth/AuthProvider";
```
dans le composant :
```tsx
  const { user } = useAuth();
  const canAck = user?.role === "hse" || user?.role === "admin";
  const isAdmin = user?.role === "admin";
```
- rendre `RtspControl` conditionnel :
```tsx
      {isAdmin ? <RtspControl /> : null}
```
- passer `onSetStatus` conditionnellement :
```tsx
        <JournalTable events={events} onSetStatus={canAck ? onSetStatus : undefined} />
```

(c) `frontend/components/console/Workspace.tsx` — gater `onEditZones` :
```tsx
import { useAuth } from "@/components/auth/AuthProvider";
```
```tsx
  const { user } = useAuth();
```
```tsx
          <FilterBar filters={filters} onChange={setFilters}
                     onEditZones={user?.role === "admin" ? () => setEditing(true) : undefined} />
```
*(remplacer le `onEditZones={() => setEditing(true)}` existant.)*

(d) `frontend/components/console/NavRail.tsx` — badge utilisateur + déconnexion en bas.
Ajouter en tête : `import { useAuth } from "@/components/auth/AuthProvider";` et `"use client"`
est déjà présent. Dans le composant, récupérer `const { user, logout } = useAuth();` et, juste
avant la fermeture du `</nav>`, ajouter :
```tsx
      {user && user.username !== "system" ? (
        <div className="mt-auto flex flex-col items-center gap-1 pt-2">
          <span title={user.username}
                className="grid h-7 w-7 place-items-center rounded-full bg-s2 text-[11px] font-bold text-ink2 uppercase">
            {user.username.slice(0, 2)}
          </span>
          <button onClick={logout} title="Déconnexion"
                  className="text-[9px] font-bold uppercase tracking-wide text-ink3 hover:text-crit">
            Quit
          </button>
        </div>
      ) : null}
```
*(le `<nav>` a `flex-col` ; `mt-auto` pousse le bloc en bas.)*

- [ ] **Step 4: Lancer les tests + build**
Run: `cd frontend && npm run test && npm run build`
Expected: tous verts (Dashboard gating, Workspace adapté, writes en authFetch) ; build OK.

- [ ] **Step 5: Commit**
```bash
git add frontend/lib/eventsApi.ts frontend/lib/zonesApi.ts frontend/lib/sourcesApi.ts frontend/components/dashboard/Dashboard.tsx frontend/components/console/Workspace.tsx frontend/components/console/NavRail.tsx frontend/components/dashboard/Dashboard.test.tsx frontend/components/console/Workspace.test.tsx
git commit -m "feat(frontend): role-gated actions + token on protected writes"
```

---

## Self-Review

**1. Couverture spec :** token+authFetch ✅ (T1) ; authApi ✅ (T2) ; AuthProvider/useAuth ✅ (T3) ;
Shell redirect + /login + layout + opt-in ✅ (T4) ; gating rôle (RTSP/zones/ack) + writes
authentifiés + NavRail user/logout ✅ (T5). Zéro dépendance ✅.

**2. Placeholders :** aucun — code complet. Adaptations de tests existants explicites
(`console.test` en T4, `Workspace.test` en T5 ; wrap `AuthProvider`).

**3. Cohérence des types :** `getToken/authFetch` (T1) ← `authApi.me` (T2) ← `AuthProvider` (T3) ←
`useAuth` consommé par `Shell` (T4), `Dashboard`/`Workspace`/`NavRail` (T5). `AuthUser.role` gate
`admin`/`hse`. Writes → `authFetch` (T5) portant le token stocké au login (T3→T1). Contexte par
défaut `{user:null, ready:true}` garde les tests unitaires sans provider verts ; les tests qui
rendent `Shell`/`Workspace` (redirection/gating) fournissent un `AuthProvider`. Mock global
`next/navigation` (T4) couvre tous les fichiers ; `Shell.test` surcharge avec un spy.
