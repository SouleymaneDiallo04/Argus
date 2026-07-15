from __future__ import annotations

from dataclasses import dataclass

PPE_CLASSES: frozenset[str] = frozenset(
    {"helmet", "safety-vest", "mask", "shoes"}
)
SUPPORT_CLASSES: frozenset[str] = frozenset({"person", "head", "face"})


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)


@dataclass(frozen=True)
class Detection:
    cls: str
    bbox: BBox
    confidence: float
    track_id: int | None = None


@dataclass(frozen=True)
class Zone:
    name: str
    polygon: tuple[tuple[float, float], ...]
    required_ppe: frozenset[str]

    def __post_init__(self) -> None:
        # Coerce polygon to nested tuples so a frozen Zone is truly hashable,
        # even when callers pass lists.
        object.__setattr__(
            self, "polygon", tuple(tuple(p) for p in self.polygon)
        )


@dataclass(frozen=True)
class ComplianceResult:
    track_id: int
    zone: str | None
    required: frozenset[str]
    present: frozenset[str]
    missing: frozenset[str]
    compliant: bool
