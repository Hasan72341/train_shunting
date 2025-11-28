# Train Shunting Prototype

This repository contains a laptop-friendly robotics prototype that couples an
ultralytics YOLO detector with an Arduino-powered shunting rig. The system is
split into a detection backend, a safety orchestrator, and a lightweight React
dashboard that exposes status information and manual overrides.

## Quick Start

1. **Install Python dependencies** (Python 3.10+):
	 ```bash
	 python -m venv .venv
	 source .venv/bin/activate
	 pip install -r requirements.txt
	 ```
2. **Install frontend dependencies**:
	 ```bash
	 cd frontend
	 npm install
	 ```
3. **Launch everything**:
	 ```bash
	 python scripts/init_all.py --dev
	 ```
	 The orchestrator listens on `http://localhost:8000`, while the detector runs
	 on `http://localhost:8001`. The Vite dev server binds to `http://localhost:5173`.

Stop all background processes with:

```bash
python scripts/stop_all.py
```

## Components Overview

- `backend/`
	- `yolo_server.py` — FastAPI service that captures frames, runs YOLO
		detections, broadcasts SSE events, and registers an mDNS record.
	- `detection_config.py` — Shared configuration defaults (classes, ports,
		timings). Values can be overridden via `.env`.
	- `serial_discovery.py` — Utility functions to list candidate serial ports.
	- `utils/zeroconf_register.py` — Shared Zeroconf registration helper.
	- `utils/discovery_http.py` — Function to mount a `/_discover` endpoint.
- `orchestrator/`
	- `main.py` — Supervises the detector subprocess, handles detection events,
		triggers serial safety commands, exposes manual command endpoints, and
		registers an mDNS record for frontend discovery.
	- `events_client.py` — Basic SSE client used by the orchestrator.
	- `mdns_discover.py` — Convenience Zeroconf discovery helper.
- `serial_cmds/` — One-module-per-command helpers (`stop`, `forward`, `reverse`)
	that send ASCII messages to the Arduino via pyserial.
- `frontend/` — Vite + React UI that discovers the orchestrator, streams
	detection events, shows the latest frame, and provides manual overrides.
- `scripts/`
	- `init_all.py` — Starts the orchestrator (and optional frontend) while
		recording PIDs.
	- `stop_all.py` — Terminates processes recorded by `init_all.py`.

## Environment Configuration

Copy `.env.example` to `.env` and adjust values for your hardware:

```bash
cp .env.example .env
```

Key settings include:

- `WATCH_CLASSES` — Comma-separated YOLO labels that trigger safety actions.
- `CAMERA_SOURCE` — Camera index (e.g. `0`) or path to a video file.
- `SERIAL_PORT` and `SERIAL_BAUD` — Connection parameters for your Arduino.
- `REVERSE_DURATION` and `STOP_TO_REVERSE_DELAY` — Timing tweaks for movement.

## Serial Command Wiring

The Arduino firmware must understand the following newline-terminated ASCII
commands:

- `STOP` — Immediately halt all motion.
- `FWD:<speed>` — Move forward using the provided integer PWM percentage.
- `REV:<speed>:<duration>` — Move in reverse for the specified seconds.

Each helper in `serial_cmds/` translates function arguments into this protocol
and returns `True` on success.

## Development Tips

- Use `uvicorn orchestrator.main:app --reload --port 8000` to run the
	orchestrator with auto-reload during development (the orchestrator will still
	spawn the detector subprocess).
- When no physical camera is attached, point `CAMERA_SOURCE` at a video file
	for repeatable testing.
- The frontend polls `/last_frame` every few seconds, so make sure the
	orchestrator can reach the detector endpoint.

## Testing Hardware Integration

- Run `python -m serial_cmds.stop` (after adding a `__main__` block if desired)
	or call the functions from an interactive session to verify serial
	connectivity before enabling the orchestrator safety sequence.
- Confirm that `zeroconf` is advertising both `_yolo._tcp.local.` and
	`_robot._tcp.local.` using tools like `dns-sd -B _robot._tcp local`.

## License

This prototype is intended for internal experimentation and should be audited
before use on safety-critical hardware.
