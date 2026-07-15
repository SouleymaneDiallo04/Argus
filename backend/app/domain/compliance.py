from __future__ import annotations

from app.domain.types import Zone, ComplianceResult


def evaluate(track_id: int, present: set[str], zone: Zone | None) -> ComplianceResult:
    required = zone.required_ppe if zone is not None else frozenset()
    present_fs = frozenset(present)
    missing = required - present_fs
    return ComplianceResult(
        track_id=track_id,
        zone=zone.name if zone is not None else None,
        required=frozenset(required),
        present=present_fs,
        missing=missing,
        compliant=len(missing) == 0,
    )
