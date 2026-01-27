from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import DebuggerSettings, load_settings
from .engine import DebuggerEngine
from .gpio_monitor import GPIOMonitor
from .models import DebuggerMessage, GPIOState, NetInterfaceStats, SystemHealth, WiFiStatus, BluetoothStatus
from .network_monitor import NetworkMonitor
from .system_monitor import SystemMonitor


def create_app(settings: DebuggerSettings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(title="rpi-simple-debugger", version="0.1.0")

    # Add CORS middleware if enabled (for web dashboards)
    if settings.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    engine = DebuggerEngine(settings=settings, version="0.1.0")
    app.state.engine = engine

    # Monitors - use configurable GPIO pins
    gpio_monitor: GPIOMonitor | None = None
    monitored_pins = settings.effective_gpio_pins
    if settings.gpio_enabled:

        def on_gpio_change(state: GPIOState) -> None:
            engine.update_gpio(state)

        gpio_monitor = GPIOMonitor(
            pins=monitored_pins,
            label_map=settings.gpio_label_map,
            interval_s=settings.gpio_poll_interval_s,
            on_change=on_gpio_change,
            backend=settings.gpio_backend,
        )
        # Populate gpio_schema with monitored pins
        engine.set_gpio_schema(monitored_pins, settings.gpio_label_map)

    def on_wifi(status: WiFiStatus) -> None:
        engine.update_wifi(status)

    def on_bt(status: BluetoothStatus) -> None:
        engine.update_bluetooth(status)

    def on_interfaces(interfaces: List[NetInterfaceStats]) -> None:
        engine.update_interfaces(interfaces)

    def on_system(health: SystemHealth) -> None:
        engine.update_system(health)

    network_monitor: NetworkMonitor | None = None
    if settings.wifi_enabled or settings.bluetooth_enabled:
        network_monitor = NetworkMonitor(
            interval_s=settings.network_poll_interval_s,
            on_wifi=on_wifi,
            on_bt=on_bt,
            on_interfaces=on_interfaces,
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
        engine_instance: DebuggerEngine = app.state.engine
        manager = engine_instance.manager
        await manager.connect(websocket)

        # Send current snapshot immediately so new clients have full state
        try:
            snapshot_data = engine_instance.snapshot.model_dump(mode="json")
            await websocket.send_json({
                "type": "snapshot",
                "data": snapshot_data,
            })
        except Exception:
            manager.disconnect(websocket)
            return

        try:
            # Handle incoming messages (for heartbeat ping-pong)
            while True:
                message = await websocket.receive_text()
                # Respond to ping with pong for connection health monitoring
                if message == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app
