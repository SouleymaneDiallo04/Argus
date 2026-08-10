from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.domain.types import (
    ComplianceResult,
    Detection,
    FrameResult,
    PPE_CLASSES,
    ViolationEvent,
    Zone,
)


class ZoneModel(BaseModel):
    name: str
    polygon: list[tuple[float, float]]
    required_ppe: list[str]

    @field_validator("polygon")
    @classmethod
    def _min_three_points(cls, v: list) -> list:
        if len(v) < 3:
            raise ValueError("polygon must have at least 3 points")
        return v

    @field_validator("required_ppe")
    @classmethod
    def _known_ppe(cls, v: list) -> list:
        unknown = set(v) - PPE_CLASSES
        if unknown:
            raise ValueError(f"unknown PPE classes: {sorted(unknown)}")
        return v

    def to_domain(self) -> Zone:
        return Zone(self.name, tuple(tuple(p) for p in self.polygon), frozenset(self.required_ppe))

    @classmethod
    def from_domain(cls, zone: Zone) -> "ZoneModel":
        return cls(
            name=zone.name,
            polygon=[list(p) for p in zone.polygon],
            required_ppe=sorted(zone.required_ppe),
        )


class ZonesConfig(BaseModel):
    zones: list[ZoneModel]


class FrameMessage(BaseModel):
    frame: str  # JPEG encodé en base64
    timestamp: float


class RtspSource(BaseModel):
    url: str


def _detection_to_dict(d: Detection) -> dict:
    return {"cls": d.cls, "bbox": [d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2],
            "confidence": d.confidence, "track_id": d.track_id}


def _result_to_dict(r: ComplianceResult) -> dict:
    return {"track_id": r.track_id, "zone": r.zone, "required": sorted(r.required),
            "present": sorted(r.present), "missing": sorted(r.missing), "compliant": r.compliant}


def _event_to_dict(e: ViolationEvent) -> dict:
    return {"track_id": e.track_id, "zone": e.zone, "missing": sorted(e.missing),
            "timestamp": e.timestamp, "camera": e.camera}


def frame_response(detections: list[Detection], result: FrameResult) -> dict:
    return {
        "detections": [_detection_to_dict(d) for d in detections],
        "results": [_result_to_dict(r) for r in result.results],
        "events": [_event_to_dict(e) for e in result.events],
    }
