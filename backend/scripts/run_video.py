from __future__ import annotations

"""Validation P1 : fait tourner le pipeline sur une vidéo, dessine les overlays,
imprime les événements d'infraction. Aucun frontend.

Usage :
    py backend/scripts/run_video.py --model best.pt --video sample.mp4 --required helmet
    (ajouter --show pour l'affichage fenêtré, --save out.mp4 pour écrire la vidéo annotée)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ sur le path

import cv2  # noqa: E402

from app.domain.types import Zone  # noqa: E402
from app.inference.detector import PPEDetector  # noqa: E402
from app.pipeline import FramePipeline  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="chemin du modèle .pt ou .onnx")
    ap.add_argument("--video", required=True, help="chemin de la vidéo")
    ap.add_argument("--required", default="helmet", help="EPI requis, séparés par des virgules")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--save", default=None, help="chemin de sortie vidéo annotée (optionnel)")
    args = ap.parse_args()

    required = frozenset(args.required.split(","))
    detector = PPEDetector.from_path(args.model)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"Impossible d'ouvrir la vidéo : {args.video}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    zone = Zone("all", [(0, 0), (width, 0), (width, height), (0, height)], required)
    pipe = FramePipeline(detector, [zone])

    writer = None
    if args.save:
        writer = cv2.VideoWriter(
            args.save, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )

    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        timestamp = frame_idx / fps
        detections, result = pipe.process(frame, timestamp)

        status = {r.track_id: r.compliant for r in result.results}
        for d in detections:
            b = d.bbox
            if d.cls == "person":
                color = (0, 255, 0) if status.get(d.track_id, True) else (0, 0, 255)
            else:
                color = (255, 200, 0)
            cv2.rectangle(frame, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), color, 2)
            cv2.putText(frame, d.cls, (int(b.x1), int(b.y1) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        for e in result.events:
            print(f"[{e.timestamp:5.1f}s] INFRACTION id={e.track_id} "
                  f"manque={sorted(e.missing)} zone={e.zone}")

        if writer is not None:
            writer.write(frame)
        if args.show:
            cv2.imshow("Argus", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        frame_idx += 1

    cap.release()
    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()
    print(f"Terminé : {frame_idx} frames traitées.")


if __name__ == "__main__":
    main()
