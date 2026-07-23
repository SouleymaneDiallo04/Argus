from __future__ import annotations

"""Fusionne les datasets d'entraînement remappés (SH17 + CHV + Pictor) en UN seul
dataset YOLO : out/{train,val}/{images,labels} + out/data.yaml.

Choix V1 :
- on ne garde que les images avec >=1 boîte (labels vides = fond, exclus) ;
- chaque image est préfixée par sa source (évite les collisions de noms entre datasets) ;
- split aléatoire déterministe au niveau image. L'éval de généralisation HONNÊTE vient
  du holdout cross-dataset (css-data), pas de ce split interne — donc un split simple suffit.
"""

import random
from pathlib import Path

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")


def find_image(images_dir, stem: str):
    """Trouve l'image correspondant à un stem de label (teste les extensions)."""
    d = Path(images_dir)
    for ext in IMAGE_EXTS:
        p = d / (stem + ext)
        if p.exists():
            return p
    matches = list(d.rglob(stem + ".*"))
    return matches[0] if matches else None


def collect_pairs(sources):
    """sources : [(labels_dir, images_dir, prefix), ...].
    Retourne [(label_path, image_path, prefix)] pour les labels NON vides
    ayant une image trouvée."""
    pairs = []
    for labels_dir, images_dir, prefix in sources:
        for label in sorted(Path(labels_dir).rglob("*.txt")):
            if not label.read_text(encoding="utf-8").strip():
                continue
            img = find_image(images_dir, label.stem)
            if img is not None:
                pairs.append((label, img, prefix))
    return pairs


def split_pairs(pairs, val_frac: float = 0.1, seed: int = 42):
    """Split aléatoire déterministe au niveau image -> (train, val), sans fuite."""
    shuffled = list(pairs)
    random.Random(seed).shuffle(shuffled)
    n_val = int(len(shuffled) * val_frac)
    return shuffled[n_val:], shuffled[:n_val]


def _write_yaml(path, root, class_names):
    lines = [f"path: {root}", "train: train/images", "val: val/images", "names:"]
    lines += [f"  {i}: {name}" for i, name in enumerate(class_names)]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _resize_to(src, dst, max_side: int) -> None:
    """Sauve une copie de `src` dont le plus grand côté <= max_side (fichier réel).
    Les labels YOLO étant normalisés, ils restent valides. Décode fallback -> copie."""
    import shutil

    from PIL import Image

    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            w, h = im.size
            scale = max_side / max(w, h)
            if scale < 1:
                im = im.resize((round(w * scale), round(h * scale)), Image.BILINEAR)
            im.save(dst, quality=90)
    except Exception:
        shutil.copy(src, dst)


def fuse(sources, out_dir, class_names, val_frac: float = 0.1, seed: int = 42,
         max_side=None, workers: int = 8):
    """Fusionne les sources en un dataset YOLO train/val + data.yaml.

    Si `max_side` est donné (ex. 1024), les images sont redimensionnées (fichiers
    réels) en PARALLÈLE, avec progression affichée -> décodage rapide à l'entraînement.
    Sinon lien symbolique (rapide, sans copie). Labels copiés (normalisés -> inchangés)."""
    import os
    import shutil
    from concurrent.futures import ThreadPoolExecutor

    out = Path(out_dir)
    train, val = split_pairs(collect_pairs(sources), val_frac, seed)
    resize_tasks = []
    for split_name, split in (("train", train), ("val", val)):
        (out / split_name / "images").mkdir(parents=True, exist_ok=True)
        (out / split_name / "labels").mkdir(parents=True, exist_ok=True)
        for label, img, prefix in split:
            base = f"{prefix}_{img.stem}"
            dst_img = out / split_name / "images" / f"{base}{img.suffix}"
            shutil.copy(label, out / split_name / "labels" / f"{base}.txt")
            if max_side:
                resize_tasks.append((img, dst_img))
            elif not dst_img.exists():
                try:
                    os.symlink(img.resolve(), dst_img)
                except (OSError, NotImplementedError):
                    shutil.copy(img, dst_img)

    if resize_tasks:
        total = len(resize_tasks)
        done = [0]

        def _work(task):
            _resize_to(task[0], task[1], max_side)
            done[0] += 1
            if done[0] % 500 == 0 or done[0] == total:
                print(f"  redimensionnement {done[0]}/{total}", flush=True)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_work, resize_tasks))

    _write_yaml(out / "data.yaml", out.resolve(), class_names)
    return {"total": len(train) + len(val), "train": len(train), "val": len(val)}
