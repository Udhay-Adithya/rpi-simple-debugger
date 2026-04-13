"""rpi-simple-debugger

Beginner-friendly Raspberry Pi debugging helpers.

This package exposes a FastAPI app and background monitors for:

The UI layer can connect over WebSockets to receive live updates.
"""

from __future__ import annotations

from .app import create_app
from .config import DebuggerSettings
from .gpio_backend import GPIOBackendError
from .models import (
    AnalogReading,
    BluetoothStatus,
    GPIOState,
    SystemHealth,
    WiFiStatus,
)
from .server import DebuggerHandle, get_engine, start_debugger_server


def push_custom(name: str, data: dict) -> None:
    """Push a custom debug payload into the debugger stream.

    This is a convenience wrapper around ``DebuggerEngine.push_custom``.
    If the debugger server is not running, the call is a no-op.
    """

    engine = get_engine()
    if engine is None:
        return
    engine.push_custom(name, data)


__all__ = [
    "create_app",
    "DebuggerSettings",
    "start_debugger_server",
    "DebuggerHandle",
    "get_engine",
    "push_custom",
    "GPIOBackendError",
    "GPIOState",
    "WiFiStatus",
    "BluetoothStatus",
    "SystemHealth",
    "AnalogReading",
]
