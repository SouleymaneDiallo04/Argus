# Docker — Conteneurisation & orchestration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lancer Argus (backend + frontend) en une commande `docker compose up`, avec preuves/DB persistées.

**Architecture:** Deux images (backend Python CPU-only avec modèle baké ; frontend Next.js standalone) orchestrées par `docker compose`, un volume nommé `argus-data` sur `/data`.

**Tech Stack:** Docker 29 + Compose v5 (dispo dans l'environnement), python:3.12-slim, node:20-slim, Next.js 16 standalone.

## Global Constraints

- **CPU-only** (torch CPU, pas de CUDA). **`best.pt` (6 Mo) copié dans l'image backend.**
- **Aucune modif de code applicatif** hors `next.config.ts` (`output: "standalone"`).
- `/data` doit **exister dans l'image backend** (`mkdir -p /data`) pour que `Journal`
  (`sqlite3.connect(/data/argus.db)`) et `SnapshotStore(/data/snapshots)` fonctionnent même
  sans volume monté.
- Vérification = **build + smoke test** (pas de TDD unitaire — c'est de la config). Docker est
  disponible : on build/up réellement.
- Contexte de build backend = **racine** (accès à `backend/` + `best.pt`) ; frontend = `./frontend`.
- `NEXT_PUBLIC_ARGUS_API=http://localhost:8000` (inliné au build ; le navigateur joint l'hôte).
- Commits conventionnels, anglais, **sans `Co-Authored-By`**. Branche : `feat/docker-deploy`.

---

### Task 1: Prérequis build — `next.config` standalone + `.dockerignore`

**Files:**
- Modify: `frontend/next.config.ts`
- Create: `.dockerignore`, `frontend/.dockerignore`

- [ ] **Step 1: Activer la sortie standalone** — `frontend/next.config.ts`
```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

- [ ] **Step 2: Créer `.dockerignore` (racine)**
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

- [ ] **Step 3: Créer `frontend/.dockerignore`**
```
node_modules/
.next/
Dockerfile
```

- [ ] **Step 4: Vérifier le build standalone** — `cd frontend && npm run build`
Expected: build OK et `frontend/.next/standalone/server.js` existe
(`ls .next/standalone/server.js`).

- [ ] **Step 5: Commit**
```bash
git add frontend/next.config.ts .dockerignore frontend/.dockerignore
git commit -m "build: Next standalone output + dockerignore"
```

---

### Task 2: Image backend (`backend/Dockerfile`)

**Files:**
- Create: `backend/Dockerfile`

- [ ] **Step 1: Écrire `backend/Dockerfile`**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./requirements.txt
# torch CPU d'abord -> ultralytics le voit satisfait (évite le wheel CUDA ~2 Go)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY best.pt /app/best.pt
RUN mkdir -p /data
ENV ARGUS_MODEL_PATH=/app/best.pt \
    ARGUS_DB_PATH=/data/argus.db \
    ARGUS_SNAPSHOT_DIR=/data/snapshots
EXPOSE 8000
CMD ["uvicorn", "--factory", "app.api.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Build l'image** (depuis la racine — plusieurs minutes à cause de torch)
Run: `docker build -f backend/Dockerfile -t argus-backend .`
Expected: build réussi.

- [ ] **Step 3: Smoke test du conteneur backend**
```bash
docker run --rm -d -p 8000:8000 --name argus-be-test argus-backend
# laisser ~15s charger le modèle
sleep 20 && curl -s http://localhost:8000/health
docker stop argus-be-test
```
Expected: `{"status":"ok","model_loaded":true}` (prouve que `/data` existe et que le modèle
charge dans le conteneur).

- [ ] **Step 4: Commit**
```bash
git add backend/Dockerfile
git commit -m "build: backend Docker image (CPU torch + baked model)"
```

---

### Task 3: Image frontend (`frontend/Dockerfile`)

**Files:**
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Écrire `frontend/Dockerfile`** (multi-stage)
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

- [ ] **Step 2: Build l'image**
Run: `docker build -t argus-frontend ./frontend`
Expected: build réussi (les 3 stages `standalone`/`static`/`public` copient sans erreur).

- [ ] **Step 3: Smoke test du conteneur frontend**
```bash
docker run --rm -d -p 3000:3000 --name argus-fe-test argus-frontend
sleep 5 && curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
docker stop argus-fe-test
```
Expected: `200`.

- [ ] **Step 4: Commit**
```bash
git add frontend/Dockerfile
git commit -m "build: frontend Docker image (Next standalone)"
```

---

### Task 4: Orchestration `docker-compose.yml` + vérification bout-en-bout

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Écrire `docker-compose.yml`**
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

- [ ] **Step 2: Build + up**
Run:
```bash
docker compose build
docker compose up -d
sleep 25
```
Expected: deux services démarrés.

- [ ] **Step 3: Smoke test bout-en-bout**
```bash
curl -s http://localhost:8000/health          # {"status":"ok","model_loaded":true}
curl -s http://localhost:8000/stats            # JSON stats (P3 présent)
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/dashboard   # 200
```
Expected : health ok + `/stats` répond + dashboard 200.

- [ ] **Step 4: Vérifier la persistance du volume**
```bash
# insère un event via l'API interne du conteneur puis redémarre
docker compose restart backend
sleep 20
docker volume ls | grep argus-data            # le volume existe
curl -s http://localhost:8000/health           # backend revient
docker compose down                            # arrêt (le volume argus-data persiste)
```
Expected: le volume `argus-data` subsiste après `down` (les preuves/DB seraient conservées).

- [ ] **Step 5: Commit**
```bash
git add docker-compose.yml
git commit -m "build: docker-compose orchestration + persistent volume"
```

---

### Task 5: Documentation — section « Lancer avec Docker »

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Ajouter une section Docker au README** (près des instructions de lancement)
```markdown
## Lancer avec Docker

Prérequis : Docker + Docker Compose. Le modèle `best.pt` doit être présent à la racine.

```bash
docker compose up --build
```

- Console : http://localhost:3000
- Dashboard : http://localhost:3000/dashboard
- API : http://localhost:8000 (`/health`, `/events`, `/stats`, `/reports/*`)

Les preuves floutées et la base SQLite sont persistées dans le volume `argus-data`
(`/data` dans le conteneur backend). Images **CPU-only** (pas de GPU requis).

Notifications (optionnel) : passer `ARGUS_TEAMS_WEBHOOK`, `ARGUS_SMTP_*`, `ARGUS_PUBLIC_URL`
au service backend (section `environment` du `docker-compose.yml`).
```

- [ ] **Step 2: Commit**
```bash
git add README.md
git commit -m "docs: how to run Argus with Docker"
```

---

## Self-Review

**1. Couverture spec (Docker) :** image backend CPU + modèle baké ✅ (T2) ; image frontend
standalone ✅ (T3, T1 pour `output: "standalone"`) ; compose + volume persistant ✅ (T4) ;
`.dockerignore` ✅ (T1) ; README ✅ (T5). GPU/registre/TLS hors périmètre ✅.

**2. Placeholders :** aucun — Dockerfiles, compose, dockerignore et README complets. La
vérification est un build + smoke test réel (Docker dispo), documentée par tâche.

**3. Cohérence :** ports 8000/3000 alignés backend↔compose↔frontend↔`NEXT_PUBLIC_ARGUS_API`
↔CORS (`ARGUS_CORS_ORIGINS=http://localhost:3000`). `/data` créé dans l'image (T2) et monté
par le volume (T4). `output: "standalone"` (T1) requis par le `COPY .next/standalone` (T3).
Contexte backend = racine (T2/T4) pour accéder à `best.pt`. Aucune modif de code applicatif
(seul `next.config.ts` change).
```
