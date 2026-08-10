from __future__ import annotations

from app.ingest.rtsp_worker import RtspWorker


class _FakeCap:
    def __init__(self, n):
        self._n = n
        self.released = False

    def read(self):
        if self._n > 0:
            self._n -= 1
            return True, "FRAME"
        return False, None

    def release(self):
        self.released = True


def test_worker_processes_all_frames_then_stops():
    calls = []
    cap = _FakeCap(3)
    w = RtspWorker("rtsp://x", handle=lambda f, ts: calls.append(f),
                   capture_factory=lambda url: cap, fps=1000)
    w.start()
    w._thread.join(timeout=3)          # se termine seul après 3 frames
    assert calls == ["FRAME", "FRAME", "FRAME"]
    assert w.status()["frames"] == 3
    assert w.status()["running"] is False
    assert cap.released is True


def test_worker_stop_is_idempotent():
    w = RtspWorker("rtsp://x", handle=lambda f, ts: None,
                   capture_factory=lambda url: _FakeCap(0), fps=1000)
    w.start()
    w.stop()
    w.stop()                            # ne lève pas
    assert w.status()["running"] is False
