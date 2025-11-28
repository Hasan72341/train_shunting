"""Main orchestrator coordinating the YOLO detector and Arduino commands.

Responsibilities covered here:
- Launch the YOLO FastAPI server in a subprocess using uvicorn and ensure it is healthy.
- Register the orchestrator itself via Zeroconf (`_robot._tcp.local.`) for frontend discovery.
- Consume detection events from the detector (SSE) and trigger serial safety commands.
- Expose a FastAPI API offering manual overrides (`/cmd/*`) and discovery (`/_discover`).
- Gracefully clean up subprocesses and zeroconf resources on shutdown.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional

import requests
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

try:  # pragma: no cover - optional convenience import
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from backend import detection_config
from backend.utils.discovery_http import create_discovery_router
from backend.utils.zeroconf_register import ZeroconfHandle, detect_local_ip, register_service
from serial_cmds import forward, reverse, stop

from .events_client import DetectionEventsClient

LOGGER = logging.getLogger("orchestrator.main")


class OrchestratorRuntime:
    """Stateful runtime driving the safety logic and background processes."""

    def __init__(self) -> None:
        self.yolo_process: Optional[subprocess.Popen[str]] = None
        self.zeroconf_handle: Optional[ZeroconfHandle] = None
        self.events_client: Optional[DetectionEventsClient] = None
        self.event_log: Deque[Dict[str, object]] = deque(maxlen=detection_config.MAX_EVENT_LOG_SIZE)
        self.last_detection: Optional[Dict[str, object]] = None
        self.serial_lock = threading.Lock()
        self._serial_cooldown = 0.0
        self._shutdown = threading.Event()

    def start(self) -> None:
        logging.basicConfig(level=logging.INFO)
        self._launch_yolo_server()
        self._wait_for_yolo_health()
        self._start_event_client()
        self._register_mdns()

    def stop(self) -> None:
        self._shutdown.set()
        if self.events_client:
            self.events_client.stop()
            self.events_client = None
        if self.zeroconf_handle:
            self.zeroconf_handle.close()
            self.zeroconf_handle = None
        if self.yolo_process:
            LOGGER.info("Stopping YOLO server subprocess")
            self._terminate_process(self.yolo_process)
            self.yolo_process = None

    # --- YOLO process management -------------------------------------------------

    def _launch_yolo_server(self) -> None:
        if self.yolo_process and self.yolo_process.poll() is None:
            LOGGER.info("YOLO server already running")
            return
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.yolo_server:app",
            "--host",
            detection_config.YOLO_SERVER_HOST,
            "--port",
            str(detection_config.YOLO_SERVER_PORT),
        ]
        env = os.environ.copy()
        LOGGER.info("Launching YOLO server: %s", " ".join(command))
        self.yolo_process = subprocess.Popen(command, env=env)

    def _wait_for_yolo_health(self, timeout: float = 45.0) -> None:
        url = f"http://{detection_config.YOLO_SERVER_HOST}:{detection_config.YOLO_SERVER_PORT}/health"
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.yolo_process and self.yolo_process.poll() is not None:
                LOGGER.error("YOLO server exited early with code %s", self.yolo_process.returncode)
                raise RuntimeError("YOLO server process terminated unexpectedly")
            try:
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    LOGGER.info("YOLO health endpoint reachable")
                    return
            except requests.RequestException:
                pass
            time.sleep(1)
        raise TimeoutError(f"Timed out waiting for YOLO health endpoint at {url}")

    def _terminate_process(self, process: subprocess.Popen[str], wait: float = 5.0) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            LOGGER.warning("Force killing subprocess %s", process.pid)
            process.kill()

    # --- Event handling ----------------------------------------------------------

    def _start_event_client(self) -> None:
        url = f"http://{detection_config.YOLO_SERVER_HOST}:{detection_config.YOLO_SERVER_PORT}/events"
        self.events_client = DetectionEventsClient(url=url, on_event=self._handle_event)
        self.events_client.start()

    def _handle_event(self, event: dict) -> None:
        if event.get("type") != "detection":
            return
        payload = event.get("payload") or {}
        label = payload.get("label")
        if not label:
            return
        LOGGER.debug("Received detection event: %s", payload)
        self.last_detection = payload
        self.event_log.appendleft(payload)
        if label in detection_config.WATCH_CLASSES:
            self._execute_safety_sequence(payload)

    def _execute_safety_sequence(self, payload: dict) -> None:
        now = time.time()
        with self.serial_lock:
            if now - self._serial_cooldown < detection_config.REVERSE_DURATION:
                LOGGER.debug("Skipping serial actions due to cooldown")
                return
            LOGGER.info("Triggering safety sequence for label=%s", payload.get("label"))
            stop.send()
            time.sleep(detection_config.STOP_TO_REVERSE_DELAY)
            reverse.send(duration=detection_config.REVERSE_DURATION)
            self._serial_cooldown = time.time()
            if detection_config.RESUME_WITH_FORWARD:
                time.sleep(detection_config.FORWARD_RESUME_DELAY)
                forward.send()

    # --- Zeroconf ---------------------------------------------------------------

    def _register_mdns(self) -> None:
        address = detect_local_ip()
        self.zeroconf_handle = register_service(
            name=detection_config.MDNS_ORCHESTRATOR_NAME,
            service_type=detection_config.MDNS_SERVICE_TYPE_ORCHESTRATOR,
            port=detection_config.ORCHESTRATOR_PORT,
            properties={"path": "/", "detector": f"{detection_config.YOLO_SERVER_HOST}:{detection_config.YOLO_SERVER_PORT}"},
            address=address,
        )


runtime = OrchestratorRuntime()

app = FastAPI(title="Train Shunting Orchestrator", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(
    create_discovery_router(
        host_resolver=lambda: detect_local_ip(),
        port_resolver=lambda: detection_config.ORCHESTRATOR_PORT,
        extra_payload=lambda: {
            "detector_host": detection_config.YOLO_SERVER_HOST,
            "detector_port": detection_config.YOLO_SERVER_PORT,
            "service": detection_config.MDNS_ORCHESTRATOR_NAME,
        },
    )
)


def get_runtime() -> OrchestratorRuntime:
    return runtime


@app.on_event("startup")
async def on_startup() -> None:
    runtime.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    runtime.stop()


@app.get("/status", tags=["orchestrator"])
async def get_status(rt: OrchestratorRuntime = Depends(get_runtime)) -> Dict[str, object]:
    return {
        "last_detection": rt.last_detection,
        "event_log": list(rt.event_log),
        "watch_classes": list(detection_config.WATCH_CLASSES),
    }


@app.get("/last_detection", tags=["orchestrator"])
async def last_detection(rt: OrchestratorRuntime = Depends(get_runtime)) -> Dict[str, object]:
    if rt.last_detection is None:
        raise HTTPException(status_code=404, detail="No detections yet")
    return rt.last_detection


def _proxy_yolo(path: str) -> requests.Response:
    url = f"http://{detection_config.YOLO_SERVER_HOST}:{detection_config.YOLO_SERVER_PORT}{path}"
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response


@app.get("/last_frame", tags=["orchestrator"])
async def proxy_last_frame() -> Dict[str, object]:
    response = _proxy_yolo("/last_frame")
    return response.json()


@app.post("/cmd/stop", tags=["commands"])
async def cmd_stop() -> Dict[str, bool]:
    return {"ok": stop.send()}


@app.post("/cmd/forward", tags=["commands"])
async def cmd_forward(speed: int = 100) -> Dict[str, bool]:
    return {"ok": forward.send(speed=speed)}


@app.post("/cmd/reverse", tags=["commands"])
async def cmd_reverse(speed: int = 80, duration: float = detection_config.REVERSE_DURATION) -> Dict[str, bool]:
    return {"ok": reverse.send(speed=speed, duration=duration)}


def _handle_sigterm(signum, frame) -> None:  # pragma: no cover - signal handler
    LOGGER.info("Received signal %s, shutting down orchestrator", signum)
    runtime.stop()
    sys.exit(0)


signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("orchestrator.main:app", host=detection_config.ORCHESTRATOR_HOST, port=detection_config.ORCHESTRATOR_PORT, reload=False)
