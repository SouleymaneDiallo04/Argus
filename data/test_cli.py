from __future__ import annotations

import eval as evaluate
import train


def test_train_defaults():
    args = train.parse_args(["--data", "d.yaml"])
    assert args.imgsz == 960
    assert args.epochs == 50
    assert args.batch == 8
    assert args.model == "yolov8n.pt"


def test_train_overrides():
    args = train.parse_args(["--data", "d.yaml", "--imgsz", "1280", "--batch", "4"])
    assert args.imgsz == 1280 and args.batch == 4


def test_eval_defaults():
    args = evaluate.parse_args(["--model", "best.pt", "--data", "d.yaml"])
    assert args.imgsz == 960 and args.split == "val"
