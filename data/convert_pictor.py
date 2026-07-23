from __future__ import annotations

"""Convertit les annotations Pictor-v3 (Approche A1, format keras-yolo3 consolidé)
vers du YOLO standard : un .txt par image, coordonnées normalisées.

Format source (UNE ligne par image, séparé par des espaces/tabs) :
    image.jpg  x1,y1,x2,y2,cls  x1,y1,x2,y2,cls  ...
où (x1,y1,x2,y2) = coins absolus en PIXELS, cls = entier.
Classes A1 : 0 = hat, 1 = vest, 2 = worker (ordre déduit géométriquement).

`parse_pictor_line` et `boxes_to_yolo` sont purs et testés. `convert_pictor_file`
lit les tailles d'images (PIL) et écrit les .txt — exécuté sur Colab.
"""


def parse_pictor_line(line: str):
    """'img.jpg x1,y1,x2,y2,cls ...' -> (nom_image, [(cls, x1, y1, x2, y2), ...])."""
    parts = line.split()
    if not parts:
        return None, []
    name = parts[0]
    boxes = []
    for tok in parts[1:]:
        vals = tok.split(",")
        if len(vals) != 5:
            continue
        x1, y1, x2, y2, cls = (int(float(v)) for v in vals)
        boxes.append((cls, x1, y1, x2, y2))
    return name, boxes


def boxes_to_yolo(boxes, width: int, height: int) -> list[str]:
    """Coins absolus (px) -> lignes YOLO normalisées '<cls> xc yc w h'."""
    out = []
    for cls, x1, y1, x2, y2 in boxes:
        xc = ((x1 + x2) / 2) / width
        yc = ((y1 + y2) / 2) / height
        w = (x2 - x1) / width
        h = (y2 - y1) / height
        out.append(f"{cls} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
    return out


def convert_pictor_file(label_file, images_dir, out_labels_dir) -> dict[str, int]:
    """Convertit un fichier de labels Pictor consolidé en .txt YOLO par image.

    Lit la taille de chaque image via PIL (nécessaire pour normaliser). Renvoie
    {images, boxes, missing} (missing = images référencées mais introuvables).
    """
    from pathlib import Path

    from PIL import Image

    images_dir, out = Path(images_dir), Path(out_labels_dir)
    out.mkdir(parents=True, exist_ok=True)
    images = boxes = missing = 0
    for line in Path(label_file).read_text(encoding="utf-8").splitlines():
        name, parsed = parse_pictor_line(line)
        if not name:
            continue
        img_path = images_dir / name
        if not img_path.exists():
            missing += 1
            continue
        with Image.open(img_path) as im:
            width, height = im.size
        (out / (Path(name).stem + ".txt")).write_text(
            "\n".join(boxes_to_yolo(parsed, width, height)) + "\n", encoding="utf-8"
        )
        images += 1
        boxes += len(parsed)
    return {"images": images, "boxes": boxes, "missing": missing}
