# P2-b — Dashboard « Analytique » — Design

**Date :** 2026-08-04
**Phase :** P2 (Frontend) — sous-projet **b** (dashboard)
**Dépend de :** P3-a (`/stats`, `/events`) et P3-b (`/events/{id}/snapshot`) — mergés (#8, #9).
**Statut :** validé

## 1. Objectif

Donner enfin un **consommateur visuel** au backend de journalisation : un tableau de bord
« Analytique » qui montre le **taux de conformité** (global / par zone / dans le temps) et le
**journal d'infractions** (avec vignette floutée), filtrable, rafraîchi automatiquement.

Répond au cahier des charges (§ ligne 57) : « Dashboard : taux de conformité (global / par
zone / dans le temps), journal d'infractions avec snapshot flouté, filtres, export de
rapports. »

## 2. Décisions de conception (validées)

- **Graphiques = SVG maison minimal** (courbe/aire + barres), alignés sur le design SCADA
  austère, zéro dépendance, zéro animation décorative.
- **Auto-refresh ~15 s** (polling de `/stats` et `/events`), avec indicateur « MAJ il y a … »
  et **pause quand l'onglet est caché**.
- **Routing réel** : nouvelle route `/dashboard` ; NavRail navigante (`Link`), état actif via
  **prop** (pas de `usePathname`, tests déterministes).
- **Sévérité calculée côté front** via `severityFor(riskOf(zone), missing)` — **même source
  que la console live** (`lib/zoneRisk.riskOf`, heuristique par nom, testable sans
  `localStorage`), cohérent avec la décision P3-a « pas de sévérité stockée ».
- **Export = stub** (bouton présent, génération réelle en P3-d).

## 3. Périmètre

**Dans P2-b :**
- Route `/dashboard` + `Shell` partagé + NavRail navigante.
- Clients REST `statsApi` / `eventsApi`.
- KPI, courbe de conformité, répartition par zone, journal filtrable avec vignette floutée.
- Polling 15 s.

**Hors P2-b :**
- Génération de rapports (PDF/CSV) → **P3-d** (bouton export inerte).
- Notifications → **P3-c**.
- Floutage du flux live → plus tard.

## 4. Architecture & routing

- Extraire **`components/console/Shell.tsx`** : grille `grid h-dvh grid-cols-[60px_1fr]` +
  `<NavRail active=… />` + un slot enfant (colonne de droite). `/` (Live) et `/dashboard`
  l'utilisent tous les deux.
- `app/page.tsx` → `<Shell active="live"><VitalStrip/><Workspace/></Shell>` (colonne droite
  en `grid-rows-[auto_1fr]`).
- `app/dashboard/page.tsx` → `<Shell active="analytique"><Dashboard/></Shell>`.
- **`NavRail`** devient client : items `Live` (`/`) et `Analytique` (`/dashboard`) en `Link`,
  actif si `active` correspond ; `Alertes`/`Zones`/`Sites` restent des boutons inertes.
  Signature : `NavRail({ active }: { active: "live" | "analytique" })`.

## 5. Couche données (pattern `zonesApi` réutilisé)

`API = process.env.NEXT_PUBLIC_ARGUS_API ?? "http://localhost:8000"`. `fetchFn` injectable.

### `lib/statsApi.ts`
```
type ZoneStat = { zone: string; person_frames: number; compliant_frames: number; rate: number | null };
type Bucket   = { bucket: string; person_frames: number; compliant_frames: number; rate: number | null };
type Stats = {
  global: { person_frames: number; compliant_frames: number; rate: number | null };
  by_zone: ZoneStat[];
  over_time: Bucket[];
  violations: { total: number; by_zone: Record<string, number> };
};
getStats(params?: { since?; until?; zone? }, fetchFn=fetch): Promise<Stats>
```

### `lib/eventsApi.ts`
```
type ApiEvent = { id: number; ts: string; stream_ts: number; camera: string;
                  zone: string | null; track_id: number; missing: string[]; snapshot: string | null };
getEvents(params?: { zone?; ppe?; since?; until?; limit? }, fetchFn=fetch): Promise<ApiEvent[]>
snapshotUrl(id: number): string            // `${API}/events/${id}/snapshot`
```

## 6. Composants

- **`components/dashboard/Dashboard.tsx`** (client) : polling 15 s (pause si `document.hidden`),
  état `stats`/`events`/`filters`/`lastUpdated`, assemble les sections. Injection possible des
  clients pour les tests (props `loadStats`/`loadEvents` avec défauts `getStats`/`getEvents`).
- **`components/dashboard/KpiRow.tsx`** : `MetricTile` × 4 (taux global %, infractions,
  zones actives, dernière MAJ).
- **`components/charts/ConformityTrend.tsx`** : SVG aire/ligne du taux (`over_time`), segments
  interrompus sur `rate: null`. S'appuie sur `lib/chart.ts`.
- **`components/charts/ZoneBreakdown.tsx`** : barres horizontales du taux par zone, couleur
  sémantique par seuil (`>=0.9` vert, `>=0.7` ambre, sinon rouge).
- **`components/dashboard/JournalTable.tsx`** : lignes = heure locale, zone, `#track_id`,
  `PpeChip` des EPI manquants, `SeverityTag` (via `severityFor(riskOf(zone), missing)`),
  vignette `<img src={snapshotUrl(id)}>` (ou tiret si `snapshot === null`).
- **`components/dashboard/DashboardFilters.tsx`** : zone (select), EPI (select), plage
  (`presets` : dernière heure / dernier jour / tout) → calcule `since`/`until` ISO.
- **`lib/chart.ts`** (pur, testable) : `scaleY(rate, height)`, `trendPoints(buckets, w, h)`
  (→ segments de polyline en sautant les `null`), `barWidth(rate, maxW)`.

## 7. Rafraîchissement

`Dashboard` : chargement au montage + `setInterval(15000)`. Handler `visibilitychange` :
saute le tick si `document.hidden`. `lastUpdated` (Date) alimente le KPI « MAJ il y a … ».
Les erreurs réseau sont avalées (garde les dernières données ; badge « hors ligne » optionnel).

## 8. Structure de fichiers

```
frontend/app/dashboard/page.tsx                 # route /dashboard
frontend/app/page.tsx                            # -> <Shell active="live">
frontend/components/console/Shell.tsx            # grille + NavRail (partagé)
frontend/components/console/NavRail.tsx          # navigante, prop `active`
frontend/components/dashboard/Dashboard.tsx
frontend/components/dashboard/KpiRow.tsx
frontend/components/dashboard/JournalTable.tsx
frontend/components/dashboard/DashboardFilters.tsx
frontend/components/charts/ConformityTrend.tsx
frontend/components/charts/ZoneBreakdown.tsx
frontend/lib/statsApi.ts   frontend/lib/eventsApi.ts   frontend/lib/chart.ts
+ tests co-localisés (*.test.ts / *.test.tsx)
```

## 9. Tests (TDD)

- **`statsApi`/`eventsApi`** : fetch mocké (comme `zonesApi.test`) — URL/params corrects,
  parsing, `snapshotUrl`.
- **`lib/chart.ts`** : `barWidth` proportionnel/clampé, `trendPoints` saute les `null`,
  `scaleY` borne 0..1.
- **`ConformityTrend`** : rend une `polyline`/`path` avec le bon nombre de points ; trou sur
  `null`.
- **`ZoneBreakdown`** : une barre par zone, couleur par seuil.
- **`JournalTable`** : une ligne par event, `SeverityTag` présent, `img src` = URL snapshot,
  tiret si `snapshot` null.
- **`NavRail`** : item actif surligné selon `active` ; liens `/` et `/dashboard`. (Mock
  `next/link` → `<a>` dans les tests si nécessaire.)
- **`Dashboard`** : monte les sections avec `loadStats`/`loadEvents` injectés (données factices).
- **`console.test`** : reste vert (NavRail prend `active="live"`, shell inchangé côté rendu).
- Suite frontend existante (**30**) reste verte ; `npm run build` OK.

## 10. Critères d'acceptation

1. `/dashboard` affiche KPI + courbe de conformité + barres par zone + journal filtrable.
2. Les données proviennent de `GET /stats` et `GET /events` ; les vignettes de
   `GET /events/{id}/snapshot`.
3. Filtres (zone / EPI / plage) rechargent le journal.
4. Auto-refresh ~15 s avec indicateur de fraîcheur ; pause si onglet caché.
5. NavRail navigue entre Live et Analytique, item actif correct.
6. Zéro nouvelle dépendance (charts SVG maison) ; suite frontend verte (30 + nouveaux) ;
   build OK.
