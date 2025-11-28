"""Bootstrap script to launch the orchestrator (and optionally the frontend) in one go.

Usage summary:
- Starts `python -m orchestrator.main`, which in turn manages the YOLO server.
- When `--dev` is passed, also starts `npm run dev` inside the frontend directory.
- Process IDs are stored in `scripts/.pids.json` so `stop_all.py` can terminate them.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

PID_REGISTRY = Path(__file__).resolve().parent / ".pids.json"
ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"


def spawn_process(command: List[str], cwd: Path | None = None) -> subprocess.Popen[str]:
    print(f"Launching: {' '.join(command)}")
    return subprocess.Popen(command, cwd=str(cwd) if cwd else None)


def record_pids(processes: Dict[str, subprocess.Popen[str]]) -> None:
    PID_REGISTRY.write_text(json.dumps({name: proc.pid for name, proc in processes.items()}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialise the full train-shunting stack")
    parser.add_argument("--dev", action="store_true", help="Start the frontend in Vite dev mode")
    parser.add_argument("--no-frontend", action="store_true", help="Skip launching the frontend entirely")
    parser.add_argument("--wait", action="store_true", help="Block and stream subprocess output")
    args = parser.parse_args()

    processes: Dict[str, subprocess.Popen[str]] = {}
    try:
        orchestrator_cmd = [sys.executable, "-m", "orchestrator.main"]
        processes["orchestrator"] = spawn_process(orchestrator_cmd, cwd=ROOT)

        if not args.no_frontend:
            npm_cmd = ["npm", "run", "dev"] if args.dev else ["npm", "run", "build"]
            processes["frontend"] = spawn_process(npm_cmd, cwd=FRONTEND_DIR)

        record_pids(processes)
        print("Processes started. Use scripts/stop_all.py to terminate.")

        if args.wait:
            for proc in processes.values():
                proc.wait()
    except KeyboardInterrupt:
        print("Interrupted, shutting down launched processes...")
        args.wait = True
    finally:
        if args.wait:
            for name, proc in processes.items():
                if proc.poll() is None:
                    proc.terminate()
                    print(f"Terminated {name} (pid={proc.pid})")
            if PID_REGISTRY.exists():
                PID_REGISTRY.unlink()


if __name__ == "__main__":
    main()
