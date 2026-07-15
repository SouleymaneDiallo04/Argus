from __future__ import annotations

from app.domain.types import BBox, Zone
from app.domain.geometry import bottom_center, point_in_polygon


def resolve_zone(person_bbox: BBox, zones: list[Zone]) -> Zone | None:
    ground_point = bottom_center(person_bbox)
    for zone in zones:
        if point_in_polygon(ground_point, zone.polygon):
            return zone
    return None
