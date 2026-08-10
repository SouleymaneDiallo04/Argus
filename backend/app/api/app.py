from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import ValidationError

from app.api.decode import decode_frame
from app.api.schemas import FrameMessage, RtspSource, ZonesConfig, frame_response
from app.api.zones_store import ZonesStore
from app.ingest.frame_sink import ingest_frame
from app.ingest.rtsp_worker import RtspWorker
from app.pipeline import FramePipeline


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # les tests pré-injectent un stub -> on saute le chargement du vrai modèle
        if app.state.detector is None:
            from app.inference.detector import PPEDetector

            path = os.environ.get("ARGUS_MODEL_PATH", "best.pt")
            app.state.detector = PPEDetector.from_path(path)
        if app.state.journal is None:
            from app.persistence.journal import Journal

            app.state.journal = Journal(os.environ.get("ARGUS_DB_PATH", "argus.db"))
        if app.state.snapshots is None:
            from app.evidence.snapshots import SnapshotStore

            app.state.snapshots = SnapshotStore(
                os.environ.get("ARGUS_SNAPSHOT_DIR", "snapshots"))
        if app.state.notifier is None:
            from app.notify.factory import build_dispatcher

            app.state.notifier = build_dispatcher()
        yield

    app = FastAPI(title="Argus", lifespan=lifespan)
    origins = [o.strip() for o in os.environ.get(
        "ARGUS_CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.zones_store = ZonesStore()
    app.state.detector = None            # remplacé par un stub dans les tests
    app.state.journal = None             # remplacé par un Journal(":memory:") dans les tests
    app.state.snapshots = None           # remplacé par un SnapshotStore(tmp) dans les tests
    app.state.notifier = None            # remplacé par un dispatcher espion dans les tests
    app.state.rtsp = None                # worker RTSP courant (un seul flux)
    app.state.rtsp_capture_factory = None  # None -> cv2.VideoCapture ; injecté en test
    app.state.decode = decode_frame

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model_loaded": app.state.detector is not None}

    @app.get("/zones")
    def get_zones() -> ZonesConfig:
        return app.state.zones_store.to_config()

    @app.put("/zones")
    def put_zones(config: ZonesConfig) -> ZonesConfig:
        app.state.zones_store.set_from_config(config)
        return app.state.zones_store.to_config()

    @app.get("/events")
    def get_events(
        zone: str | None = None,
        ppe: str | None = None,
        since: str | None = None,
        until: str | None = None,
        camera: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        return {"events": app.state.journal.events(
            zone=zone, ppe=ppe, since=since, until=until,
            camera=camera, limit=limit, offset=offset)}

    @app.get("/stats")
    def get_stats(
        since: str | None = None,
        until: str | None = None,
        zone: str | None = None,
    ) -> dict:
        return app.state.journal.stats(since=since, until=until, zone=zone)

    @app.get("/events/{event_id}/snapshot")
    def get_event_snapshot(event_id: int):
        event = app.state.journal.event(event_id)
        if event is None or event["snapshot"] is None:
            raise HTTPException(status_code=404, detail="snapshot introuvable")
        path = app.state.snapshots.path(event["snapshot"])
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="fichier snapshot absent")
        return FileResponse(path, media_type="image/jpeg")

    @app.get("/reports/events.csv")
    def report_events_csv(
        zone: str | None = None,
        ppe: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> Response:
        from app.reports.csv_report import events_csv

        events = app.state.journal.events(
            zone=zone, ppe=ppe, since=since, until=until, limit=1000)
        return Response(
            content=events_csv(events), media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="argus-events.csv"'})

    @app.get("/reports/summary.pdf")
    def report_summary_pdf(
        since: str | None = None,
        until: str | None = None,
        zone: str | None = None,
    ) -> Response:
        from app.reports.pdf_report import summary_pdf

        stats = app.state.journal.stats(since=since, until=until, zone=zone)
        events = app.state.journal.events(zone=zone, since=since, until=until, limit=1000)
        meta = {
            "site": os.environ.get("ARGUS_SITE", "Meknès-Nord"),
            "since": since, "until": until,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }
        return Response(
            content=summary_pdf(stats, events, meta), media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="argus-rapport.pdf"'})

    @app.post("/sources/rtsp")
    def start_rtsp(source: RtspSource) -> dict:
        if app.state.rtsp is not None:
            app.state.rtsp.stop()
        app.state.detector.reset()
        pipeline = FramePipeline(
            app.state.detector, app.state.zones_store.get_zones(), camera="rtsp")

        def handle(frame, ts):
            detections, result = pipeline.process(frame, ts)
            ingest_frame(app.state.journal, app.state.snapshots, app.state.notifier,
                         frame, detections, result, datetime.now(timezone.utc))

        factory = app.state.rtsp_capture_factory
        if factory is None:
            import cv2
            factory = cv2.VideoCapture
        worker = RtspWorker(source.url, handle, capture_factory=factory)
        worker.start()
        app.state.rtsp = worker
        return worker.status()

    @app.delete("/sources/rtsp")
    def stop_rtsp() -> dict:
        if app.state.rtsp is not None:
            app.state.rtsp.stop()
            app.state.rtsp = None
        return {"stopped": True}

    @app.get("/sources/rtsp")
    def rtsp_status() -> dict:
        return app.state.rtsp.status() if app.state.rtsp is not None else {"running": False}

    @app.websocket("/ws/stream")
    async def stream(ws: WebSocket) -> None:
        await ws.accept()
        app.state.detector.reset()  # nouveau flux : réinitialise le tracker
        pipeline = FramePipeline(app.state.detector, app.state.zones_store.get_zones())
        try:
            while True:
                try:
                    data = await ws.receive_json()  # json.loads -> ValueError (JSONDecodeError) si non-JSON
                    msg = FrameMessage(**data)
                    frame = app.state.decode(msg.frame)
                except (ValidationError, ValueError) as exc:
                    await ws.send_json({"error": str(exc)})
                    continue
                try:
                    detections, result = pipeline.process(frame, msg.timestamp)
                except Exception as exc:  # une frame défaillante ne doit pas tuer le flux
                    await ws.send_json({"error": str(exc)})
                    continue
                await run_in_threadpool(
                    ingest_frame, app.state.journal, app.state.snapshots,
                    app.state.notifier, frame, detections, result,
                    datetime.now(timezone.utc))
                await ws.send_json(frame_response(detections, result))
        except WebSocketDisconnect:
            return

    return app
