# V2 — Auth + rôles (frontend) — Design

**Date :** 2026-09-20
**Phase :** V2 — auth, incrément **frontend** (complète le backend auth, PR #17 mergée).
**Statut :** validé

## 1. Objectif

Rendre l'auth **utilisable depuis l'UI** : page de login, envoi du token JWT sur les appels
protégés, protection des routes, et masquage des actions réservées selon le rôle.

## 2. Décisions de conception (validées)

- **Token** en `localStorage` (`argus.token`, caveat XSS accepté), envoyé en `Authorization:
  Bearer` par un wrapper `authFetch`.
- **Protection des routes côté client** (redirection vers `/login` si non connecté), pas de
  middleware SSR.
- **Opt-in transparent** : quand l'auth backend est désactivée, `/auth/me` renvoie 200
  (`system/admin`) sans token → l'app s'affiche **sans login**. L'UI suit le backend, aucun flag.
- **Rôles** : `admin` (éditer zones, contrôle RTSP) ; `hse`+`admin` (acquitter/résoudre).

## 3. Périmètre

**Dans cet incrément :** `authApi`, helpers token + `authFetch`, `AuthProvider`/`useAuth`, page
`/login`, redirection via `Shell`, gating par rôle (RTSP, éditeur de zones, actions ack),
badge utilisateur + déconnexion dans `NavRail`.
**Hors périmètre :** auth des reads + du WS, refresh token, inscription (users seedés env).

## 4. Couche données

### `lib/http.ts` (extension)
```ts
getToken() / setToken(t) / clearToken()      // localStorage "argus.token", try/catch
authFetch(url, init?) : Promise<Response>     // ajoute Authorization: Bearer <token> si présent
```

### `lib/authApi.ts`
```ts
type AuthUser = { username: string; role: "admin" | "hse" | string };
login(username, password, fetchFn=fetch) : Promise<{ access_token: string; role: string }>  // POST /auth/login
me(fetchFn=authFetch) : Promise<AuthUser>                                                    // GET /auth/me
```

### Appels protégés → `authFetch` par défaut
`setEventStatus`, `putZones`, `startRtsp`, `stopRtsp` : défaut `fetchFn = authFetch`.
Les reads (`getEvents`, `getStats`, `getZones`) restent en `fetch` nu.

## 5. Contexte d'auth

### `components/auth/AuthProvider.tsx` ("use client")
- Contexte `{ user: AuthUser | null, ready: boolean, login(u,p), logout() }`.
- `AuthProvider({ children, loadMe=me, doLogin=login })` (loaders **injectables** pour les tests).
- Au montage : `loadMe()` → succès ⇒ `user`, `ready=true` ; échec (401) ⇒ `user=null`, `ready=true`.
- `login(u,p)` : `doLogin` → `setToken(access_token)` → `loadMe()` → `user`.
- `logout()` : `clearToken()` → `user=null`.
- `useAuth()` : contexte ; **défaut hors provider** = `{ user:null, ready:true, login,logout }`
  (pour que les tests unitaires de composants ne cassent pas).

### `app/layout.tsx`
Envelopper `{children}` dans `<AuthProvider>` (composant client dans un layout serveur — OK).

## 6. Protection des routes — `Shell`

`Shell` devient `"use client"` :
```
const { user, ready } = useAuth();
const router = useRouter();
useEffect(() => { if (ready && !user) router.push("/login"); }, [ready, user]);
if (!ready || !user) return null;    // évite un flash avant redirection
return <div grid…><NavRail active user/><…>{children}</…></div>;
```
`/login` n'utilise pas `Shell` (non protégée).

### `app/login/page.tsx` ("use client")
Formulaire username+password → `useAuth().login(u,p)` → succès : `router.push("/")` ; échec :
message d'erreur.

## 7. Gating par rôle

- **`Dashboard`** : `const { user } = useAuth();` → `RtspControl` rendu seulement si
  `user?.role === "admin"` ; `onSetStatus` passé à `JournalTable` seulement si `user` peut
  acquitter (`role ∈ {hse, admin}`).
- **`Workspace`** (console) : `onEditZones` passé à `FilterBar` seulement si `user?.role ===
  "admin"` (sinon le bouton « Éditer les zones » disparaît — `FilterBar` inchangé).
- **`NavRail`** : en bas, badge `user.username` + bouton **Déconnexion** (`logout()`), masqués si
  `!user` ou `user.username === "system"`.

## 8. Fichiers

```
frontend/lib/http.ts                    (+ token + authFetch)
frontend/lib/authApi.ts                 (+ .test.ts)
frontend/components/auth/AuthProvider.tsx  (+ .test.tsx)
frontend/app/layout.tsx                 (AuthProvider)
frontend/app/login/page.tsx
frontend/components/console/Shell.tsx    (client + redirect)  (+ Shell.test.tsx)
frontend/components/console/NavRail.tsx  (badge user + logout)
frontend/components/console/Workspace.tsx (gating onEditZones)
frontend/components/dashboard/Dashboard.tsx (gating RtspControl + ack)
frontend/lib/eventsApi.ts, zonesApi.ts, sourcesApi.ts  (authFetch par défaut sur les writes)
frontend/vitest.setup.ts                (mock next/navigation useRouter)
frontend/app/console.test.tsx           (wrap Page dans AuthProvider admin)
```

## 9. Tests (TDD)

- **`authApi`** : `login` → `POST /auth/login` body+parse ; `me` → `GET /auth/me` avec token.
- **`AuthProvider`** : `loadMe` renvoie un user → `useAuth().user` défini, `ready` ; `login`
  injecté → stocke token + set user ; `logout` → user null.
- **`Shell`** : sans user (loadMe 401) → appelle `router.push("/login")` (router mocké) ; avec
  user admin → rend le shell + `NavRail`.
- **gating** : `Dashboard` avec user `hse` → pas de `RtspControl` ; user `admin` → présent.
- **existant** : `console.test` adapté (Page enveloppée dans `AuthProvider` admin injecté) ;
  `NavRail.test`, `Dashboard.test`, etc. restent verts (contexte par défaut). Build OK.

## 10. Critères d'acceptation

1. Auth backend activée : sans token, `/` et `/dashboard` redirigent vers `/login` ; après login,
   l'app s'affiche et les appels protégés portent le token.
2. Auth backend désactivée : l'app s'affiche sans login (via `/auth/me` = 200).
3. Rôle `hse` : pas d'édition de zones ni de contrôle RTSP ; peut acquitter. Rôle `admin` : tout.
4. Déconnexion vide le token et ramène au login.
5. Zéro nouvelle dépendance ; suites existantes vertes ; build OK.
