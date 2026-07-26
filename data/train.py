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
