"""Terminate processes started by `scripts/init_all.py` using stored PID data."""
from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path

PID_REGISTRY = Path(__file__).resolve().parent / ".pids.json"


def stop_process(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    time.sleep(1.0)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return
    os.kill(pid, signal.SIGKILL)


def main() -> None:
    if not PID_REGISTRY.exists():
        print("No PID registry found; nothing to stop.")
        return

    registry = json.loads(PID_REGISTRY.read_text())
    for name, pid in registry.items():
        print(f"Stopping {name} (pid={pid})")
        stop_process(int(pid))

    PID_REGISTRY.unlink()


if __name__ == "__main__":
    main()
