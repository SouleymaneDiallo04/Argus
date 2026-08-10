from __future__ import annotations

from datetime import datetime


def ingest_frame(journal, snapshots, notifier, frame, detections, result,
                 now: datetime) -> None:
    """Snapshot flouté (si infraction) + persistance + notifications, tolérant aux pannes.

    Partagé par le handler WS et le worker RTSP.
    """
    snapshot = None
    if result.events and snapshots is not None:
        try:
            persons = [d.bbox for d in detections if d.cls == "person"]
            snapshot = snapshots.save(frame, persons)
        except Exception:
            snapshot = None  # preuve indisponible ne bloque pas le journal
    try:
        journal.record_frame(result, now, snapshot)
    except Exception:
        pass  # une panne de persistance ne doit pas tuer le flux
    if notifier is not None:
        for event in result.events:
            try:
                notifier.notify(event)
            except Exception:
                pass  # une panne de notification ne doit pas tuer le flux
