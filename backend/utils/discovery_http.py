"""Utility helpers for discovery HTTP endpoints shared across services.

The frontend performs a simple REST call to discover the orchestrator's host
and port. This module exposes a convenience function that injects a `_discover`
route into any FastAPI application so code stays DRY when multiple services
need similar metadata.
"""
from __future__ import annotations

from typing import Callable, Dict

from fastapi import APIRouter


def create_discovery_router(host_resolver: Callable[[], str], port_resolver: Callable[[], int], extra_payload: Callable[[], Dict[str, str]] | None = None) -> APIRouter:
    """Return a router exposing `/_discover` that describes the current service."""
    router = APIRouter()

    @router.get("/_discover", tags=["discovery"])
    def discover() -> Dict[str, object]:
        payload: Dict[str, object] = {"host": host_resolver(), "port": port_resolver()}
        if extra_payload is not None:
            payload.update(extra_payload())
        return payload

    return router


__all__ = ["create_discovery_router"]
