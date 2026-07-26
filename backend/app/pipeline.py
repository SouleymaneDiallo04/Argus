from __future__ import annotations

from app.domain.engine import ComplianceEngine
from app.domain.types import Detection, FrameResult, Zone


class FramePipeline:
    """Orchestration temps réel : frame -> détections -> moteur de conformité.

    `detector` doit exposer `.detect(frame) -> list[Detection]`. Renvoie aussi les
    détections brutes (pour les overlays d'affichage) en plus du FrameResult.
    """

    def __init__(self, detector, zones: list[Zone], **engine_kwargs):
        self._detector = detector
        self._engine = ComplianceEngine(zones, **engine_kwargs)

    def process(self, frame, timestamp: float) -> tuple[list[Detection], FrameResult]:
        detections = self._detector.detect(frame)
        result = self._engine.process_frame(detections, timestamp)
        return detections, result
