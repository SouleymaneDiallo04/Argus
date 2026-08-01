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

    def record_observations(self, bucket: str, zone: str,
                            person_frames: int, compliant_frames: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO observations (bucket, zone, person_frames, compliant_frames) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(bucket, zone) DO UPDATE SET "
                "  person_frames = person_frames + excluded.person_frames, "
                "  compliant_frames = compliant_frames + excluded.compliant_frames",
                (bucket, zone, person_frames, compliant_frames),
            )
            self._conn.commit()

    # --- lecture ---
    def stats(self, *, since=None, until=None, zone=None) -> dict:
        obs_clauses, obs_params = [], []
        if zone is not None:
            obs_clauses.append("zone = ?"); obs_params.append(zone)
        else:
            obs_clauses.append("zone <> ''")                      # exclut hors-zone
        if since is not None:
            obs_clauses.append("bucket >= ?"); obs_params.append(since[:16])
        if until is not None:
            obs_clauses.append("bucket <= ?"); obs_params.append(until[:16])
        obs_where = " WHERE " + " AND ".join(obs_clauses)

        g = self._conn.execute(
            f"SELECT COALESCE(SUM(person_frames), 0) pf, "
            f"COALESCE(SUM(compliant_frames), 0) cf FROM observations{obs_where}",
            obs_params,
        ).fetchone()
        global_stat = _rate_row(g["pf"], g["cf"])

        by_zone = [
            {"zone": r["zone"], **_rate_row(r["pf"], r["cf"])}
            for r in self._conn.execute(
                f"SELECT zone, SUM(person_frames) pf, SUM(compliant_frames) cf "
                f"FROM observations{obs_where} GROUP BY zone ORDER BY zone", obs_params,
            ).fetchall()
        ]
        over_time = [
            {"bucket": r["bucket"], **_rate_row(r["pf"], r["cf"])}
            for r in self._conn.execute(
                f"SELECT bucket, SUM(person_frames) pf, SUM(compliant_frames) cf "
                f"FROM observations{obs_where} GROUP BY bucket ORDER BY bucket", obs_params,
            ).fetchall()
        ]

        ev_clauses, ev_params = [], []
        if zone is not None:
            ev_clauses.append("zone = ?"); ev_params.append(zone)
        if since is not None:
            ev_clauses.append("ts >= ?"); ev_params.append(since)
        if until is not None:
            ev_clauses.append("ts <= ?"); ev_params.append(until)
        ev_where = (" WHERE " + " AND ".join(ev_clauses)) if ev_clauses else ""
        total = self._conn.execute(
            f"SELECT COUNT(*) n FROM events{ev_where}", ev_params).fetchone()["n"]
        by_zone_v = {
            r["zone"]: r["n"]
            for r in self._conn.execute(
                f"SELECT zone, COUNT(*) n FROM events{ev_where} GROUP BY zone", ev_params,
            ).fetchall()
        }
        return {"global": global_stat, "by_zone": by_zone,
                "over_time": over_time,
                "violations": {"total": total, "by_zone": by_zone_v}}

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
