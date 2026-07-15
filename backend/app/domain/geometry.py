from __future__ import annotations

from app.domain.types import BBox


def intersection_area(a: BBox, b: BBox) -> float:
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    w = max(0.0, ix2 - ix1)
    h = max(0.0, iy2 - iy1)
    return w * h


def iou(a: BBox, b: BBox) -> float:
    inter = intersection_area(a, b)
    union = a.area + b.area - inter
    if union <= 0:
        return 0.0
    return inter / union


def containment_ratio(inner: BBox, outer: BBox) -> float:
    if inner.area <= 0:
        return 0.0
    return intersection_area(inner, outer) / inner.area


def center(b: BBox) -> tuple[float, float]:
    return ((b.x1 + b.x2) / 2.0, (b.y1 + b.y2) / 2.0)


def bottom_center(b: BBox) -> tuple[float, float]:
    return ((b.x1 + b.x2) / 2.0, b.y2)


def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    # Ray casting. Points on the edge are treated as inside is not guaranteed;
    # tests use clearly interior/exterior points.
    x, y = point
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside
