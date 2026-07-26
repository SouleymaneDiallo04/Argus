# Amélioration `shoes` (imgsz 960) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Outiller une itération d'entraînement ciblée pour la classe faible `shoes` — oversampling des images à chaussures + retrain `imgsz=960` — de façon reproductible et testée.

**Architecture:** 3 unités dans `data/`, à côté de `fuse.py`/`rebuild.py` : `oversample.py` (logique pure : construit la liste train avec les images à chaussures répétées + réécrit le `data.yaml`), `train.py` et `eval.py` (wrappers Ultralytics minces, import **paresseux**). L'entraînement/éval réels tournent **sur Kaggle** (GPU) ; le code est construit et **unit-testé en local** (pas de GPU, pas d'ultralytics en test).

**Tech Stack:** Python stdlib (logique + tests), Ultralytics YOLOv8 (uniquement à l'exécution sur Kaggle, import paresseux).

## Global Constraints

- Python ≥ 3.10 ; chaque module commence par `from __future__ import annotations`.
- Nouveau code **uniquement dans `data/`** ; ne pas modifier `backend/` ni les modules `data/` existants (`fuse.py`, `remap.py`, `rebuild.py`, …).
- **L'import d'`ultralytics` DOIT être paresseux** (à l'intérieur de `main()`), pour que `import train` / `import eval` et la suite de tests (+ CI) ne dépendent ni d'`ultralytics` ni de `torch`.
- Tests **purs** (stdlib seule), import des modules frères par nom (`from oversample import ...`), lancés via `py -m pytest` depuis `data/`. Le job CI `data` installe seulement `pytest` → les tests ne doivent rien importer de lourd.
- Taxonomie : la classe `shoes` a l'**id 4** (`ARGUS_CLASSES = {0:person,1:helmet,2:safety-vest,3:mask,4:shoes}`). Défauts : `factor=3`, `imgsz=960`, `batch=8`, `epochs=50`.
- Layout du dataset fusionné (produit par `fuse.py`) : `<root>/train/{images,labels}`, `<root>/val/{images,labels}`, `<root>/data.yaml` dont la clé est `train: train/images`. Les images et labels partagent le même *stem* (`{prefix}_{nom}`).
- Commits : préfixe conventionnel, anglais, **sans `Co-Authored-By`** ni ligne "Generated with".

---

### Task 1: `oversample.py` — liste d'oversampling + réécriture du data.yaml

**Files:**
- Create: `data/oversample.py`
- Test: `data/test_oversample.py`

**Interfaces:**
- Produces: `oversampled_image_list(labels_dir, images_dir, *, shoe_class_id=4, factor=3) -> list[Path]` ; `_rewrite_train_in_yaml(text: str, new_train: str) -> str` ; CLI `main(argv=None)`.

- [ ] **Step 1: Écrire le test qui échoue** — `data/test_oversample.py`

```python
from __future__ import annotations

import pytest

from oversample import _rewrite_train_in_yaml, oversampled_image_list


def _make_pair(images_dir, labels_dir, stem, cls_ids):
    (images_dir / f"{stem}.jpg").write_bytes(b"x")
    lines = "\n".join(f"{c} 0.5 0.5 0.2 0.2" for c in cls_ids)
    (labels_dir / f"{stem}.txt").write_text(lines + "\n", encoding="utf-8")


def test_oversamples_shoe_images_and_keeps_others_once(tmp_path):
    images, labels = tmp_path / "images", tmp_path / "labels"
    images.mkdir(); labels.mkdir()
    _make_pair(images, labels, "a_with_shoes", [0, 4])
    _make_pair(images, labels, "b_no_shoes", [0, 1])
    _make_pair(images, labels, "c_with_shoes", [4])

    paths = oversampled_image_list(labels, images, shoe_class_id=4, factor=3)
    names = [p.name for p in paths]
    assert names.count("a_with_shoes.jpg") == 3
    assert names.count("c_with_shoes.jpg") == 3
    assert names.count("b_no_shoes.jpg") == 1
    assert len(paths) == 7


def test_factor_one_is_no_oversampling(tmp_path):
    images, labels = tmp_path / "images", tmp_path / "labels"
    images.mkdir(); labels.mkdir()
    _make_pair(images, labels, "s", [4])
    _make_pair(images, labels, "n", [0])
    assert len(oversampled_image_list(labels, images, shoe_class_id=4, factor=1)) == 2


def test_skips_label_without_matching_image(tmp_path):
    images, labels = tmp_path / "images", tmp_path / "labels"
    images.mkdir(); labels.mkdir()
    (labels / "orphan.txt").write_text("4 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    assert oversampled_image_list(labels, images) == []


def test_rewrite_train_replaces_only_train_line():
    text = "path: /d\ntrain: train/images\nval: val/images\nnames:\n  0: person\n"
    out = _rewrite_train_in_yaml(text, "/abs/train.txt")
    assert "train: /abs/train.txt" in out
    assert "val: val/images" in out and "path: /d" in out
    assert "train: train/images" not in out


def test_rewrite_train_raises_if_absent():
    with pytest.raises(ValueError):
        _rewrite_train_in_yaml("path: /d\nval: v\n", "/abs/train.txt")
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd data && py -m pytest test_oversample.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oversample'`.

- [ ] **Step 3: Écrire l'implémentation** — `data/oversample.py`

```python
from __future__ import annotations

import argparse
from pathlib import Path

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")


def _label_class_ids(label_path) -> set[int]:
    ids: set[int] = set()
    for line in Path(label_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            ids.add(int(float(line.split()[0])))
    return ids


def _find_image(images_dir, stem: str):
    d = Path(images_dir)
    for ext in IMAGE_EXTS:
        p = d / (stem + ext)
        if p.exists():
            return p
    matches = list(d.glob(stem + ".*"))
    return matches[0] if matches else None


def oversampled_image_list(labels_dir, images_dir, *, shoe_class_id: int = 4,
                           factor: int = 3) -> list[Path]:
    """Chemins d'images de la split train, chaque image contenant >=1 instance de
    `shoe_class_id` répétée `factor` fois (les autres une seule fois)."""
    paths: list[Path] = []
    for label in sorted(Path(labels_dir).glob("*.txt")):
        img = _find_image(images_dir, label.stem)
        if img is None:
            continue
        reps = factor if shoe_class_id in _label_class_ids(label) else 1
        paths.extend([img.resolve()] * reps)
    return paths


def _rewrite_train_in_yaml(text: str, new_train: str) -> str:
    """Remplace la valeur de la clé `train:` d'un data.yaml par `new_train`."""
    out, replaced = [], False
    for line in text.splitlines():
        if line.strip().startswith("train:"):
            out.append(f"train: {new_train}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        raise ValueError("aucune ligne 'train:' dans le data.yaml")
    return "\n".join(out) + "\n"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(
        description="Génère train_oversampled.txt (images à chaussures répétées) + "
                    "data_oversampled.yaml à partir d'un dataset fusionné.")
    ap.add_argument("--dataset-root", required=True,
                    help="racine du dataset fusionné (contient train/, val/, data.yaml)")
    ap.add_argument("--factor", type=int, default=3,
                    help="répétition des images contenant des chaussures")
    ap.add_argument("--shoe-class-id", type=int, default=4)
    args = ap.parse_args(argv)

    root = Path(args.dataset_root)
    paths = oversampled_image_list(
        root / "train" / "labels", root / "train" / "images",
        shoe_class_id=args.shoe_class_id, factor=args.factor,
    )
    txt = root / "train_oversampled.txt"
    txt.write_text("\n".join(str(p) for p in paths) + "\n", encoding="utf-8")

    base_yaml = (root / "data.yaml").read_text(encoding="utf-8")
    (root / "data_oversampled.yaml").write_text(
        _rewrite_train_in_yaml(base_yaml, str(txt.resolve())), encoding="utf-8")

    print(f"train_oversampled.txt : {len(paths)} lignes ; data_oversampled.yaml écrit.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd data && py -m pytest test_oversample.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add data/oversample.py data/test_oversample.py
git commit -m "feat(data): shoe-image oversampling for training (train list + data.yaml rewrite)"
```

---

### Task 2: `train.py` + `eval.py` — wrappers Ultralytics (import paresseux)

**Files:**
- Create: `data/train.py`
- Create: `data/eval.py`
- Test: `data/test_cli.py`

**Interfaces:**
- Produces: `train.parse_args(argv=None)` (defaults `imgsz=960`, `epochs=50`, `batch=8`, `model="yolov8n.pt"`, `name="argus_shoes_v1_960"`) + `train.main`; `eval.parse_args(argv=None)` (defaults `imgsz=960`, `split="val"`) + `eval.main`.

- [ ] **Step 1: Écrire le test qui échoue** — `data/test_cli.py`

```python
from __future__ import annotations

import eval as evaluate
import train


def test_train_defaults():
    args = train.parse_args(["--data", "d.yaml"])
    assert args.imgsz == 960
    assert args.epochs == 50
    assert args.batch == 8
    assert args.model == "yolov8n.pt"


def test_train_overrides():
    args = train.parse_args(["--data", "d.yaml", "--imgsz", "1280", "--batch", "4"])
    assert args.imgsz == 1280 and args.batch == 4


def test_eval_defaults():
    args = evaluate.parse_args(["--model", "best.pt", "--data", "d.yaml"])
    assert args.imgsz == 960 and args.split == "val"
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd data && py -m pytest test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'train'`.

- [ ] **Step 3: Écrire l'implémentation**

`data/train.py` :
```python
from __future__ import annotations

import argparse


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Entraîne YOLOv8n sur le set fusionné (itération shoes, imgsz 960).")
    ap.add_argument("--data", required=True,
                    help="chemin du data.yaml (ex. data_oversampled.yaml)")
    ap.add_argument("--model", default="yolov8n.pt", help="poids de départ")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--project", default=None, help="dossier de sortie (ex. Drive)")
    ap.add_argument("--name", default="argus_shoes_v1_960")
    return ap.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    from ultralytics import YOLO  # import paresseux : non requis par les tests / la CI

    YOLO(args.model).train(
        data=args.data, imgsz=args.imgsz, epochs=args.epochs, batch=args.batch,
        project=args.project, name=args.name,
    )


if __name__ == "__main__":
    main()
```

`data/eval.py` :
```python
from __future__ import annotations

import argparse


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Évalue un modèle par classe (mAP50 / mAP50-95 / rappel) sur un data.yaml.")
    ap.add_argument("--model", required=True, help="chemin du .pt à évaluer (ex. best.pt)")
    ap.add_argument("--data", required=True)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--split", default="val")
    return ap.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    from ultralytics import YOLO  # import paresseux

    model = YOLO(args.model)
    m = model.val(data=args.data, imgsz=args.imgsz, split=args.split)
    print(f"all  mAP50={m.box.map50:.3f}  mAP50-95={m.box.map:.3f}")
    for k, cls_id in enumerate(m.box.ap_class_index):
        name = model.names[int(cls_id)]
        print(f"  {name:12s} mAP50={m.box.ap50[k]:.3f}  mAP50-95={m.box.maps[int(cls_id)]:.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd data && py -m pytest test_cli.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Lancer toute la suite `data/`**

Run: `cd data && py -m pytest -q`
Expected: tous verts (existants + oversample + cli), sans dépendance à ultralytics.

- [ ] **Step 6: Commit**

```bash
git add data/train.py data/eval.py data/test_cli.py
git commit -m "feat(data): Ultralytics train/eval wrappers (imgsz 960, per-class metrics)"
```

---

## Runbook opérationnel (à exécuter par Souleymane sur Kaggle, hors code)

Après merge, sur Kaggle (GPU T4, dataset fusionné reconstruit par `rebuild.py`) :

```bash
# 1. Générer la liste oversamplée + le yaml (root = dossier du dataset fusionné)
py data/oversample.py --dataset-root /kaggle/working/train_set --factor 3

# 2. Entraîner à 960 (baseline: best.pt actuel à 640 -> comparer)
py data/train.py --data /kaggle/working/train_set/data_oversampled.yaml \
    --project /kaggle/working/argus_runs --name argus_shoes_v1_960

# 3. Éval par classe : comparer shoes (baseline 0.445 / rappel 0.42)
py data/eval.py --model /kaggle/working/argus_runs/argus_shoes_v1_960/weights/best.pt \
    --data /kaggle/working/train_set/data.yaml
```

Succès = `shoes` mAP50 ≥ ~0.55 et rappel > 0.42 sans régression des autres classes ; sinon escalade B (re-fuse `max_side=1280` + `imgsz=1280`).

## Self-Review

**1. Couverture spec :** oversampling images shoes ✅ (Task 1, `oversampled_image_list`) ; câblage `data.yaml` → liste ✅ (`_rewrite_train_in_yaml` + CLI) ; retrain imgsz 960 / batch 8 / epochs 50 / yolov8n ✅ (Task 2 `train.py` defaults) ; éval par classe ✅ (`eval.py`) ; import ultralytics paresseux ✅ ; reproductibilité committée ✅ ; exécution Kaggle ✅ (runbook). Hors périmètre (re-fuse 1280, copy-paste) : absent ✅.

**2. Placeholders :** aucun — code complet à chaque étape.

**3. Cohérence des types :** `oversampled_image_list(...) -> list[Path]` consommé par `main` (Task 1) ; `parse_args` defaults (imgsz 960, batch 8) cohérents entre Task 2 et le runbook ; `shoe_class_id=4` cohérent avec la taxonomie. Les tests importent par nom de module frère (`from oversample import ...`, `import train`, `import eval as evaluate`) comme `test_fuse.py`. L'import ultralytics reste dans `main()` → `import train`/`import eval` sûrs en CI.
