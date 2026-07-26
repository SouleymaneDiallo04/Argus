from __future__ import annotations

import base64

import cv2
import numpy as np


def decode_frame(b64: str) -> np.ndarray:
    """Décode une frame JPEG encodée en base64 vers une image BGR OpenCV.

    Lève ValueError si le base64 est invalide ou si l'image est illisible.
    """
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception as exc:
        raise ValueError("base64 invalide") from exc
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("frame illisible (décodage image échoué)")
    return img
