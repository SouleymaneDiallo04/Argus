from __future__ import annotations

"""Prépare css-data (le HOLDOUT) pour l'éval cross-dataset d'Argus.

Télécharge css-data (Roboflow v30) → remappe ses labels vers la taxonomie Argus
(en place, idempotent) → écrit un `eval.yaml` pointant sur TOUT css-data (train+valid
+test, aucun n'a servi à l'entraînement → tout est holdout).

Pré-requis : os.environ["ROBOFLOW_API_KEY"] défini. Lancer depuis la racine du repo.
Usage : python data/prep_css_eval.py   puis   YOLO(best.pt).val(data=".../eval.yaml")

Note : css-data n'a PAS de `shoes` → l'AP shoes en cross-dataset sera nul/indéfini,
c'est attendu (shoes ne peut s'évaluer qu'en intra-SH17).
"""

import glob
import os
import sys

import yaml

sys.path.insert(0, "data")
from remap import remap_dataset  # noqa: E402

ROOT = "data/raw/css-data"
SPLITS = ("train", "valid", "test")
ARGUS = {0: "person", 1: "helmet", 2: "safety-vest", 3: "mask", 4: "shoes"}


def download() -> None:
    if os.path.exists(ROOT):
        return
    from roboflow import Roboflow

    rf = Roboflow(api_key=os.environ["ROBOFLOW_API_KEY"])
    (rf.workspace("roboflow-universe-projects").project("construction-site-safety")
       .version(30).download("yolov8", location=ROOT))


def remap_in_place() -> None:
    marker = os.path.join(ROOT, ".remapped")
    if os.path.exists(marker):
        print("Déjà remappé, on saute.")
        return
    mapping = yaml.safe_load(open("data/mapping.yaml"))
    css_names = yaml.safe_load(open(f"{ROOT}/data.yaml"))["names"]
    for split in SPLITS:
        src = f"{ROOT}/{split}"
        if os.path.exists(src):
            print(split, remap_dataset(src, src, "css-data", mapping, css_names))
    open(marker, "w").close()


def write_eval_yaml() -> str:
    root_abs = os.path.abspath(ROOT)
    images = []
    for split in SPLITS:
        images += sorted(glob.glob(f"{root_abs}/{split}/images/*.*"))
    list_file = f"{root_abs}/holdout_images.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        f.write("\n".join(images) + "\n")
    eval_yaml = f"{root_abs}/eval.yaml"
    with open(eval_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"path": root_abs, "val": "holdout_images.txt", "names": ARGUS},
            f, sort_keys=False, allow_unicode=True,
        )
    print(f"{len(images)} images holdout -> {eval_yaml}")
    return eval_yaml


def main() -> None:
    download()
    remap_in_place()
    write_eval_yaml()


if __name__ == "__main__":
    main()
