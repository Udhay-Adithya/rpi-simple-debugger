from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from .config import DebuggerSettings, load_settings
from .engine import DebuggerEngine
from .gpio_monitor import GPIOMonitor
from .models import GPIOState, SystemHealth, WiFiStatus, BluetoothStatus
from .network_monitor import NetworkMonitor
from .system_monitor import SystemMonitor


def create_app(settings: DebuggerSettings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="rpi-simple-debugger", version="0.1.0")
    engine = DebuggerEngine(settings=settings, version="0.1.0")
    app.state.engine = engine

    # Monitors
    gpio_monitor: GPIOMonitor | None = None
    if settings.gpio_enabled:
        # Default to all BCM pins that are generally safe inputs for Pi 3/4.
        default_pins = [2, 3, 4, 17, 18, 22, 23, 24, 25, 27]

        def on_gpio_change(state: GPIOState) -> None:
            engine.update_gpio(state)

        gpio_monitor = GPIOMonitor(
            pins=default_pins,
            label_map=settings.gpio_label_map,
            interval_s=settings.gpio_poll_interval_s,
            on_change=on_gpio_change,
        )

    def on_wifi(status: WiFiStatus) -> None:
        engine.update_wifi(status)

    def on_bt(status: BluetoothStatus) -> None:
        engine.update_bluetooth(status)

    def on_system(health: SystemHealth) -> None:
        engine.update_system(health)

    network_monitor: NetworkMonitor | None = None
    if settings.wifi_enabled or settings.bluetooth_enabled:
        network_monitor = NetworkMonitor(
            interval_s=settings.network_poll_interval_s,
            on_wifi=on_wifi,
            on_bt=on_bt,
        )

    system_monitor: SystemMonitor | None = None
    if settings.system_health_enabled:
        system_monitor = SystemMonitor(
            interval_s=settings.system_poll_interval_s,
            on_update=on_system,
        )

    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover - integration behavior
        if gpio_monitor is not None:
            gpio_monitor.start()
        if network_monitor is not None:
            network_monitor.start()
        if system_monitor is not None:
            system_monitor.start()

        # Send an initial meta broadcast so connected clients quickly
        # understand capabilities.
        await engine.send_meta()

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # pragma: no cover - integration behavior
        if gpio_monitor is not None:
            gpio_monitor.stop()
        if network_monitor is not None:
            network_monitor.stop()
        if system_monitor is not None:
            system_monitor.stop()

    @app.get("/status")
    async def get_status() -> JSONResponse:
        """Return the most recent snapshot for easy polling UIs."""

        snapshot = app.state.engine.snapshot
        # Ensure datetimes and other non-JSON-native types are encoded.
        return JSONResponse(snapshot.model_dump(mode="json"))

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:  # pragma: no cover
        manager = app.state.engine.manager
        await manager.connect(websocket)
        try:
            # For now, the client does not need to send anything.
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app
