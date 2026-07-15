from __future__ import annotations

from app.domain.types import BBox, Detection
from app.domain.association import associate


def person(track_id: int, x1, y1, x2, y2) -> Detection:
    return Detection("person", BBox(x1, y1, x2, y2), 0.9, track_id=track_id)


def ppe(cls: str, x1, y1, x2, y2) -> Detection:
    return Detection(cls, BBox(x1, y1, x2, y2), 0.8)


def test_helmet_on_head_associates_to_person():
    p = person(1, 100, 100, 200, 400)          # tête ~ y in [100,190]
    helmet = ppe("helmet", 120, 110, 180, 150)  # centre (150,130), dans la bande tête
    result = associate([p], [helmet])
    assert result == {1: {"helmet"}}


def test_shoes_at_bottom_associate():
    p = person(1, 100, 100, 200, 400)
    shoes = ppe("shoes", 120, 370, 180, 400)    # bas de la personne
    result = associate([p], [shoes])
    assert result == {1: {"shoes"}}


def test_two_persons_helmet_goes_to_the_right_one():
    left = person(1, 0, 100, 100, 400)
    right = person(2, 300, 100, 400, 400)
    helmet = ppe("helmet", 320, 110, 380, 150)  # au-dessus de la personne 2
    result = associate([left, right], [helmet])
    assert result == {2: {"helmet"}}


def test_multiple_ppe_accumulate_per_person():
    p = person(1, 100, 100, 200, 400)
    helmet = ppe("helmet", 120, 110, 180, 150)
    vest = ppe("safety-vest", 110, 200, 190, 300)
    result = associate([p], [helmet, vest])
    assert result == {1: {"helmet", "safety-vest"}}


def test_person_without_ppe_absent_from_map():
    p = person(1, 100, 100, 200, 400)
    result = associate([p], [])
    assert result == {}


def test_ambiguous_ppe_falls_back_to_nearest_person():
    # gant loin de tout containment -> rattaché à la personne la plus proche
    p1 = person(1, 0, 0, 50, 200)
    p2 = person(2, 1000, 0, 1050, 200)
    mask = ppe("mask", 60, 90, 80, 110)         # proche de p1, hors des deux boîtes
    result = associate([p1, p2], [mask])
    assert result == {1: {"mask"}}
