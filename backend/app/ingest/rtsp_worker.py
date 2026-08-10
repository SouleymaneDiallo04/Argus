from __future__ import annotations

import threading


class RtspWorker:
    """Ingestion d'un flux RTSP dans un thread : read -> handle(frame, ts), throttlé."""

    def __init__(self, url: str, handle, capture_factory=None, fps: float = 5.0):
        if capture_factory is None:
            import cv2
            capture_factory = cv2.VideoCapture
        self._url = url
        self._handle = handle
        self._cap_factory = capture_factory
        self._interval = 1.0 / fps
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.frames = 0
        self.error: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        cap = self._cap_factory(self._url)
        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                try:
                    self._handle(frame, self.frames * self._interval)
                except Exception as exc:  # une frame défaillante ne tue pas l'ingestion
                    self.error = str(exc)
                self.frames += 1
                self._stop.wait(self._interval)  # throttle interruptible
        finally:
            cap.release()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def status(self) -> dict:
        running = self._thread is not None and self._thread.is_alive()
        return {"running": running, "url": self._url, "frames": self.frames,
                "error": self.error}
