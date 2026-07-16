from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _TrackState:
    anomaly_since: float | None = None
    compliant_since: float | None = None
    in_violation: bool = False
    last_event_ts: float | None = None


class DebounceTracker:
    def __init__(self, confirm_seconds: float, clear_seconds: float, cooldown_seconds: float):
        self.confirm_seconds = confirm_seconds
        self.clear_seconds = clear_seconds
        self.cooldown_seconds = cooldown_seconds
        self._states: dict[int, _TrackState] = {}

    def update(self, track_id: int, compliant: bool, timestamp: float) -> bool:
        st = self._states.setdefault(track_id, _TrackState())

        if not compliant:
            st.compliant_since = None
            if st.anomaly_since is None:
                st.anomaly_since = timestamp
            duration = timestamp - st.anomaly_since
            if not st.in_violation and duration >= self.confirm_seconds:
                cooldown_ok = (
                    st.last_event_ts is None
                    or (timestamp - st.last_event_ts) >= self.cooldown_seconds
                )
                if cooldown_ok:
                    st.in_violation = True
                    st.last_event_ts = timestamp
                    return True
            return False

        # compliant
        st.anomaly_since = None
        if st.compliant_since is None:
            st.compliant_since = timestamp
        if st.in_violation and (timestamp - st.compliant_since) >= self.clear_seconds:
            st.in_violation = False
        return False
