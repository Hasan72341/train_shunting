"""FastAPI YOLO detector server.

Specification implemented:
- Opens a camera (cv2.VideoCapture) and shares the latest frame as base64.
- Loads an ultralytics YOLO model and performs detections in a background thread.
- Exposes `/health`, `/last_frame`, `/events` (SSE), and `/detect_once` endpoints.
- Broadcasts detection events to the orchestrator via server-sent events.
- Registers and unregisters an mDNS service (`_yolo._tcp.local.`) on lifecycle events.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import threading
import time
from typing import Any, Dict, AsyncGenerator, List, Optional

import cv2
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

try:  # pragma: no cover - optional convenience import
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from . import detection_config
from .utils.discovery_http import create_discovery_router
from .utils.zeroconf_register import ZeroconfHandle, register_service, detect_local_ip

LOGGER = logging.getLogger("backend.yolo_server")

try:
    from ultralytics import YOLO
except ImportError as exc:  # pragma: no cover - resolved at runtime when deps installed
    raise RuntimeError(
        "ultralytics package is required. Install with `pip install ultralytics`."
    ) from exc


def _parse_camera_source(source: str) -> int | str:
    """Convert camera environment variable into OpenCV-compatible input."""
    if isinstance(source, int):
        return source
    if source.isdigit():
        return int(source)
    return source


class DetectionState:
    """Holds shared mutable state for the detection loop and API layers."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_detection: Optional[Dict[str, Any]] = None
        self.last_frame_b64: Optional[str] = None
        self.event_queues: List[asyncio.Queue[Dict[str, Any]]] = []
        self.model: Optional[YOLO] = None
        self.capture: Optional[cv2.VideoCapture] = None
        self.stop_event = threading.Event()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.zeroconf_handle: Optional[ZeroconfHandle] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def init_model(self) -> None:
        if self.model is not None:
            return
        LOGGER.info("Loading YOLO model: %s", detection_config.YOLO_MODEL_PATH)
        self.model = YOLO(detection_config.YOLO_MODEL_PATH)

    def init_camera(self) -> None:
        if self.capture is not None and self.capture.isOpened():
            return
        source = _parse_camera_source(str(detection_config.CAMERA_SOURCE))
        LOGGER.info("Opening camera source %s", source)
        self.capture = cv2.VideoCapture(source)
        if not self.capture.isOpened():
            raise RuntimeError(f"Unable to open camera source: {source}")

    def update_frame(self, frame) -> None:
        success, buffer = cv2.imencode(".png", frame)
        if not success:
            LOGGER.debug("Failed to encode frame for last_frame endpoint")
            return
        b64 = base64.b64encode(buffer).decode("ascii")
        with self.lock:
            self.last_frame_b64 = b64

    def update_detection(self, detection: Dict[str, Any]) -> None:
        with self.lock:
            self.last_detection = detection

    def register_queue(self) -> asyncio.Queue[Dict[str, Any]]:
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        with self.lock:
            self.event_queues.append(queue)
        return queue

    def unregister_queue(self, queue: asyncio.Queue[Dict[str, Any]]) -> None:
        with self.lock:
            if queue in self.event_queues:
                self.event_queues.remove(queue)

    def broadcast(self, payload: Dict[str, Any]) -> None:
        """Push payload onto every subscriber queue in a thread-safe fashion."""
        with self.lock:
            queues = list(self.event_queues)
        for queue in queues:
            if self.loop is None:
                continue
            asyncio.run_coroutine_threadsafe(queue.put(payload), self.loop)

    def close(self) -> None:
        self.stop_event.set()
        if self.capture is not None:
            LOGGER.info("Releasing camera")
            self.capture.release()
        if self.zeroconf_handle is not None:
            self.zeroconf_handle.close()
            self.zeroconf_handle = None


state = DetectionState()

app = FastAPI(title="YOLO Detection Server", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
    allow_credentials=True,
)

app.include_router(
    create_discovery_router(
        host_resolver=lambda: detect_local_ip(),
        port_resolver=lambda: detection_config.YOLO_SERVER_PORT,
        extra_payload=lambda: {"service": detection_config.MDNS_DETECTOR_NAME},
    )
)


def get_detection_state() -> DetectionState:
    return state


def _detection_loop() -> None:
    LOGGER.info("Starting detection loop")
    last_emit = 0.0
    assert state.model is not None
    assert state.capture is not None

    while not state.stop_event.is_set():
        ret, frame = state.capture.read()
        if not ret:
            LOGGER.warning("Camera read failed; retrying")
            time.sleep(1.0)
            continue

        state.update_frame(frame)

        now = time.time()
        if now - last_emit < detection_config.CAPTURE_INTERVAL_SEC:
            time.sleep(0.01)
            continue
        last_emit = now

        results = state.model(frame, verbose=False)
        detections = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_idx = int(box.cls)
                label = r.names.get(cls_idx, str(cls_idx)) if hasattr(r, "names") else str(cls_idx)
                conf = float(box.conf)
                if label not in detection_config.WATCH_CLASSES:
                    continue
                detection_payload = {
                    "label": label,
                    "confidence": conf,
                    "bbox": box.xyxy.tolist()[0],  # type: ignore[call-arg]
                    "timestamp": now,
                }
                detections.append(detection_payload)

        if detections:
            top = max(detections, key=lambda d: d["confidence"])
            LOGGER.info("Detected %s (%.2f)", top["label"], top["confidence"])
            state.update_detection(top)
            state.broadcast({"type": "detection", "payload": top})

    LOGGER.info("Detection loop terminated")


@app.on_event("startup")
async def on_startup() -> None:
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_running_loop()
    state.set_event_loop(loop)
    state.init_model()
    try:
        state.init_camera()
    except RuntimeError as exc:
        LOGGER.error(exc)
        raise

    state.zeroconf_handle = register_service(
        name=detection_config.MDNS_DETECTOR_NAME,
        service_type=detection_config.MDNS_SERVICE_TYPE_DETECTOR,
        port=detection_config.YOLO_SERVER_PORT,
        properties={"path": "/", "health": "/health"},
    )

    threading.Thread(target=_detection_loop, name="YOLODetection", daemon=True).start()
    LOGGER.info("YOLO detector online")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    state.close()


@app.get("/health", tags=["health"])
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/last_frame", tags=["frames"])
async def last_frame(state: DetectionState = Depends(get_detection_state)) -> Dict[str, Any]:
    with state.lock:
        if state.last_frame_b64 is None:
            raise HTTPException(status_code=404, detail="No frame captured yet")
        payload = state.last_detection or {}
        return {"image_b64": state.last_frame_b64, "last_detection": payload}


@app.post("/detect_once", tags=["detection"])
async def detect_once(state: DetectionState = Depends(get_detection_state)) -> Dict[str, Any]:
    if state.model is None or state.capture is None:
        raise HTTPException(status_code=500, detail="Detector not initialised")
    ret, frame = state.capture.read()
    if not ret:
        raise HTTPException(status_code=503, detail="Failed to capture frame")

    results = state.model(frame, verbose=False)
    body: List[Dict[str, Any]] = []
    for r in results:
        boxes = r.boxes
        if boxes is None:
            continue
        for box in boxes:
            cls_idx = int(box.cls)
            label = r.names.get(cls_idx, str(cls_idx)) if hasattr(r, "names") else str(cls_idx)
            conf = float(box.conf)
            body.append({
                "label": label,
                "confidence": conf,
                "bbox": box.xyxy.tolist()[0],  # type: ignore[call-arg]
            })
    return {"detections": body}


async def _event_publisher(queue: asyncio.Queue[Dict[str, Any]]) -> AsyncGenerator[Dict[str, str], None]:
    try:
        while True:
            payload = await queue.get()
            yield {"event": payload.get("type", "message"), "data": json.dumps(payload)}
    except asyncio.CancelledError:  # pragma: no cover - lifecycle detail
        raise
    finally:
        state.unregister_queue(queue)


@app.get("/events", tags=["events"])
async def events_endpoint() -> Response:
    queue = state.register_queue()
    return EventSourceResponse(_event_publisher(queue))
