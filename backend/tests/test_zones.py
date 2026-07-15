from __future__ import annotations

from app.domain.types import BBox, Zone
from app.domain.zones import resolve_zone


def _person_at(cx: float, y_bottom: float) -> BBox:
    # boîte de 100x300 dont le bottom-center vaut (cx, y_bottom)
    return BBox(cx - 50, y_bottom - 300, cx + 50, y_bottom)


def test_person_inside_single_zone():
    zone = Zone(
        name="A",
        polygon=[(0, 0), (300, 0), (300, 500), (0, 500)],
        required_ppe=frozenset({"helmet", "safety-vest"}),
    )
    person = _person_at(150, 400)
    resolved = resolve_zone(person, [zone])
    assert resolved is zone


def test_person_outside_all_zones_returns_none():
    zone = Zone(
        name="A",
        polygon=[(0, 0), (300, 0), (300, 500), (0, 500)],
        required_ppe=frozenset({"helmet"}),
    )
    person = _person_at(400, 400)  # bottom-center hors du carré
    assert resolve_zone(person, [zone]) is None


def test_first_matching_zone_wins():
    z1 = Zone("first", [(0, 0), (500, 0), (500, 500), (0, 500)], frozenset({"helmet"}))
    z2 = Zone("second", [(0, 0), (500, 0), (500, 500), (0, 500)], frozenset({"gloves"}))
    person = _person_at(250, 250)
    assert resolve_zone(person, [z1, z2]) is z1


def test_uses_bottom_center_not_box_center():
    # zone couvrant seulement le bas de l'image ; le centre de la boîte est au-dessus
    zone = Zone("floor", [(0, 350), (500, 350), (500, 500), (0, 500)], frozenset({"shoes"}))
    person = _person_at(250, 400)   # bottom-center y=400 -> dans la zone ; center y=250 -> hors
    assert resolve_zone(person, [zone]) is zone
