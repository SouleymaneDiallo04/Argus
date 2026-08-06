# P3-d — Rapports HSE (CSV + PDF) — Design

**Date :** 2026-08-04
**Phase :** P3 (Alertes, RGPD, preuves, rapports) — sous-projet **d** (dernière brique)
**Dépend de :** P3-a (`/events`, `/stats`, `Journal`) mergé ; P2-b (dashboard) mergé.
**Statut :** validé

## 1. Objectif

Exporter le journal d'infractions et la synthèse de conformité en **CSV** (données brutes)
et **PDF** (rapport HSE lisible), et **activer le bouton « Exporter »** du dashboard.

Clôt le cahier des charges V1 (§ « export de rapports »).

## 2. Décisions de conception (validées)

- **CSV** via `csv` (stdlib) ; **PDF** via **ReportLab** (pur Python, **1ʳᵉ nouvelle
  dépendance** du projet — aucun binaire natif).
- **PDF = synthèse + tableaux** : en-tête (site / période) + taux de conformité (global +
  par zone) + tableau des infractions. **Pas de vignette floutée** dans le PDF (V2 — évite de
  coupler le générateur au stockage disque).
- **Génération pure et testable** (dict/list → `str`/`bytes`), séparée des endpoints.
- Réutilise les filtres existants (`zone`, `ppe`, `since`, `until`) via `Journal`.

## 3. Périmètre

**Dans P3-d :**
- `app/reports/` : `events_csv` (CSV) + `summary_pdf` (PDF ReportLab).
- Endpoints `GET /reports/events.csv` et `GET /reports/summary.pdf` (téléchargement).
- Frontend : bouton export activé (CSV / PDF) + `lib/reportsApi.ts`.

**Hors P3-d :**
- Vignettes floutées dans le PDF, planification/envoi automatique de rapports, signature →
  V2. Auth/rôles → V2.

## 4. Backend — génération pure

### `app/reports/csv_report.py`
```
events_csv(events: list[dict]) -> str
    # entête FR : Heure, Zone, Personne, EPI manquants, Caméra, Preuve
    # une ligne par event ; `missing` -> "helmet, shoes" ; snapshot -> nom ou ""
```

### `app/reports/pdf_report.py`
```
summary_pdf(stats: dict, events: list[dict], meta: dict) -> bytes
    # meta = {site, since, until, generated_at}
    # Structure ReportLab (SimpleDocTemplate) :
    #   - Titre "Rapport de conformité EPI — Argus" + site + période + date de génération
    #   - Tableau synthèse : conformité globale (rate%), nb infractions
    #   - Tableau par zone : zone / taux / infractions
    #   - Tableau des infractions : heure, zone, personne, EPI manquants
    # Retourne les octets du PDF (%PDF...).
```

## 5. Backend — endpoints (téléchargement)

Les deux lisent `app.state.journal`, appellent le générateur pur, et renvoient une réponse
avec `Content-Disposition: attachment`.

- **`GET /reports/events.csv?zone&ppe&since&until`**
  → `journal.events(filters)` → `events_csv(...)` → `Response(text/csv)`,
  `filename="argus-events.csv"`.
- **`GET /reports/summary.pdf?since&until&zone`**
  → `journal.stats(filters)` + `journal.events(filters)` → `summary_pdf(...)` →
  `Response(application/pdf)`, `filename="argus-rapport.pdf"`.
  `meta.site` = `ARGUS_SITE` (défaut `"Meknès-Nord"`), `generated_at = now UTC`.

## 6. Dépendance

`reportlab` ajouté à **`backend/requirements.txt`** (runtime) **et**
**`backend/requirements-dev.txt`** (la CI backend installe ce dernier — il est autonome).

## 7. Frontend — activer l'export

- `frontend/lib/reportsApi.ts` :
  ```
  reportUrl(kind: "csv" | "pdf", params: {zone?; ppe?; since?}) -> string
    # `${API}/reports/events.csv?…`  |  `${API}/reports/summary.pdf?…`
  ```
- `Dashboard` : le bouton inerte devient deux liens **CSV** / **PDF**
  (`<a href={reportUrl(...)} download>`), construits avec les filtres courants
  (zone/ppe + `since` dérivé de la plage). Téléchargement natif du navigateur.

## 8. Structure de fichiers

```
backend/app/reports/__init__.py
backend/app/reports/csv_report.py
backend/app/reports/pdf_report.py
backend/app/api/app.py                 # + 2 endpoints /reports/*
backend/requirements.txt               # + reportlab
backend/requirements-dev.txt           # + reportlab
backend/tests/test_csv_report.py
backend/tests/test_pdf_report.py
backend/tests/test_reports_api.py
frontend/lib/reportsApi.ts  + reportsApi.test.ts
frontend/components/dashboard/Dashboard.tsx  (bouton export activé)
frontend/components/dashboard/Dashboard.test.tsx  (adapté : liens CSV/PDF)
```

## 9. Tests (TDD)

- **`csv_report`** : entête + lignes exactes ; `missing` joint ; snapshot vide si `null`.
- **`pdf_report`** : les octets **commencent par `%PDF`** et le PDF n'est pas vide ;
  ne lève pas sur `stats`/`events` vides.
- **`reports_api`** : `GET /reports/events.csv` → 200, `text/csv`, `Content-Disposition`
  attachment, corps = CSV ; `GET /reports/summary.pdf` → 200, `application/pdf`, attachment
  (journal injecté en `:memory:`).
- **Frontend** : `reportUrl` construit les bonnes URLs + filtres ; `Dashboard` rend des
  liens CSV/PDF avec le bon `href`.
- Suites existantes vertes (backend **97**, frontend **44**) ; `npm run build` OK.

## 10. Critères d'acceptation

1. `GET /reports/events.csv` télécharge le journal filtré en CSV.
2. `GET /reports/summary.pdf` télécharge un PDF valide (synthèse + tableaux).
3. Le dashboard propose CSV / PDF, avec les filtres courants, et déclenche le téléchargement.
4. `reportlab` présent dans les deux requirements ; CI verte.
5. Générateurs purs testés ; suites existantes vertes.
