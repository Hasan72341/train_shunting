"""Serial helper for issuing a FORWARD command with configurable speed.

The Arduino firmware should parse messages formatted as `FWD:<speed>\n` where
speed is an integer PWM percentage. This module mirrors that expectation so
higher-level orchestrator code can simply call `forward.send(speed=120)`.
"""
from __future__ import annotations

import logging
from typing import Optional

import serial

from backend import detection_config

LOGGER = logging.getLogger(__name__)
SERIAL_TIMEOUT = 2.0
COMMAND_TEMPLATE = "FWD:{speed}\n"


def send(port: Optional[str] = None, baud: Optional[int] = None, speed: int = 100) -> bool:
    """Send a FORWARD command. Returns True if the serial exchange succeeded."""
    port = port or detection_config.SERIAL_PORT_DEFAULT
    baud = baud or detection_config.SERIAL_BAUD_DEFAULT

    try:
        with serial.Serial(port=port, baudrate=baud, timeout=SERIAL_TIMEOUT) as ser:
            command = COMMAND_TEMPLATE.format(speed=speed)
            LOGGER.info("Sending FORWARD(%s) command to %s @ %d", speed, port, baud)
            ser.write(command.encode("ascii"))
            ser.flush()
        return True
    except serial.SerialException as exc:
        LOGGER.error("Serial FORWARD command failed: %s", exc)
        return False
