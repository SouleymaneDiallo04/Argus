from __future__ import annotations

from app.domain.types import (
    Detection,
    Zone,
    ViolationEvent,
    FrameResult,
    PPE_CLASSES,
)
from app.domain.association import associate
from app.domain.zones import resolve_zone
from app.domain.compliance import evaluate
from app.domain.debounce import DebounceTracker


class ComplianceEngine:
    def __init__(
        self,
        zones: list[Zone],
        confirm_seconds: float = 3.0,
        clear_seconds: float = 3.0,
        cooldown_seconds: float = 30.0,
        camera: str = "cam-1",
        containment_threshold: float = 0.5,
    ):
        self.zones = zones
        self.camera = camera
        self.containment_threshold = containment_threshold
        self.debounce = DebounceTracker(confirm_seconds, clear_seconds, cooldown_seconds)

    def process_frame(self, detections: list[Detection], timestamp: float) -> FrameResult:
        persons = [d for d in detections if d.cls == "person" and d.track_id is not None]
        ppe = [d for d in detections if d.cls in PPE_CLASSES]
        assoc = associate(persons, ppe, self.containment_threshold)

        results = []
        events = []
        for p in persons:
            present = assoc.get(p.track_id, set())
            zone = resolve_zone(p.bbox, self.zones)
            res = evaluate(p.track_id, present, zone)
            results.append(res)
            if self.debounce.update(p.track_id, res.compliant, timestamp):
                events.append(
                    ViolationEvent(
                        track_id=p.track_id,
                        zone=res.zone,
                        missing=res.missing,
                        timestamp=timestamp,
                        camera=self.camera,
                    )
                )
        return FrameResult(results=results, events=events)
