# V1.5 — Contrôle RTSP depuis l'UI — Design

**Date :** 2026-08-31
**Phase :** V1.5 (durcissement) — second incrément.
**Dépend de :** RTSP backend (endpoints `POST/DELETE/GET /sources/rtsp`, mergés). Tout sur `main`.
**Statut :** validé

## 1. Objectif

Rendre le flux RTSP **pilotable depuis le dashboard** (démarrer / arrêter / voir le statut) au
lieu de `curl` uniquement. Sous-projet **100 % frontend** — le backend est déjà en place.

## 2. Décisions de conception (validées)

- **Placement** : bandeau compact en haut du **dashboard** (au-dessus des KPI) — co-localisé
  avec les résultats RTSP (journal, stats, preuves).
- **Polling léger** du statut (~5 s) + rafraîchi après chaque action.
- **Source unique** (limite V1) : un seul flux ; démarrer remplace.
- Réutilise le pattern `zonesApi` (`fetchFn` injectable) et les tokens du design system.

## 3. Périmètre

**Dans ce sous-projet :** `lib/sourcesApi.ts` + `components/dashboard/RtspControl.tsx` + intégration
dans `Dashboard`.
**Hors périmètre :** multi-source simultané (V2), auth, contrôle depuis la console live.

## 4. Couche données — `lib/sourcesApi.ts`

```ts
type RtspStatus = { running: boolean; url?: string; frames?: number; error?: string | null };
startRtsp(url: string, fetchFn=fetch): Promise<RtspStatus>   // POST /sources/rtsp {url}
stopRtsp(fetchFn=fetch): Promise<void>                        // DELETE /sources/rtsp
rtspStatus(fetchFn=fetch): Promise<RtspStatus>               // GET /sources/rtsp
```
`API = NEXT_PUBLIC_ARGUS_API` (via `lib/http`). Rejette sur erreur HTTP (sauf que `rtspStatus`
renvoie simplement l'objet).

## 5. Composant — `components/dashboard/RtspControl.tsx` ("use client")

- État : `url` (input contrôlé), `status: RtspStatus`, `busy`.
- Au montage : `load()` = `rtspStatus()` → `setStatus`. `setInterval(5000)` (pause si
  `document.hidden`) → `load()`.
- **Démarrer** : `startRtsp(url)` puis `load()` ; visible si `!status.running`.
- **Arrêter** : `stopRtsp()` puis `load()` ; visible si `status.running`.
- **Statut** : point coloré + texte — « En cours · N frames · <url> » (vert) ou « Arrêté »
  (gris) ; ligne d'erreur si `status.error`.
- Loaders injectables (props `loadStatus`/`onStart`/`onStop` avec défauts) pour les tests.

Signature :
```ts
RtspControl({ loadStatus?, doStart?, doStop? }: {
  loadStatus?: typeof rtspStatus; doStart?: typeof startRtsp; doStop?: typeof stopRtsp;
})
```

## 6. Intégration — `Dashboard.tsx`

Ajouter `<RtspControl />` en tête du conteneur, **avant** `<DashboardFilters />`. Aucun autre
changement (le RTSP alimente déjà le journal/stats via le polling existant du dashboard).

## 7. Fichiers

```
frontend/lib/sourcesApi.ts   (+ sourcesApi.test.ts)
frontend/components/dashboard/RtspControl.tsx   (+ RtspControl.test.tsx)
frontend/components/dashboard/Dashboard.tsx     (ajout <RtspControl/>)
```

## 8. Tests (TDD)

- **`sourcesApi`** : `startRtsp` → `POST /sources/rtsp` méthode+body `{url}` ; `stopRtsp` →
  `DELETE` ; `rtspStatus` → parse `{running,...}` (fetch mocké).
- **`RtspControl`** : rend le champ + « Démarrer » quand arrêté ; saisir une URL + cliquer
  Démarrer appelle `doStart(url)` ; quand `loadStatus` renvoie `running:true`, affiche « En
  cours » + le bouton « Arrêter » (loaders injectés).
- Suites existantes vertes (frontend **48**) ; `npm run build` OK.

## 9. Critères d'acceptation

1. Le dashboard affiche un contrôle RTSP (URL + Démarrer/Arrêter + statut).
2. Démarrer lance le flux serveur (POST) ; Arrêter le stoppe (DELETE) ; le statut se met à jour
   (polling + après action).
3. Zéro nouvelle dépendance ; suites existantes vertes ; build OK.
