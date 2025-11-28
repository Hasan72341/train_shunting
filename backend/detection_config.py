"""Configuration shared between the detection backend and orchestrator.

This module centralises tunable values such as which YOLO classes trigger
responses, camera selection, detection cadence, and network ports. The values
are deliberately overridable via environment variables so that developers can
adjust behaviour without editing code.
"""
from __future__ import annotations

import os
from typing import Set

WATCH_CLASSES: Set[str] = {
    cls.strip()
    for cls in os.getenv("WATCH_CLASSES", "person,bottle").split(",")
    if cls.strip()
}
"""YOLO labels that should trigger stop/reverse safety behaviour."""

YOLO_MODEL_PATH: str = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")
"""Model file name understood by ultralytics.YOLO."""

CAMERA_SOURCE: int | str = os.getenv("CAMERA_SOURCE", "0")
"""Default camera index or path to video file used for detection."""

CAPTURE_INTERVAL_SEC: float = float(os.getenv("CAPTURE_INTERVAL_SEC", "0.5"))
"""Minimum interval between detector runs while streaming frames."""

YOLO_SERVER_HOST: str = os.getenv("YOLO_SERVER_HOST", "127.0.0.1")
YOLO_SERVER_PORT: int = int(os.getenv("YOLO_SERVER_PORT", "8001"))

ORCHESTRATOR_HOST: str = os.getenv("ORCHESTRATOR_HOST", "0.0.0.0")
ORCHESTRATOR_PORT: int = int(os.getenv("ORCHESTRATOR_PORT", "8000"))

MDNS_SERVICE_TYPE_DETECTOR = os.getenv("MDNS_SERVICE_TYPE_DETECTOR", "_yolo._tcp.local.")
MDNS_SERVICE_TYPE_ORCHESTRATOR = os.getenv("MDNS_SERVICE_TYPE_ORCHESTRATOR", "_robot._tcp.local.")
MDNS_DETECTOR_NAME = os.getenv("MDNS_DETECTOR_NAME", "YOLO-Detector")
MDNS_ORCHESTRATOR_NAME = os.getenv("MDNS_ORCHESTRATOR_NAME", "TrainShunting-Orchestrator")

SERIAL_PORT_DEFAULT = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUD_DEFAULT = int(os.getenv("SERIAL_BAUD", "115200"))

STOP_TO_REVERSE_DELAY: float = float(os.getenv("STOP_TO_REVERSE_DELAY", "1.0"))
REVERSE_DURATION: float = float(os.getenv("REVERSE_DURATION", "1.5"))
FORWARD_RESUME_DELAY: float = float(os.getenv("FORWARD_RESUME_DELAY", "1.0"))
RESUME_WITH_FORWARD: bool = os.getenv("RESUME_WITH_FORWARD", "true").lower() in {"1", "true", "yes"}

SSE_BACKOFF_SEC: float = float(os.getenv("SSE_BACKOFF_SEC", "2.0"))
"""Delay before retrying the YOLO event stream when the connection drops."""

MAX_EVENT_LOG_SIZE: int = int(os.getenv("MAX_EVENT_LOG_SIZE", "100"))
"""Limit for storing recent detection events within the orchestrator."""
