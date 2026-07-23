from __future__ import annotations

from fuse import collect_pairs, find_image, split_pairs


def test_split_pairs_sizes_determinism_and_no_leak():
    pairs = list(range(100))
    tr1, va1 = split_pairs(pairs, val_frac=0.1, seed=42)
    assert len(va1) == 10 and len(tr1) == 90
    # déterministe
    tr2, va2 = split_pairs(pairs, val_frac=0.1, seed=42)
    assert (tr1, va1) == (tr2, va2)
    # pas de fuite train/val
    assert set(tr1).isdisjoint(va1)


def test_find_image_matches_extension(tmp_path):
    (tmp_path / "img1.png").write_text("x", encoding="utf-8")
    assert find_image(tmp_path, "img1").name == "img1.png"
    assert find_image(tmp_path, "absent") is None


def test_collect_pairs_skips_empty_labels_and_tags_source(tmp_path):
    labels = tmp_path / "labels"
    labels.mkdir()
    images = tmp_path / "images"
    images.mkdir()
    (labels / "a.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    (labels / "b.txt").write_text("", encoding="utf-8")  # vide -> ignoré
    (images / "a.jpg").write_text("x", encoding="utf-8")
    (images / "b.jpg").write_text("x", encoding="utf-8")
    pairs = collect_pairs([(labels, images, "ds")])
    assert len(pairs) == 1
    assert pairs[0][0].name == "a.txt"
    assert pairs[0][2] == "ds"
