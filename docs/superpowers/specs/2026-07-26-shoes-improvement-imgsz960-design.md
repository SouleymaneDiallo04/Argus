# Amélioration `shoes` — itération imgsz 960 — Design

> **Auteur :** Souleymane Diallo · **Date :** 2026-07-26 · **Phase :** P0.4 (amélioration modèle, en parallèle du backend)

## Objectif

Faire progresser la classe la plus faible du modèle — `shoes`, **mAP50 0.445 / rappel 0.42** — sans régression matérielle des autres classes, par une itération d'entraînement ciblée et **mesurée honnêtement**. Cible : `shoes` mAP50 **≥ ~0.55** et rappel **> 0.42**.

## Diagnostic

`shoes` n'est **pas** limité par la quantité de données : 4560 instances (plus que `safety-vest` 2356 ou `mask` 670). C'est une classe **intrinsèquement difficile** — petit objet, en bas de cadre, souvent occulté — et **mono-source** (uniquement SH17). L'échec est **dominé par le rappel** (0.42) : le modèle rate des chaussures qu'il devrait détecter.

**Levier n°1 = la résolution.** Preuve directe : lors de la validation vidéo P1a, passer `imgsz` 640 → 960 → 1280 a quasi **doublé** les détections (chaussures et personnes au fond). L'augmentation et l'oversampling sont des leviers secondaires ; les toucher sans changer la résolution donnerait peu.

## Approche — itération `shoes-v1` (imgsz 960)

Principe : **changer peu de choses par rapport au baseline** pour que le gain soit *attribuable*.

### Données
- On **réutilise le set fusionné actuel** (`max_side=1024`) — **pas de re-fuse**. À 1024 px source, entraîner à `imgsz=960` n'upscale quasiment pas.
- **Un seul levier data ciblé : oversampling des images contenant des chaussures.** Un script scanne les labels de la split `train`, repère les images ayant au moins une instance de la classe `4` (shoes) et génère une liste `train.txt` (chemins d'images) où ces images sont **répétées `factor` fois** (défaut 3). Ultralytics accepte un fichier-liste comme `train:` dans le `data.yaml` → les images à chaussures sont vues plus souvent, sans dupliquer les fichiers sur disque.

### Recette d'entraînement (YOLOv8n)
- `imgsz` **640 → 960** (le levier dominant).
- **Augmentation inchangée** (défauts Ultralytics du baseline : `mosaic=1.0`, `scale=0.5`, jitter HSV). On ne modifie **que** `imgsz` et l'oversampling → le gain reste attribuable à ces deux leviers, pas à une refonte de l'augmentation.
- **`copy_paste` écarté** : l'augmentation copy-paste d'Ultralytics exige des masques de segmentation, or nos labels sont des boîtes. (Réservé à l'escalade B.)
- `batch` **16 → 8** (attendu : 960 px consomme plus de VRAM sur T4).
- **Entraînement frais** (pas un fine-tune de `best.pt`) : attribution propre du gain, même recette au détail près de `imgsz`/oversampling. ~50 epochs. Couvert par le budget Kaggle gratuit (30 h GPU/sem, T4×2).

### Reproductibilité (comble le trou « notebooks » du §10 de la spec produit)
- On **committe** les wrappers Ultralytics `data/train.py` et `data/eval.py` au lieu de cellules Kaggle jetables → retrain reproductible, comparaison avant/après équitable et versionnée.
- **Répartition d'exécution :** l'entraînement et l'évaluation réels tournent **sur Kaggle** (GPU) — l'utilisateur lance `train.py`/`eval.py` là-bas. Les scripts sont **construits et testés en local** (pas de GPU ici) : la logique pure (construction de la liste d'oversampling, parsing d'arguments) est couverte par des tests ; l'import d'`ultralytics` est **paresseux** pour que la suite de tests et la CI n'en dépendent pas.

## Composants (unités à responsabilité unique)

| Fichier | Responsabilité |
|---|---|
| `data/oversample.py` | Fonction pure : à partir du dossier de labels `train`, produire la liste des chemins d'images avec les images contenant des chaussures répétées `factor` fois ; écrire `train.txt`. **Testable sans ultralytics.** |
| `data/train.py` | Wrapper mince : `YOLO(base).train(data=<yaml pointant sur train.txt>, imgsz=960, epochs, batch, ...)`. Import ultralytics **paresseux**. Args via `argparse`. |
| `data/eval.py` | Wrapper mince : `YOLO(best).val(data=<yaml>)` → métriques **par classe** (mAP50/mAP50-95, rappel). Import ultralytics paresseux. Args via `argparse`. |

## Évaluation

- **Per-classe sur la val interne** : comparaison directe `shoes 0.445 → ?`, focus sur le **rappel**. Aussi vérifier l'absence de régression sur person/helmet/safety-vest/mask.
- ⚠️ **Limite assumée et publiée : `shoes` n'a pas de test cross-dataset** — le holdout css-data ne contient pas de chaussures. `shoes` est donc mesuré sur la val (dérivée SH17) uniquement. À documenter tel quel, pas à masquer.
- Le service tournera à `imgsz` élevé à l'inférence (960/1280) ; l'éval doit refléter la résolution d'usage.

## Critères de succès

- `shoes` mAP50 **≥ ~0.55** et rappel **> 0.42**, **sans régression matérielle** des autres classes (tolérance : pas de baisse > ~2 points mAP50 sur une classe déjà forte).
- Si non atteint → **escalader vers B** : re-fuse `max_side=1280` + `imgsz=1280` + oversampling + (copy-paste via masques de segmentation si envisagé).

## Hors périmètre de cette itération

Re-fuse à 1280 (escalade B), copy-paste, active-learning (P5), et le réglage *inférence* (imgsz↑ / seuil conf↓ pour shoes) — complémentaire mais traité séparément, pas dans ce retrain.

## Frontières & DRY

Le nouveau code vit dans `data/` (couche données/entraînement), à côté de `fuse.py`/`rebuild.py` existants. Aucune modification de `backend/`. L'oversampling réutilise le format de labels YOLO déjà produit par `fuse.py` ; l'éval réutilise `prep_css_eval.py` si un cross-dataset est relancé pour les classes qui l'ont.
