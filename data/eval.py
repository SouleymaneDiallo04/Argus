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
