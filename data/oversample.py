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
