from __future__ import annotations

"""Reconstruit tout le dataset d'entraînement Argus depuis zéro (Colab).

Enchaîne : download (SH17 / css-data / CHV / Pictor) -> conversion Pictor
-> remap des sources d'entraînement -> fusion en un dataset YOLO.

Pré-requis (à faire AVANT, dans une cellule Colab) :
    !pip install -q roboflow kaggle gdown ultralytics
    import os
    os.environ["KAGGLE_API_TOKEN"] = "..."     # token Kaggle (KGAT_...)
    os.environ["ROBOFLOW_API_KEY"] = "..."     # clé Roboflow
    from google.colab import drive; drive.mount('/content/drive')   # pour les images Pictor

Puis : !python data/rebuild.py

Idempotent : ne re-télécharge que ce qui manque. C'est le filet quand le runtime
Colab est recyclé (disque effacé). Lancer depuis la racine du repo (/content/Argus).
"""

import glob
import os
import subprocess
import sys

sys.path.insert(0, "data")

import yaml  # noqa: E402
from convert_pictor import convert_pictor_file  # noqa: E402
from fuse import fuse  # noqa: E402
from remap import remap_dataset  # noqa: E402

# Images Pictor : accédées via le raccourci "pictor-ppe" monté depuis le Drive
PICTOR_IMAGES_SRC = os.environ.get(
    "PICTOR_IMAGES_SRC", "/content/drive/MyDrive/pictor-ppe/Images"
)
PICTOR_LABELS_FOLDER = (
    "https://drive.google.com/drive/folders/17VMS2-EQAuB6CsCVDK5ScmxjrP-B2cgW"
)
CHV_ZIP_ID = "1fdGn67W0B7ShpBDbbQpUF0ScPQa4DR0a"

SH17_NAMES = {0: "person", 1: "ear", 2: "ear-mufs", 3: "face", 4: "face-guard",
              5: "face-mask", 6: "foot", 7: "tool", 8: "glasses", 9: "gloves",
              10: "helmet", 11: "hands", 12: "head", 13: "medical-suit", 14: "shoes",
              15: "safety-suit", 16: "safety-vest"}
CHV_NAMES = ["person", "vest", "blue helmet", "red helmet", "white helmet", "yellow helmet"]
PICTOR_NAMES = ["hat", "vest", "worker"]
ARGUS = ["person", "helmet", "safety-vest", "mask", "shoes"]


def sh(cmd: str) -> None:
    print("+", cmd)
    subprocess.run(cmd, shell=True, check=True)


def exists(path: str) -> bool:
    return os.path.exists(path)


def download() -> None:
    os.makedirs("data/raw/pictor", exist_ok=True)
    if not exists("data/raw/sh17/labels"):
        sh("python data/download.py sh17")
    if not exists("data/raw/css-data"):
        from roboflow import Roboflow

        rf = Roboflow(api_key=os.environ["ROBOFLOW_API_KEY"])
        (rf.workspace("roboflow-universe-projects").project("construction-site-safety")
           .version(30).download("yolov8", location="data/raw/css-data"))
    if not exists("data/raw/chv/CHV_dataset"):
        sh(f"gdown {CHV_ZIP_ID} -O data/raw/chv.zip")
        sh("unzip -q data/raw/chv.zip -d data/raw/chv")
    if not exists("data/raw/pictor/labels_raw"):
        sh(f'gdown --folder "{PICTOR_LABELS_FOLDER}" -O data/raw/pictor/labels_raw')
    if not exists("data/raw/pictor/images"):
        sh(f'cp -r "{PICTOR_IMAGES_SRC}" data/raw/pictor/images')


def convert_pictor() -> None:
    for f in sorted(glob.glob("data/raw/pictor/labels_raw/*approach-01*.txt")):
        print(f, convert_pictor_file(f, "data/raw/pictor/images", "data/raw/pictor/labels"))


def remap_all(mapping: dict) -> None:
    print("SH17  ", remap_dataset("data/raw/sh17", "data/unified/sh17", "sh17", mapping, SH17_NAMES))
    print("CHV   ", remap_dataset("data/raw/chv/CHV_dataset", "data/unified/chv", "chv",
                                   mapping, CHV_NAMES, labels_subdir="annotations"))
    print("Pictor", remap_dataset("data/raw/pictor", "data/unified/pictor", "pictor",
                                   mapping, PICTOR_NAMES))


def main() -> None:
    mapping = yaml.safe_load(open("data/mapping.yaml"))
    download()
    convert_pictor()
    remap_all(mapping)
    sources = [
        ("data/unified/sh17/labels", "data/raw/sh17/images", "sh17"),
        ("data/unified/chv/annotations", "data/raw/chv/CHV_dataset/images", "chv"),
        ("data/unified/pictor/labels", "data/raw/pictor/images", "pictor"),
    ]
    print("FUSION", fuse(sources, "data/unified/train_set", ARGUS))


if __name__ == "__main__":
    main()
