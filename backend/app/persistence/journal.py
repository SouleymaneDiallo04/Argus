from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime

from app.domain.types import FrameResult, ViolationEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    stream_ts REAL NOT NULL,
    camera TEXT NOT NULL,
    zone TEXT,
    track_id INTEGER NOT NULL,
    missing TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_zone ON events(zone);
CREATE TABLE IF NOT EXISTS observations (
    bucket TEXT NOT NULL,
    zone TEXT NOT NULL,
    person_frames INTEGER NOT NULL DEFAULT 0,
    compliant_frames INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket, zone)
);
"""


def _rate_row(pf: int, cf: int) -> dict:
    return {"person_frames": pf, "compliant_frames": cf,
            "rate": (cf / pf) if pf else None}


class Journal:
    """Repository SQLite du journal d'infractions + agrégats de conformité."""

    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # --- écriture ---
    def record_event(self, event: ViolationEvent, ts: datetime) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (ts, stream_ts, camera, zone, track_id, missing) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts.isoformat(), event.timestamp, event.camera, event.zone,
                 event.track_id, json.dumps(sorted(event.missing))),
            )
            self._conn.commit()

    # --- lecture ---
    def events(self, *, zone=None, ppe=None, since=None, until=None, camera=None,
               limit=100, offset=0) -> list[dict]:
        clauses, params = [], []
        if zone is not None:
            clauses.append("zone = ?"); params.append(zone)
        if ppe is not None:
            clauses.append("missing LIKE ?"); params.append(f'%"{ppe}"%')
        if since is not None:
            clauses.append("ts >= ?"); params.append(since)
        if until is not None:
            clauses.append("ts <= ?"); params.append(until)
        if camera is not None:
            clauses.append("camera = ?"); params.append(camera)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        limit = max(1, min(int(limit), 1000))
        rows = self._conn.execute(
            f"SELECT id, ts, stream_ts, camera, zone, track_id, missing FROM events"
            f"{where} ORDER BY ts DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, int(offset)),
        ).fetchall()
        return [
            {"id": r["id"], "ts": r["ts"], "stream_ts": r["stream_ts"],
             "camera": r["camera"], "zone": r["zone"], "track_id": r["track_id"],
             "missing": json.loads(r["missing"])}
            for r in rows
        ]
