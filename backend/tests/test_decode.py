from __future__ import annotations

import base64

import cv2
import numpy as np
import pytest

from app.api.decode import decode_frame


def _tiny_jpeg_b64() -> str:
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return base64.b64encode(buf.tobytes()).decode("ascii")


def test_decode_frame_returns_image():
    img = decode_frame(_tiny_jpeg_b64())
    assert img.shape == (8, 8, 3)


def test_decode_frame_rejects_bad_base64():
    with pytest.raises(ValueError):
        decode_frame("not@@base64")


def test_decode_frame_rejects_non_image_bytes():
    # base64 valide mais pas une image
    b64 = base64.b64encode(b"hello world not an image").decode("ascii")
    with pytest.raises(ValueError):
        decode_frame(b64)
