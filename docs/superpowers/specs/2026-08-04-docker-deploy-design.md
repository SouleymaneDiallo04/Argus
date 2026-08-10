# Docker — Conteneurisation & orchestration — Design

**Date :** 2026-08-04
**Contexte :** clôture V1 (§ « Docker » du cahier des charges). Sous-projet indépendant.
**Statut :** validé

## 1. Objectif

Rendre Argus **reproductible et déployable en une commande** : images Docker pour le backend
(FastAPI + modèle) et le frontend (Next.js), orchestrées par `docker compose`, avec
persistance des preuves et de la base entre redémarrages.

## 2. Décisions de conception (validées)

- **CPU-only** : torch CPU (pas de CUDA/nvidia) — tourne partout, image ~1-1,5 Go. GPU = V2.
- **`best.pt` (6 Mo) copié dans l'image backend** — image self-contained, pas de montage requis.
- **Frontend Next.js `output: "standalone"`** → runtime `node:20-slim` léger.
- **Un volume nommé `argus-data`** monté sur `/data` (persiste `argus.db` + `snapshots/`).
- **OpenCV** satisfait par libs système (`libgl1`, `libglib2.0-0`) — `requirements.txt`
  inchangé.

## 3. Périmètre

**Dans ce sous-projet :**
- `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`.
- `next.config.ts` : `output: "standalone"`.
- `.dockerignore` (racine + `frontend/`).
- `README` : section « Lancer avec Docker ».

**Hors périmètre :** support GPU (CUDA/nvidia runtime), image de prod signée + push registre,
TLS/reverse-proxy, healthchecks compose avancés → V2.

## 4. Image backend (`backend/Dockerfile`)

Contexte de build = **racine du repo** (pour accéder à `backend/` **et** `best.pt`).
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./requirements.txt
# torch CPU d'abord -> ultralytics le voit déjà satisfait (évite le wheel CUDA ~2 Go)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY best.pt /app/best.pt
ENV ARGUS_MODEL_PATH=/app/best.pt \
    ARGUS_DB_PATH=/data/argus.db \
    ARGUS_SNAPSHOT_DIR=/data/snapshots
EXPOSE 8000
CMD ["uvicorn", "--factory", "app.api.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
```

## 5. Image frontend (`frontend/Dockerfile`, multi-stage)

Contexte de build = `./frontend`. Requiert `output: "standalone"` dans `next.config.ts`.
```dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_ARGUS_API=http://localhost:8000
ENV NEXT_PUBLIC_ARGUS_API=$NEXT_PUBLIC_ARGUS_API
RUN npm run build

FROM node:20-slim AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```
*(Le `COPY public` n'est présent que si `frontend/public/` existe ; sinon retiré.)*
`NEXT_PUBLIC_ARGUS_API` est inliné au build : le **navigateur** joint le backend publié sur
l'hôte (`http://localhost:8000`), pas le nom de service compose.

## 6. Orchestration (`docker-compose.yml`)
```yaml
services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports: ["8000:8000"]
    environment:
      - ARGUS_CORS_ORIGINS=http://localhost:3000
    volumes:
      - argus-data:/data
  frontend:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_ARGUS_API: http://localhost:8000
    ports: ["3000:3000"]
    depends_on: [backend]
volumes:
  argus-data:
```

## 7. Hygiène — `.dockerignore`

Racine :
```
**/__pycache__/
**/*.pyc
.git/
.github/
docs/
*.db
*.db-wal
*.db-shm
snapshots/
*.log
.venv/
backend/.pytest_cache/
frontend/node_modules/
frontend/.next/
```
`frontend/.dockerignore` : `node_modules/`, `.next/`, `Dockerfile`.

## 8. Vérification (config, pas de TDD unitaire)

1. `docker compose build` réussit (backend + frontend).
2. `docker compose up -d` ; `curl http://localhost:8000/health` → `{"status":"ok","model_loaded":true}`.
3. `curl -sI http://localhost:3000` → 200 ; le dashboard `/dashboard` se charge.
4. Redémarrage (`docker compose restart backend`) : les preuves/DB persistent (volume `argus-data`).

*(Réalisée manuellement — Docker est dispo dans l'environnement, je build/up moi-même.)*

## 9. Critères d'acceptation

1. `docker compose build` produit deux images sans erreur (backend CPU ~1-1,5 Go).
2. `docker compose up` sert le backend (:8000, modèle chargé) et le frontend (:3000).
3. La chaîne fonctionne de bout en bout via les conteneurs (WS, journal, preuves, rapports).
4. `argus.db` + `snapshots/` persistent dans le volume `argus-data`.
5. Suites unitaires existantes inchangées (aucune modif de code applicatif, sauf
   `next.config.ts` standalone). README documente le lancement Docker.
