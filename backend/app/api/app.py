from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.api.decode import decode_frame
from app.api.schemas import FrameMessage, ZonesConfig, frame_response
from app.api.zones_store import ZonesStore
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
                snapshot = None
                if result.events:
                    try:
                        persons = [d.bbox for d in detections if d.cls == "person"]
                        snapshot = await run_in_threadpool(
                            app.state.snapshots.save, frame, persons)
                    except Exception:
                        snapshot = None  # preuve indisponible ne bloque pas le journal
                try:
                    await run_in_threadpool(
                        app.state.journal.record_frame, result,
                        datetime.now(timezone.utc), snapshot)
                except Exception:
                    pass  # une panne de persistance ne doit pas tuer le flux live
                for event in result.events:
                    try:
                        await run_in_threadpool(app.state.notifier.notify, event)
                    except Exception:
                        pass  # une panne de notification ne doit pas tuer le flux
                await ws.send_json(frame_response(detections, result))
        except WebSocketDisconnect:
            return

    return app
