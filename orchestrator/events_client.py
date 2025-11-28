"""Lightweight SSE client used by the orchestrator to consume YOLO events."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable, Optional

import requests

from backend import detection_config

LOGGER = logging.getLogger(__name__)


class DetectionEventsClient:
    """Subscribes to the YOLO server `/events` SSE stream and forwards payloads."""

    def __init__(self, url: str, on_event: Callable[[dict], None]) -> None:
        self.url = url
        self.on_event = on_event
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="YOLOEvents", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        session = requests.Session()
        backoff = detection_config.SSE_BACKOFF_SEC
        while not self._stop_event.is_set():
            try:
                LOGGER.info("Connecting to YOLO SSE stream at %s", self.url)
                with session.get(self.url, stream=True, timeout=30) as response:
                    response.raise_for_status()
                    event_lines: list[str] = []
                    for line in response.iter_lines(decode_unicode=True):
                        if self._stop_event.is_set():
                            break
                        if line == "":
                            if event_lines:
                                self._dispatch("\n".join(event_lines))
                                event_lines.clear()
                            continue
                        event_lines.append(line)
                backoff = detection_config.SSE_BACKOFF_SEC
            except requests.RequestException as exc:
                LOGGER.warning("SSE connection error: %s", exc)
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

    def _dispatch(self, raw_event: str) -> None:
        data_lines = []
        for line in raw_event.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if not data_lines:
            return
        try:
            payload = json.loads("".join(data_lines))
            self.on_event(payload)
        except json.JSONDecodeError as exc:
            LOGGER.debug("Failed to decode SSE payload: %s", exc)
