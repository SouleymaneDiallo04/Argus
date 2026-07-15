# Argus — Détection d'EPI sur chantier & conformité HSE

> Spec de conception (V1 « fondation complète »). Document autoporteur : conçu pour qu'un assistant reprenant le projet de zéro comprenne le périmètre et puisse aider à le réaliser.
>
> **Auteur :** Souleymane Diallo · **Date :** 2026-07-15 · **Working name :** Argus

---

## 1. Contexte & problème

Les accidents du travail coûtent des vies, des arrêts de production, des primes d'assurance, et engagent la **responsabilité pénale** de l'employeur. Le contrôle du port des équipements de protection individuelle (EPI) est aujourd'hui **manuel, ponctuel et non traçable**.

**Argus** détecte en temps réel le port des EPI sur des flux vidéo de chantiers/usines, évalue la conformité par zone, **alerte** en cas de manquement et **conserve une preuve** (dans le respect du RGPD). Il répond à un besoin HSE réel, réglementaire et assurantiel.

**Positionnement portfolio :** projet phare démontrant la double compétence IA (computer vision, MLOps) + web (full-stack), sur l'angle industriel de l'auteur. Non générique grâce à la logique métier (association personne-EPI, zones, anti-faux-positifs, RGPD) et à la rigueur d'évaluation.

## 2. Objectifs & non-objectifs

**Objectifs V1**
- Détecter 6 EPI + personne, de façon robuste et honnêtement évaluée.
- Associer chaque EPI à la bonne personne, évaluer la conformité selon des zones à règles.
- Alerter en temps réel (dashboard + email/Telegram) avec anti-faux-positifs.
- Conserver des preuves floutées (RGPD), produire des rapports HSE (PDF/CSV).
- Fonctionner sur webcam, vidéo, ou **1 flux RTSP** (vraie caméra IP), dockerisé.

**Non-objectifs V1 (documentés comme vision, voir §12)**
- Multi-caméras simultanées, re-identification inter-caméras.
- SaaS multi-utilisateurs, auth/rôles avancés, plannings de règles.
- MLOps continu (monitoring de drift, réentraînement automatique).
- Certification industrielle terrain (nécessite données du site cible).

**Caveat d'honnêteté :** V1 vise une solution **robuste, complète et rigoureusement évaluée** qui démontre la bonne méthodologie opérationnelle — pas un système certifié terrain, qui exigerait des milliers d'images du site cible et un cycle MLOps continu.

## 3. Angles différenciateurs de l'auteur à exploiter
- IA industrielle / HSE (angle rare).
- IA souveraine / locale possible (inférence CPU, pas de dépendance cloud obligatoire).
- Rigueur : évaluation cross-dataset, métriques par classe, tests unitaires de la logique.

## 4. Architecture

Trois composants à responsabilité unique, testables isolément.

**1. Modèle de détection** — YOLOv8 entraîné sur données EPI fusionnées (Colab, GPU gratuit), exporté `.pt` + `.onnx`. Développé dans des notebooks pédagogiques exécutés par l'auteur.

**2. Service d'inférence FastAPI (Python)** — le cerveau métier :
- WebSocket : reçoit une image, lance YOLO (+ tracking), renvoie les détections JSON.
- Logique métier : association EPI↔personne, appartenance aux zones, évaluation de conformité, machine à états du debounce, génération d'événements.
- Floutage des visages **côté serveur** avant tout stockage de preuve.
- REST : config zones/règles, journal d'événements, statistiques, rapports.
- Stockage SQLite (événements + config) + snapshots d'infraction floutés.
- Notifications : email / Telegram / webhook.

**3. Frontend Next.js** — l'interface :
- Source : webcam, vidéo uploadée, ou flux RTSP.
- Envoie les frames échantillonnées (~5-8 img/s) au WebSocket, dessine les overlays (boîtes + statut de conformité par personne).
- Éditeur de zones (polygones) + choix des EPI obligatoires par zone.
- Dashboard : taux de conformité (global / par zone / dans le temps), journal d'infractions avec snapshot flouté, filtres, export de rapports.

**Flux de données**
```
webcam / vidéo / RTSP
  -> Next.js échantillonne les frames
  -> WebSocket
  -> FastAPI : YOLO -> tracking -> association -> règles de la zone -> conformité -> debounce -> événements
  -> JSON renvoyé
  -> Next.js : overlays + floutage à l'affichage
  -> si infraction confirmée : événement + snapshot flouté persistés -> dashboard mis à jour + notification
```

**Transport temps réel :** le navigateur envoie les frames au backend via WebSocket et reçoit des détections structurées (JSON). Le backend garde toute la logique métier (testable en Python) ; le front reste léger et interactif (overlays, zones).

**Performance :** inférence CPU avec YOLOv8n, frames échantillonnées pour tenir la latence. Résolution d'entraînement plus élevée possible (ex. 960 px) pour les petits objets, avec compromis vitesse assumé.

## 5. Classes détectées

EPI : `helmet` (casque), `safety-vest` (gilet), `mask` (masque), `gloves` (gants), `glasses` (lunettes), `shoes` (chaussures/bottes).
Support : `person`, `head`/`face` (association + floutage RGPD).

**Caveat chaussures :** la vision confirme la présence de chaussures mais ne distingue pas des bottes *certifiées* de sécurité — documenté clairement.

## 6. Données & robustesse

**Diversité / généralisation — fusion multi-datasets.** SH17 (base, 17 classes dont gants/lunettes/chaussures) + CHV + Construction Site Safety (css-data) + Pictor-PPE. Impose une **harmonisation des labels** (script de mapping des schémas hétérogènes vers notre taxonomie) — vrai travail d'ingénierie data.

**Test de généralisation honnête.** Set de test issu d'une source **différente** de l'entraînement (éval cross-dataset) + test sur une **vidéo propre** de l'auteur.

**Déséquilibre des classes** (gants/lunettes/chaussures = petits objets rares) :
- Échantillonnage équilibré (suréchantillonner images à classes rares).
- Augmentation ciblée (copy-paste des classes rares, jitter éclairage/HSV, flou de mouvement, occlusions — Albumentations).
- Résolution d'entrée plus haute pour petits objets.
- Métriques **par classe** pour concentrer l'effort là où c'est faible.

**Stratégie d'annotation (staged, validée) :**
- **V1 :** datasets publics fusionnés/harmonisés + augmentation + éval cross-dataset, **sans** annotation manuelle.
- **V1.5 :** boucle **active-learning** ciblée — entraîner un 1er modèle → pré-annoter de nouvelles images (captation propre, images web) → **corriger** uniquement (assisté SAM) → cibler les classes faibles et cas d'échec. Outils : CVAT / Label Studio / Roboflow.

## 7. Logique métier (testable en Python pur)

- **Tracking** : ByteTrack (intégré Ultralytics) → IDs stables par personne.
- **Association EPI↔personne** : rattachement par géométrie (contenu / IoU dans la boîte personne) + a priori corporels (casque↔tête, lunettes/masque↔visage, gilet↔torse, gants↔mains, chaussures↔bas). Cas ambigus → personne la plus proche.
- **Appartenance à une zone** : point au sol = bas-centre de la boîte personne → test point-dans-polygone. La personne hérite des EPI requis de sa zone.
- **Conformité** : par personne → tous les EPI requis présents ? sinon `non-conforme` + liste des manquants.
- **Debounce temporel (anti-faux-positifs)** : infraction confirmée seulement après N secondes d'anomalie continue (par ID) ; effacée après M secondes de conformité ; **cooldown** pour éviter le spam.
- **Événement** : `{horodatage, zone, EPI manquants, caméra, snapshot flouté}`.
- **RGPD** : floutage têtes/visages côté serveur avant stockage + envoi au front pour l'affichage live ; snapshots de preuve toujours floutés.

## 8. Évaluation (ce qui impressionne)

**Modèle :** mAP@50 et mAP@50-95 **par classe**, courbes PR, matrice de confusion, **test cross-dataset**, test sur vidéo propre, galerie de cas d'échec. Rapport d'évaluation + notebook.

**Logique métier :** tests unitaires **pytest** (association, appartenance aux zones, conformité, machine à états du debounce) — fonctions déterministes, sans le modèle.

## 9. Stack technique

- Vision / entraînement : Ultralytics YOLOv8, PyTorch, Albumentations, Google Colab (GPU).
- Inférence : ONNX Runtime / PyTorch CPU, OpenCV, ByteTrack.
- Backend : FastAPI (WebSocket + REST), SQLite, ReportLab (PDF), smtplib / API Telegram.
- Frontend : Next.js, canvas pour overlays et éditeur de zones.
- Déploiement : Docker + docker-compose.

## 10. Livrables

- Notebooks Colab : préparation/fusion des données, entraînement, évaluation.
- Backend FastAPI (inférence + logique + SQLite + alertes + rapports).
- Frontend Next.js (vidéo/webcam/RTSP, overlays, éditeur de zones, dashboard).
- `docker-compose.yml`.
- `README` (métriques par classe + vidéo démo de 90 s).
- `DECISIONS.md` (justification des choix techniques).

## 11. Structure du dépôt (nouveau repo dédié `argus/`)

```
argus/
  notebooks/        # data prep, training, evaluation (Colab)
  backend/
    app/            # FastAPI : ws, rest, logique métier
    models/         # poids exportés (.onnx)
    tests/          # pytest logique métier
  frontend/         # Next.js
  data/             # scripts de fusion/harmonisation des datasets
  docker/           # Dockerfiles + docker-compose
  docs/             # cette spec, DECISIONS.md, rapport d'éval
```

## 12. Périmètre & roadmap (phases)

**V1 (cette spec) :** détection 6 EPI robuste · tracking · zones/règles · conformité anti-faux-positifs · alertes dashboard+email/Telegram · preuves floutées RGPD · dashboard+rapports PDF · webcam/vidéo/1 RTSP · Docker.

**V2 :** multi-caméras simultanées · escalade d'alertes/sévérité · auth + rôles (admin/HSE) · plannings horaires des règles · politique de rétention/audit · API d'intégration/webhooks · tendances & KPIs avancés.

**V3 :** re-identification inter-caméras · découverte ONVIF · edge (Jetson)/scalabilité GPU multi-flux · monitoring de drift + réentraînement automatique.

## 13. Sous-phases de construction de la V1

- **P0 — Données & modèle (Colab)** : fusion/harmonisation → entraînement YOLOv8 → éval par classe + cross-dataset → export ONNX.
- **P1 — Backend & logique** : FastAPI WS inférence + logique (association/zones/conformité/debounce) + tests unitaires, validé sur vidéo échantillon (script, sans front).
- **P2 — Frontend** : Next.js vidéo (webcam/upload/RTSP), overlays, éditeur de zones, dashboard live.
- **P3 — Alertes, RGPD, preuves, rapports** : floutage, événements+snapshots, notifications, rapports PDF, persistance.
- **P4 — Déploiement & vitrine** : Docker/compose, README, vidéo démo, DECISIONS.md.
- **P5 (option) — Active-learning** : annotation ciblée classes faibles → réentraînement → mesurer l'amélioration.

## 14. Risques & mitigations

| Risque | Mitigation |
|---|---|
| Précision faible sur gants/lunettes/chaussures | Augmentation ciblée, résolution ↑, active-learning P5, métriques par classe honnêtes |
| Faux positifs d'alertes | Debounce temporel + cooldown + tracking par ID |
| Latence CPU insuffisante | YOLOv8n, échantillonnage des frames, ONNX Runtime |
| Généralisation faible hors dataset | Fusion multi-datasets + test cross-dataset + vidéo propre |
| Conformité RGPD | Floutage systématique côté serveur avant stockage |

## 15. Critères de réussite V1

- Pipeline end-to-end fonctionnel : d'un flux vidéo à une alerte + preuve + rapport.
- Métriques par classe publiées honnêtement + test cross-dataset.
- Tests unitaires verts sur la logique métier.
- Démo reproductible (Docker) + vidéo de 90 s.
- `DECISIONS.md` justifiant les choix.
