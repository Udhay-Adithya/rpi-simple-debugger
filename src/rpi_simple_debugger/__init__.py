"""rpi-simple-debugger

Beginner-friendly Raspberry Pi debugging helpers.

This package exposes a FastAPI app and background monitors for:
- GPIO digital pin state
- WiFi/Bluetooth connectivity
- System health (CPU temperature, disk usage)

The UI layer can connect over WebSockets to receive live updates.
"""

from .app import create_app

__all__ = ["create_app"]
