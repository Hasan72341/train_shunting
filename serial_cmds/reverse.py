"""Serial helper issuing REVERSE commands to recover from detected obstacles.

The Arduino firmware should support `REV:<speed>:<duration>\n` where speed is a
percentage PWM value and duration is measured in seconds. This helper writes the
proper message and optionally allows callers to tweak the defaults.
"""
from __future__ import annotations

import logging
from typing import Optional

import serial

from backend import detection_config

LOGGER = logging.getLogger(__name__)
SERIAL_TIMEOUT = 2.0
COMMAND_TEMPLATE = "REV:{speed}:{duration}\n"


def send(port: Optional[str] = None, baud: Optional[int] = None, speed: int = 80, duration: float = 1.5) -> bool:
    """Send a REVERSE command. Returns True on success."""
    port = port or detection_config.SERIAL_PORT_DEFAULT
    baud = baud or detection_config.SERIAL_BAUD_DEFAULT

    try:
        with serial.Serial(port=port, baudrate=baud, timeout=SERIAL_TIMEOUT) as ser:
            command = COMMAND_TEMPLATE.format(speed=speed, duration=duration)
            LOGGER.info(
                "Sending REVERSE(speed=%s,duration=%s) to %s @ %d",
                speed,
                duration,
                port,
                baud,
            )
            ser.write(command.encode("ascii"))
            ser.flush()
        return True
    except serial.SerialException as exc:
        LOGGER.error("Serial REVERSE command failed: %s", exc)
        return False
