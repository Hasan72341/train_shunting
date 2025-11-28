"""Serial port discovery helpers used during local development.

The prototype does not assume a particular Arduino port; instead we use
pyserial's tools to enumerate connected serial devices and offer helper
functions that attempt to pick the most likely candidate. Developers can use
these utilities to print debug information before wiring the orchestrator to
real hardware.
"""
from __future__ import annotations

from typing import Iterable, Optional

try:
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - pyserial is a runtime dependency.
    list_ports = None  # type: ignore[assignment]


def iter_serial_ports() -> Iterable[str]:
    """Yield device paths for each detected serial port, if pyserial is available."""
    if list_ports is None:
        return []
    return (port.device for port in list_ports.comports())


def find_default_serial_port(preferred_substrings: Optional[list[str]] = None) -> Optional[str]:
    """Return the first serial port that loosely matches the provided hints.

    Parameters
    ----------
    preferred_substrings:
        Optional list of substrings (e.g. "usb", "ttyACM") that help choose the
        most likely Arduino-compatible port.
    """
    ports = list(iter_serial_ports())
    if not ports:
        return None

    if not preferred_substrings:
        preferred_substrings = ["usb", "ttyacm", "wch", "ch340"]

    for substring in preferred_substrings:
        for port in ports:
            if substring.lower() in port.lower():
                return port

    return ports[0]


__all__ = ["iter_serial_ports", "find_default_serial_port"]
