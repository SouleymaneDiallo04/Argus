from __future__ import annotations

from dataclasses import dataclass

PPE_CLASSES: frozenset[str] = frozenset(
    {"helmet", "safety-vest", "mask", "gloves", "glasses", "shoes"}
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
