"""Helpers for discovering services advertised via Zeroconf."""
from __future__ import annotations

def discover_first(service_type: str, timeout: float = 3.0) -> Optional[dict]:
import logging
import threading
from typing import Optional

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

LOGGER = logging.getLogger(__name__)


def discover_first(service_type: str, timeout: float = 3.0) -> Optional[dict]:
    """Block briefly while searching for a Zeroconf service and return metadata."""
    zeroconf = Zeroconf()
    found: dict[str, str] | None = None
    event = threading.Event()

    def _on_service_change(zeroconf_obj: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        nonlocal found
        if state_change is ServiceStateChange.Added and found is None:
            info = zeroconf_obj.get_service_info(service_type, name)
            if info is None:
                return
            addresses = [addr for addr in info.parsed_scoped_addresses()]
            found = {
                "name": name,
                "port": str(info.port),
                "addresses": ",".join(addresses),
            }
            event.set()

    ServiceBrowser(zeroconf, service_type, handlers=[_on_service_change])

    event.wait(timeout)
    zeroconf.close()
    if found:
        LOGGER.info("Discovered service %s", found)
    return found
