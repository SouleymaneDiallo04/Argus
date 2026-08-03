from __future__ import annotations

import numpy as np

from app.domain.types import BBox
from app.evidence.redaction import blur_head_regions, head_region


def test_head_region_is_full_width_top_30pct():
    # bbox x 100..200, y 100..300 (hauteur 200) -> tête = y 100..160, pleine largeur
    assert head_region(BBox(100, 100, 200, 300)) == (100, 100, 200, 160)


def test_blur_changes_head_region_only():
    rng = np.random.default_rng(0)
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    img[100:160, 100:200] = rng.integers(0, 256, (60, 100, 3), dtype=np.uint8)
    low = img[250:260, 100:200].copy()
    out = blur_head_regions(img, [BBox(100, 100, 200, 300)])
    assert np.array_equal(out[250:260, 100:200], low)              # zone basse intacte
    assert not np.array_equal(out[100:160, 100:200], img[100:160, 100:200])  # tête pixelisée


def test_blur_ignores_degenerate_and_offscreen():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    out = blur_head_regions(img, [BBox(10, 10, 10, 10), BBox(500, 500, 600, 700)])
    assert out.shape == img.shape                                  # aucune exception
