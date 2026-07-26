from __future__ import annotations

import pytest

from oversample import _rewrite_train_in_yaml, oversampled_image_list


def _make_pair(images_dir, labels_dir, stem, cls_ids):
    (images_dir / f"{stem}.jpg").write_bytes(b"x")
    lines = "\n".join(f"{c} 0.5 0.5 0.2 0.2" for c in cls_ids)
    (labels_dir / f"{stem}.txt").write_text(lines + "\n", encoding="utf-8")


def test_oversamples_shoe_images_and_keeps_others_once(tmp_path):
    images, labels = tmp_path / "images", tmp_path / "labels"
    images.mkdir(); labels.mkdir()
    _make_pair(images, labels, "a_with_shoes", [0, 4])
    _make_pair(images, labels, "b_no_shoes", [0, 1])
    _make_pair(images, labels, "c_with_shoes", [4])

    paths = oversampled_image_list(labels, images, shoe_class_id=4, factor=3)
    names = [p.name for p in paths]
    assert names.count("a_with_shoes.jpg") == 3
    assert names.count("c_with_shoes.jpg") == 3
    assert names.count("b_no_shoes.jpg") == 1
    assert len(paths) == 7


def test_factor_one_is_no_oversampling(tmp_path):
    images, labels = tmp_path / "images", tmp_path / "labels"
    images.mkdir(); labels.mkdir()
    _make_pair(images, labels, "s", [4])
    _make_pair(images, labels, "n", [0])
    assert len(oversampled_image_list(labels, images, shoe_class_id=4, factor=1)) == 2


def test_skips_label_without_matching_image(tmp_path):
    images, labels = tmp_path / "images", tmp_path / "labels"
    images.mkdir(); labels.mkdir()
    (labels / "orphan.txt").write_text("4 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    assert oversampled_image_list(labels, images) == []


def test_rewrite_train_replaces_only_train_line():
    text = "path: /d\ntrain: train/images\nval: val/images\nnames:\n  0: person\n"
    out = _rewrite_train_in_yaml(text, "/abs/train.txt")
    assert "train: /abs/train.txt" in out
    assert "val: val/images" in out and "path: /d" in out
    assert "train: train/images" not in out


def test_rewrite_train_raises_if_absent():
    with pytest.raises(ValueError):
        _rewrite_train_in_yaml("path: /d\nval: v\n", "/abs/train.txt")
