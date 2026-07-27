# Argus — Rapport d'évaluation du modèle de détection

> **Auteur :** Souleymane Diallo · **Dernière mise à jour :** 2026-07-27 · **Modèle :** YOLOv8n

Ce rapport documente **honnêtement** les performances du détecteur EPI d'Argus : métriques **par classe**, test de **généralisation cross-dataset**, et l'**itération d'amélioration** de la classe la plus faible (`shoes`). Le parti pris est de *chiffrer et publier* les faiblesses (notamment le domain gap), pas de les lisser.

## 1. Modèle & entraînement

- **Architecture :** YOLOv8n (Ultralytics), 5 classes — `person`, `helmet`, `safety-vest`, `mask`, `shoes`.
- **Baseline :** `imgsz=640`, ~45 epochs.
- **Modèle courant (itération `shoes`) :** `imgsz=960`, `batch=8`, 50 epochs, optimiseur AdamW (auto), oversampling ×3 des images contenant des chaussures (voir §4). Augmentation Ultralytics par défaut (mosaic, HSV, scale) — inchangée par rapport au baseline pour que le gain soit attribuable.
- **Outillage reproductible :** `data/train.py`, `data/eval.py`, `data/oversample.py` (wrappers testés).

## 2. Datasets (nommés & versionnés)

Fusion multi-datasets avec **harmonisation des labels** (remap par nom vers la taxonomie Argus — scripts `data/`).

| Dataset | Source | Rôle | Apport |
|---|---|---|---|
| **SH17** | Kaggle | entraînement (base) | seule source de `shoes` et `mask` |
| **CHV** | Google Drive | entraînement | casques colorés → `helmet`, `vest` |
| **Pictor-PPE (A1)** | GitHub / Drive | entraînement | `worker`/`hat`/`vest` (converti) |
| **Construction Site Safety (css-data)** | Roboflow v30 | **holdout cross-dataset** | jamais vu à l'entraînement |

**Set fusionné :** 9768 images (**8792 train / 976 val**), 5 classes.
**Distribution des instances :** person 20186 · helmet 6111 · shoes 4560 · safety-vest 2356 · **mask 670** (maillon le plus rare, mono-source).

## 3. Résultats — validation interne (par classe)

Val interne (976 images). Le modèle courant est évalué à `imgsz=960` (sa résolution de déploiement).

| Classe | mAP50 baseline (640) | mAP50 **courant (960)** | rappel baseline | rappel **courant** |
|---|---|---|---|---|
| person | 0.872 | **0.888** | — | 0.851 |
| helmet | 0.839 | **0.886** | — | 0.825 |
| safety-vest | 0.789 | **0.794** | — | 0.735 |
| mask | 0.707 | **0.761** | — | 0.646 |
| **shoes** | 0.445 | **0.544** | 0.42 | **0.52** |
| **all** | **0.73** | **0.775** | — | 0.715 |

Le modèle courant `mAP50-95` (all) = **0.473**. Toutes les classes progressent, sans régression.

## 4. Itération d'amélioration `shoes` (le maillon faible)

**Diagnostic.** `shoes` n'était pas limité par la quantité de données (4560 instances, plus que gilet ou masque) mais par la **difficulté intrinsèque** : petit objet, en bas de cadre, souvent occulté, **mono-source (SH17)**. L'échec était **dominé par le rappel** (0.42) — le modèle *ratait* des chaussures.

**Levier n°1 : la résolution.** Confirmé empiriquement lors de la validation vidéo P1 (`imgsz` 640→960→1280 double quasiment les détections de petits objets). Leviers secondaires : oversampling des images à chaussures (×3), augmentation inchangée.

**Résultat (avant → après) :**

| Métrique `shoes` | baseline (640) | itération (960 + oversampling) | Δ |
|---|---|---|---|
| mAP50 | 0.445 | **0.544** | **+22 %** |
| rappel | 0.42 | **0.52** | **+24 %** |
| mAP50-95 | — | 0.311 | — |

Le **rappel** — la métrique HSE clé (ne pas *rater* une infraction) — gagne le plus. Aucune régression sur les autres classes ; l'agrégat passe de 0.73 à 0.775.

## 5. Généralisation cross-dataset (domain gap)

Évaluation du baseline sur **css-data** (717 images holdout, jamais entraînées, remappées via `data/prep_css_eval.py`).

| | Val interne | Cross-dataset (css-data) |
|---|---|---|
| all mAP50 | 0.73 | **0.624** |

Par classe (cross-dataset) : helmet 0.692 · person 0.644 · safety-vest 0.594 · mask 0.566 (`shoes` absent de css-data).

**Lecture :** un écart de ~15 % relatif entre val interne et domaine inconnu — **modéré**, signe que la fusion multi-datasets a bien généralisé. La **précision** reste haute (~0.87) mais le **rappel chute (~0.53)** : signature classique du domain gap (le modèle *rate* plus sur un domaine non vu). Le rappel est donc le levier prioritaire (résolution ↑, seuil de confiance ↓, diversité des données).

## 6. Caveats d'honnêteté

- **Résolution d'évaluation :** le baseline est mesuré à 640, le modèle courant à 960 — une part du gain vient donc de la résolution d'*évaluation*. Mais 960 est **la résolution de déploiement** (le service tourne à 960/1280), donc c'est le chiffre pertinent en usage. Pour isoler l'effet « entraînement » pur, évaluer l'ancien `best.pt` à 960 (à faire).
- **`shoes` sans cross-dataset :** css-data ne contient pas de chaussures → `shoes` n'est mesuré que sur la val interne (dérivée SH17). Publié tel quel.
- **`mask` mono-source :** 670 instances, uniquement SH17 → couverture de domaine étroite.
- **Chaussures ≠ certifiées :** la vision confirme la *présence* de chaussures, pas qu'il s'agit de bottes de sécurité certifiées.
- **Portée :** ces chiffres démontrent la **méthodologie** (fusion, harmonisation, éval honnête par classe + cross-dataset). Un déploiement certifié terrain exigerait des milliers d'images du site cible et un cycle MLOps continu.

## 7. Reproduire

```bash
# 1. Reconstruire le set fusionné (Colab/Kaggle GPU)
python data/rebuild.py
# 2. Oversampling des images à chaussures
python data/oversample.py --dataset-root <root>/train_set --factor 3
# 3. Entraîner (imgsz 960, 50 epochs)
python data/train.py --data <root>/train_set/data_oversampled.yaml --imgsz 960 --epochs 50
# 4. Évaluer par classe
python data/eval.py --model <run>/weights/best.pt --data <root>/train_set/data.yaml --imgsz 960
```
