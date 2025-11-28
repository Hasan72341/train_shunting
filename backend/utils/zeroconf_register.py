"""Convenience helpers for advertising services via Zeroconf/mDNS.

Both the detector backend and orchestrator use these utilities to register a
service record with the local Zeroconf daemon. The helpers wrap the underlying
zeroconf API so callers can focus on providing a service name, type, port and
TXT records.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Dict, Optional

from zeroconf import IPVersion, ServiceInfo, Zeroconf

LOGGER = logging.getLogger(__name__)


def _get_address_bytes(host: str) -> bytes:
    """Return network byte order representation for the provided host."""
    addr = ipaddress.ip_address(host)
    return addr.packed


def detect_local_ip(fallback: str = "127.0.0.1") -> str:
    """Attempt to determine the developer machine's primary outbound IP."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        LOGGER.debug("Falling back to %s for zeroconf registration", fallback)
        return fallback


@dataclass
class ZeroconfHandle(AbstractContextManager["ZeroconfHandle"]):
    """Thin wrapper storing zeroconf objects for deterministic cleanup."""

    name: str
    service_type: str
    port: int
    properties: Optional[Dict[str, str]] = None
    address: Optional[str] = None

    def __post_init__(self) -> None:
        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self._info: Optional[ServiceInfo] = None

    def register(self) -> None:
        if self._info is not None:
            LOGGER.debug("Zeroconf service %s already registered", self.name)
            return
        address = self.address or detect_local_ip()
        properties = {k: v.encode("utf-8") for k, v in (self.properties or {}).items()}
        self._info = ServiceInfo(
            type_=self.service_type,
            name=f"{self.name}.{self.service_type}",
            port=self.port,
            addresses=[_get_address_bytes(address)],
            properties=properties,
        )
        LOGGER.info("Registering zeroconf service %s on %s:%d", self.name, address, self.port)
        self.zeroconf.register_service(self._info)

    def unregister(self) -> None:
        if self._info is None:
            return
        LOGGER.info("Unregistering zeroconf service %s", self.name)
        self.zeroconf.unregister_service(self._info)
        self._info = None

    def close(self) -> None:
        LOGGER.debug("Closing zeroconf handle for %s", self.name)
        try:
            self.unregister()
        finally:
            self.zeroconf.close()

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()


def register_service(name: str, service_type: str, port: int, properties: Optional[Dict[str, str]] = None, address: Optional[str] = None) -> ZeroconfHandle:
    """Utility returning a ready-to-use `ZeroconfHandle` context manager."""
    handle = ZeroconfHandle(name=name, service_type=service_type, port=port, properties=properties, address=address)
    handle.register()
    return handle


__all__ = ["ZeroconfHandle", "register_service", "detect_local_ip"]
