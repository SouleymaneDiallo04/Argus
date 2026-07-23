"""Télécharge les 4 datasets EPI dans data/raw/ — à lancer sur Colab.

À exécuter là où tournera l'entraînement (Colab/GPU), pas en local : les datasets
pèsent plusieurs Go et doivent vivre à côté du GPU. Deux sources exigent TES clés
API perso (je ne peux pas m'authentifier à ta place) — voir prérequis.

Prérequis (dans une cellule Colab) :
    !pip install roboflow kaggle gdown
    # Roboflow : clé perso sur app.roboflow.com -> Settings -> API
    import os; os.environ["ROBOFLOW_API_KEY"] = "xxxxxxxx"
    # Kaggle   : kaggle.com -> Account -> Create API Token -> uploader kaggle.json
    !mkdir -p ~/.kaggle && cp kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json

Usage :
    python data/download.py                 # tout
    python data/download.py sh17 css-data   # sélection
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAW = Path("data/raw")

# Numéros de version Roboflow — à lire sur la page "Download Dataset". Surchargeables
# par variables d'env (pas besoin d'éditer ce fichier sur Colab).
CSS_DATA_VERSION = int(os.environ.get("CSS_DATA_VERSION", "1"))   # roboflow-universe-projects/construction-site-safety
PICTOR_VERSION = int(os.environ.get("PICTOR_VERSION", "9"))       # ppe-orxtt/ppe-u7jtr ("Pictor-v3-revised")


def _roboflow(workspace: str, project: str, version: int, out: str) -> None:
    from roboflow import Roboflow

    key = os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        raise RuntimeError("ROBOFLOW_API_KEY manquante (app.roboflow.com -> Settings -> API).")
    rf = Roboflow(api_key=key)
    proj = rf.workspace(workspace).project(project)
    proj.version(version).download("yolov8", location=out)


def _ensure_kaggle_auth() -> None:
    """Écrit le token (env KAGGLE_API_TOKEN) dans ~/.kaggle/access_token pour que
    le paquet kaggle le trouve de façon fiable, y compris dans un sous-processus."""
    tok = os.environ.get("KAGGLE_API_TOKEN")
    if not tok:
        return
    kdir = Path.home() / ".kaggle"
    kdir.mkdir(exist_ok=True)
    token_file = kdir / "access_token"
    token_file.write_text(tok)
    try:
        token_file.chmod(0o600)
    except OSError:
        pass


def download_sh17() -> None:
    # Base du projet : 8099 images, 17 classes, seule source de shoes + mask. Kaggle.
    _ensure_kaggle_auth()
    import kaggle

    dest = RAW / "sh17"
    dest.mkdir(parents=True, exist_ok=True)
    kaggle.api.dataset_download_files(
        "mugheesahmad/sh17-dataset-for-ppe-detection", path=str(dest), unzip=True
    )


def download_css_data() -> None:
    # HOLDOUT cross-dataset : téléchargé mais JAMAIS entraîné (cf. mapping.yaml).
    _roboflow("roboflow-universe-projects", "construction-site-safety",
              CSS_DATA_VERSION, str(RAW / "css-data"))


def download_pictor() -> None:
    # Version Roboflow "Pictor-v3-revised" (YOLO, boîtes séparées). Vérifier ses
    # classes réelles (worker/hat/vest) après download.
    _roboflow("ppe-orxtt", "ppe-u7jtr", PICTOR_VERSION, str(RAW / "pictor"))


def download_chv() -> None:
    # CHV (1330 img). Repo GitHub -> inspecter la structure images/labels après
    # clone ; convertir en YOLO si le format diffère.
    dest = RAW / "chv"
    if dest.exists():
        print(f"  {dest} existe déjà, skip clone.")
        return
    subprocess.run(
        ["git", "clone", "--depth", "1",
         "https://github.com/ZijianWang-ZW/PPE_detection", str(dest)],
        check=True,
    )


DATASETS = {
    "sh17": download_sh17,
    "css-data": download_css_data,
    "pictor": download_pictor,
    "chv": download_chv,
}


def main(argv: list[str]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    keys = argv or list(DATASETS)
    for key in keys:
        if key not in DATASETS:
            print(f"[SKIP] dataset inconnu : {key}")
            continue
        print(f"[{key}] téléchargement…")
        try:
            DATASETS[key]()
            print(f"[{key}] OK -> {RAW / key}")
        except Exception as exc:  # une source qui échoue ne bloque pas les autres
            print(f"[{key}] ÉCHEC : {exc}")


if __name__ == "__main__":
    main(sys.argv[1:])
