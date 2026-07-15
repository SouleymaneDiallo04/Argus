from __future__ import annotations

from app.domain.types import BBox
from app.domain.geometry import (
    intersection_area,
    iou,
    containment_ratio,
    center,
    bottom_center,
    point_in_polygon,
)


def test_bbox_properties():
    b = BBox(10, 20, 40, 100)
    assert b.width == 30
    assert b.height == 80
    assert b.area == 2400


def test_intersection_area_overlap():
    a = BBox(0, 0, 10, 10)
    b = BBox(5, 5, 15, 15)
    assert intersection_area(a, b) == 25


def test_intersection_area_disjoint():
    a = BBox(0, 0, 10, 10)
    b = BBox(20, 20, 30, 30)
    assert intersection_area(a, b) == 0


def test_iou_identical_is_one():
    a = BBox(0, 0, 10, 10)
    assert iou(a, a) == 1.0


def test_iou_half_overlap():
    a = BBox(0, 0, 10, 10)      # area 100
    b = BBox(5, 0, 15, 10)      # area 100, inter = 50, union = 150
    assert iou(a, b) == 50 / 150


def test_containment_full_inside():
    inner = BBox(2, 2, 4, 4)    # area 4, fully inside outer
    outer = BBox(0, 0, 10, 10)
    assert containment_ratio(inner, outer) == 1.0


def test_containment_partial():
    inner = BBox(-5, 0, 5, 10)  # area 100, half inside outer
    outer = BBox(0, 0, 10, 10)
    assert containment_ratio(inner, outer) == 0.5


def test_center_and_bottom_center():
    b = BBox(0, 0, 100, 300)
    assert center(b) == (50.0, 150.0)
    assert bottom_center(b) == (50.0, 300.0)


def test_point_in_polygon_inside_and_outside():
    square = [(0, 0), (300, 0), (300, 500), (0, 500)]
    assert point_in_polygon((150, 400), square) is True
    assert point_in_polygon((400, 400), square) is False


def test_point_in_polygon_triangle():
    tri = [(0, 0), (10, 0), (0, 10)]
    assert point_in_polygon((1, 1), tri) is True
    assert point_in_polygon((9, 9), tri) is False
