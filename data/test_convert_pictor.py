from __future__ import annotations

from convert_pictor import boxes_to_yolo, parse_pictor_line


def test_parse_pictor_line_real_sample():
    # Extrait réel d'un fichier approach-01.
    name, boxes = parse_pictor_line(
        "image_from_china(1).jpg 992,366,1040,511,2 1000,366,1040,385,0"
    )
    assert name == "image_from_china(1).jpg"
    assert boxes == [(2, 992, 366, 1040, 511), (0, 1000, 366, 1040, 385)]


def test_parse_pictor_line_empty():
    assert parse_pictor_line("") == (None, [])


def test_boxes_to_yolo_normalizes():
    # box (0,0,100,200) dans une image 200x400 -> centre (50,100) -> (0.25, 0.25),
    # largeur 100/200=0.5, hauteur 200/400=0.5.
    out = boxes_to_yolo([(2, 0, 0, 100, 200)], 200, 400)
    assert out == ["2 0.250000 0.250000 0.500000 0.500000"]


def test_boxes_to_yolo_keeps_source_class_id():
    # Le convertisseur préserve l'ID Pictor (0=hat) ; le remap Argus vient après.
    out = boxes_to_yolo([(0, 10, 10, 30, 50)], 100, 100)
    assert out[0].startswith("0 ")
