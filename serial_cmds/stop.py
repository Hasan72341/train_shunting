"""Serial helper issuing the STOP command to the motor controller.

The Arduino firmware is expected to understand a simple ASCII protocol where
sending `STOP\n` halts all motion. This function opens the configured serial
port, writes the command, and returns a boolean to indicate success.
"""
from __future__ import annotations

import logging
from typing import Optional

import serial

from backend import detection_config

LOGGER = logging.getLogger(__name__)
SERIAL_TIMEOUT = 2.0
COMMAND = "STOP\n"


def send(port: Optional[str] = None, baud: Optional[int] = None) -> bool:
    """Transmit the STOP command to the Arduino."""
    port = port or detection_config.SERIAL_PORT_DEFAULT
    baud = baud or detection_config.SERIAL_BAUD_DEFAULT

    try:
        with serial.Serial(port=port, baudrate=baud, timeout=SERIAL_TIMEOUT) as ser:
            LOGGER.info("Sending STOP command to %s @ %d", port, baud)
            ser.write(COMMAND.encode("ascii"))
            ser.flush()
        return True
    except serial.SerialException as exc:
        LOGGER.error("Serial STOP command failed: %s", exc)
        return False
