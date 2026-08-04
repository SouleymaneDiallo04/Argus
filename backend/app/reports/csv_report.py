from __future__ import annotations

import csv
import io

_HEADER = ["Heure", "Zone", "Personne", "EPI manquants", "Caméra", "Preuve"]


def events_csv(events: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_HEADER)
    for e in events:
        writer.writerow([
            e.get("ts", ""),
            e.get("zone") or "",
            f"#{e['track_id']}",
            ", ".join(e.get("missing", [])),
            e.get("camera", ""),
            e.get("snapshot") or "",
        ])
    return buf.getvalue()
