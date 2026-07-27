# P2-a — Frontend « Argus Ops Console » (UI de monitoring live) — Design

> **Auteur :** Souleymane Diallo · **Date :** 2026-07-27 · **Phase :** P2-a

## Objectif

Construire l'interface web qui rend Argus **démontrable** : un poste de supervision HSE temps réel, de qualité **enterprise / SCADA** (pas académique), qui consomme le service P1b (WebSocket d'inférence + REST des zones). Source vidéo → détections + conformité → overlays + file d'alertes priorisée + éditeur de zones.

## Périmètre

**Dans P2-a** *(tout est supporté par P1b aujourd'hui)* :
- Sources vidéo **webcam** (`getUserMedia`) + **fichier uploadé**, échantillonnées côté navigateur.
- Streaming des frames vers `WS /ws/stream`, rendu des **overlays de détection** (boîtes personnes vert/rouge, EPI, polygones de zones).
- **Conformité par personne** (roster live) + **file d'alertes priorisée** (sévérité × risque de zone).
- **Éditeur de zones** (polygones + EPI requis) → `PUT /zones`.
- **Filtres** live (zone / type d'EPI / statut) + recherche.
- Design system complet (le socle réutilisable pour toute la suite).

**Hors P2-a → P2-b (après P3)** : dashboard historique, courbes de conformité dans le temps, snapshots floutés, exports PDF/CSV, notifications, auth/rôles, multi-site persistant. La file d'alertes de P2-a est **live only** (pas d'historique persistant).

**Hypothèse V1 :** un seul flux actif (une caméra), cohérent avec P1b.

## Architecture

`Next.js (App Router, TypeScript)` ↔ `Backend FastAPI (P1b)`.

**Flux de données :**
```
webcam / fichier vidéo
  -> <video> (masqué) -> échantillonnage canvas ~6-8 i/s -> JPEG base64
  -> WS /ws/stream  { frame, timestamp }
  <- { detections, results, events }
  -> rendu overlays (canvas superposé à la vidéo) + roster + file d'alertes
Config des zones : éditeur -> PUT /zones ; chargement -> GET /zones
```

- **Frame transport :** identique au contrat P1b — `{ frame: <jpeg base64>, timestamp: <float> }` → `{ detections:[{cls,bbox:[x1,y1,x2,y2],confidence,track_id}], results:[{track_id,zone,required,present,missing,compliant}], events:[...] }`.
- **Échantillonnage :** un `<video>` (webcam ou fichier) est dessiné périodiquement sur un canvas off-screen → `toDataURL('image/jpeg', q)` → envoi WS. Cadence réglable (défaut ~7 i/s) pour tenir la latence CPU.
- **Rendu :** un canvas d'overlay **superposé** à la vidéo (mêmes dimensions), redessiné à chaque réponse WS. La vidéo n'est jamais renvoyée par le serveur — le front l'affiche localement et dessine les boîtes par-dessus.
- **Priorisation (côté frontend) :** le backend émet des `events` bruts ; **le front calcule la sévérité** = f(risque de zone, type d'EPI manquant) pour trier/colorer la file. Le **risque de zone** est un attribut géré côté front (réglé dans l'éditeur de zones, persisté en `localStorage` pour V1) — **aucun changement du modèle `Zone` du backend**.

**Dépendance backend (petite addition P1b) :** ajouter le **CORS** (`fastapi.middleware.cors.CORSMiddleware`) pour que le navigateur (origine `localhost:3000`) puisse appeler `GET/PUT /zones`. Origines configurables par variable d'env. C'est la seule modif backend de P2-a.

## Design system — « Argus Ops Console »

Référence visuelle : maquette console validée (dark control-room, type SCADA). **Rigueur = le luxe** : discipline, densité maîtrisée, couleur fonctionnelle.

### Logo
**L'Objectif-Œil** — œil dont l'iris est un diaphragme d'objectif. Wordmark **ARGUS · HSE VISION**. Bleu ISO « obligation ». Fournir SVG mark + lockups (horizontal, vertical, favicon, monochrome noir/inversé).

### Palette (graphite instrument, sémantique ISO 7010 stricte)
Chaque couleur a un **rôle fixe** — jamais décorative.
- Fond `#0B0D12` · surfaces `#111419`/`#161A22`/`#1D222C` · hairlines `rgba(255,255,255,.065/.11)`.
- Texte `#EDEFF4` / `#98A0B2` / `#5E6779`.
- **Bleu obligation/interactif (marque)** `#3B82F6` (ISO mandatory) — nav active, focus, actions.
- **Critique** `#F0464B` (rouge ISO) · **Attention** `#F5A524` (ambre) · **Conforme** `#31C46F` (vert) · **Neutre/inactif** `#6B7488`.
- Sévérité (file d'alertes) : Critique (rouge) › Élevé (ambre) › Moyen (bleu) › Faible (slate).

### Typographie (hiérarchie fonctionnelle — la taille encode l'importance)
**IBM Plex Sans** (UI, auto-hébergé) + **IBM Plex Mono** (données : IDs, temps, %, compteurs — `tabular-nums`). Échelle : Vital 34 mono › Section 15/700 › Ligne 13/600 › Méta 12 › Label 10.5 uppercase `.12em`.

### Système de composants (traitement identique partout, réutilisables)
`Logo` · `SeverityTag` (Critique/Élevé/Moyen/Faible) · `StatusBadge` (Active/Acquittée/Résolue) · `PpeChip` · `Button` (primary/ghost/danger) · `MetricTile` · `AlertRow` · `FilterControl` · `ComplianceRosterRow` · `VitalStrip`. Coins nets, pas de glow/glassmorphism.

### Layout (multi-écran)
Rail de nav (icônes : Live / Alertes / Zones / Sites / Analytique) · **bandeau vital** (signature : conformité du site + sparkline live + tallies) · barre de filtres · espace de travail = **flux live** (gauche) + **file d'alertes priorisée dense** (droite). Responsive : le rail se replie (tablette), la file passe en pleine largeur (mur d'écran ≥ 1440px). Doit rester lisible **plein de données** (dizaines de lignes), pas seulement avec 3 exemples.

### Motion (fonctionnel uniquement)
Live only : pouls LIVE, point de sparkline, insertion/flash d'alerte, transitions d'état (hover/focus). Durées 150-300ms. **Zéro animation décorative.** `prefers-reduced-motion` coupe tout.

### Accessibilité (usage prolongé, contexte industriel)
Contraste fort (texte primaire ≥ 7:1 sur graphite), **couleur jamais seule** (tag texte + forme + position), focus visible partout, navigation clavier, `aria-live` sur la file d'alertes, cibles ≥ 40px.

## Fonctionnalités P2-a (détaillées)

1. **Sélection de source** : webcam (permission) ou upload d'un fichier vidéo ; bouton Démarrer/Arrêter.
2. **Flux live + overlays** : boîtes personnes (vert conforme / rouge infraction), boîtes EPI, polygones de zones ; HUD (caméra, timestamp, i/s, latence).
3. **Roster de conformité** (live) : par `track_id` — EPI présents/manquants (chips), statut ; un état **ambre « en confirmation »** reflète le debounce (event pas encore confirmé).
4. **File d'alertes priorisée** : chaque `event` confirmé devient une ligne (sévérité, temps, zone, ID, EPI manquants, statut) ; triée par sévérité × risque de zone ; nouvelle alerte flashée ; actions Acquitter/Résoudre (état local V1).
5. **Bandeau vital** : taux de conformité courant du flux + sparkline (fenêtre glissante en mémoire) + compteurs Critique/Attention/Conforme.
6. **Éditeur de zones** : mode dessin de polygones sur la vidéo (clic = point, fermeture), nommage, choix des **EPI requis** (multi-select) et du **risque de zone** (faible/moyen/élevé) ; sauvegarde → `PUT /zones` (le risque reste côté front).
7. **Filtres & recherche** : zone / type d'EPI / statut (Actives/Acquittées/Résolues) + recherche par ID ; appliqués en direct sur roster + file.

## Stack technique

Next.js (App Router) · TypeScript · **Tailwind CSS** (tokens du design system en variables CSS) · primitives **shadcn/ui** (Radix) pour dropdown/dialog/select accessibles · **Canvas 2D** pour overlays + éditeur de zones · client WS natif. Pas de librairie de charts en P2-a (la sparkline vitale = SVG/canvas maison léger).

## Tests

- **Composants du design system** (`SeverityTag`, `StatusBadge`, `AlertRow`, priorisation…) : tests unitaires (Testing Library) — rendu + états.
- **Logique de priorisation** (sévérité = f(risque, EPI)) : fonction pure testée.
- **Client WS / échantillonnage** : logique isolée et testée avec un WS mocké (pas de vrai backend en test).
- Pas de dépendance à un backend réel ni au modèle YOLO dans la suite de tests front.

## Frontières & DRY

Le frontend vit dans `frontend/` (vierge aujourd'hui). Il consomme le contrat P1b **inchangé** (sauf ajout CORS). Toute la logique métier reste au backend ; le front ne fait que **capturer → streamer → afficher → configurer les zones**, et calcule la **priorisation d'affichage** (concern purement front). Le design system (tokens + composants) est le socle réutilisé par P2-b/P3.
