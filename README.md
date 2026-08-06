# Argus — Détection d'EPI & conformité HSE par vision

> Système de vision par ordinateur qui détecte en temps réel le port des équipements de protection individuelle (EPI) sur chantiers et sites industriels, évalue la conformité par zone, alerte en cas de manquement et conserve une preuve dans le respect du RGPD.

**Statut :** 🚧 En conception / démarrage (V1). Voir la spec complète dans [`docs/argus-design.md`](docs/argus-design.md).

---

## Le problème

Les accidents du travail coûtent des vies, des arrêts de production, des primes d'assurance et engagent la responsabilité pénale de l'employeur. Le contrôle du port des EPI reste aujourd'hui **manuel, ponctuel et non traçable**. Argus le rend **continu, automatique et documenté**.

## La solution (V1)

- **Détection de 4 EPI** : casque, gilet, masque, chaussures (+ personne / tête). *Gants et lunettes : reportés en V2 via active-learning — objets minuscules, données publiques rares (choix documenté dans la spec).*
- **Suivi multi-personnes** (tracking) et **association EPI ↔ personne**.
- **Zones à règles** : chaque zone impose ses EPI obligatoires.
- **Conformité anti-faux-positifs** : confirmation temporelle avant toute alerte.
- **Alertes** temps réel : dashboard + email / Telegram.
- **Preuves floutées (RGPD)** : capture d'infraction avec floutage des visages côté serveur.
- **Dashboard & rapports** : taux de conformité par zone / caméra / temps, export PDF / CSV.
- **Sources** : webcam, vidéo, ou flux RTSP (caméra IP). Dockerisé.

## Architecture

```
webcam / vidéo / RTSP
  -> Frontend Next.js (échantillonne les frames)
  -> WebSocket
  -> Backend FastAPI : YOLOv8 -> tracking -> association -> règles de zone -> conformité -> debounce -> événements
  -> overlays + floutage à l'affichage
  -> infraction confirmée : événement + snapshot flouté + notification
```

Trois composants à responsabilité unique :
1. **Modèle** — YOLOv8 entraîné sur des datasets EPI fusionnés/harmonisés (entraînement Colab).
2. **Backend FastAPI** — inférence + logique métier + stockage + alertes + rapports.
3. **Frontend Next.js** — vidéo, overlays, éditeur de zones, dashboard.

## Stack

`YOLOv8 / PyTorch` · `ONNX Runtime` · `OpenCV / ByteTrack` · `FastAPI` · `SQLite` · `Next.js` · `Docker`

## Lancer avec Docker

Prérequis : Docker + Docker Compose. Le modèle `best.pt` doit être présent à la racine du dépôt.

```bash
docker compose up --build
```

- Console : http://localhost:3000
- Dashboard : http://localhost:3000/dashboard
- API : http://localhost:8000 (`/health`, `/events`, `/stats`, `/reports/events.csv`, `/reports/summary.pdf`)

Les preuves floutées (RGPD) et la base SQLite sont persistées dans le volume `argus-data`
(monté sur `/data` dans le conteneur backend) — elles survivent à `docker compose down`.
Images **CPU-only** (aucun GPU requis).

Notifications (optionnel) : ajouter `ARGUS_TEAMS_WEBHOOK`, `ARGUS_SMTP_*` et `ARGUS_PUBLIC_URL`
dans la section `environment` du service `backend` de `docker-compose.yml`.

## Structure du dépôt

```
argus/
  notebooks/   # préparation des données, entraînement, évaluation (Colab)
  backend/     # FastAPI : inférence, logique métier, tests
  frontend/    # Next.js : UI, overlays, éditeur de zones, dashboard
  data/        # scripts de fusion / harmonisation des datasets
  backend/Dockerfile · frontend/Dockerfile · docker-compose.yml
  docs/        # spec de conception, décisions, rapport d'évaluation
```

## Roadmap

- **V1 (en cours)** — détection 4 EPI, tracking, zones, conformité, alertes, RGPD, dashboard, rapports, RTSP, Docker.
- **V2** — gants & lunettes (active-learning), multi-caméras, escalade d'alertes, auth/rôles, plannings de règles, API d'intégration.
- **V3** — re-identification inter-caméras, edge (Jetson), monitoring de drift & réentraînement.

## Rigueur & évaluation

Métriques **par classe** (mAP@50, mAP@50-95), test **cross-dataset** (généralisation honnête), tests unitaires de la logique métier. Rapport complet : [`docs/model-evaluation.md`](docs/model-evaluation.md).

**Détecteur YOLOv8n — val interne, mAP@50 par classe :**

| person | helmet | safety-vest | mask | shoes | **all** |
|---|---|---|---|---|---|
| 0.888 | 0.886 | 0.794 | 0.761 | 0.544 | **0.775** |

- **Généralisation cross-dataset** (holdout css-data, jamais entraîné) : all mAP@50 **0.624** → domain gap ~15 % relatif, *mesuré et publié* plutôt que masqué.
- **Amélioration ciblée de la classe faible `shoes`** (résolution 640→960 + oversampling) : mAP@50 **0.445 → 0.544 (+22 %)**, rappel **0.42 → 0.52 (+24 %)**, sans régression des autres classes.

## Auteur

**Souleymane Diallo** — élève ingénieur IA & Data Science (ENSAM Meknès).
Portfolio : https://jeuf-tech-portfolio.vercel.app/

---

*Projet à visée pédagogique et de démonstration. La détection confirme la présence des EPI mais ne distingue pas des équipements certifiés ; un déploiement industriel certifié nécessite des données du site cible et un cycle MLOps continu.*
