from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import DebuggerSettings, load_settings
from .engine import DebuggerEngine
from .gpio_backend import GPIOBackendError
from .gpio_monitor import GPIOMonitor
from .models import DebuggerMessage, GPIOState, NetInterfaceStats, SystemHealth, WiFiStatus, BluetoothStatus
from .network_monitor import NetworkMonitor
from .system_monitor import SystemMonitor

logger = logging.getLogger(__name__)


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

        try:
            gpio_monitor = GPIOMonitor(
                pins=monitored_pins,
                label_map=settings.gpio_label_map,
                interval_s=settings.gpio_poll_interval_s,
                on_change=on_gpio_change,
                backend=settings.gpio_backend,
            )
            # Populate gpio_schema with monitored pins
            engine.set_gpio_schema(monitored_pins, settings.gpio_label_map)
        except GPIOBackendError as exc:
            logger.error("GPIO monitoring disabled: %s", exc)
            gpio_monitor = None

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

    # ----- GPIO Output Controller -----
    output_backend = None
    if settings.gpio_output_pins:
        try:
            from .gpio_backend import LibgpiodOutputBackend, RPiGPIOOutputBackend

            # Try RPi.GPIO output first, then libgpiod
            try:
                output_backend = RPiGPIOOutputBackend()
            except GPIOBackendError:
                output_backend = LibgpiodOutputBackend()

            for pin in settings.gpio_output_pins:
                output_backend.setup_output(pin)
        except GPIOBackendError as exc:
            logger.error("GPIO output disabled: %s", exc)
            output_backend = None

    app.state.output_backend = output_backend

    # ----- Analog Input Monitor -----
    analog_backend = None
    if settings.analog_enabled and settings.analog_channels:
        try:
            from .gpio_backend import ADS1115Backend, MCP3008Backend

            if settings.analog_backend == "ads1115":
                analog_backend = ADS1115Backend(
                    bus=settings.analog_i2c_bus,
                    address=settings.analog_i2c_address,
                )
            else:
                analog_backend = MCP3008Backend(
                    bus=settings.analog_spi_bus,
                    device=settings.analog_spi_device,
                )

            for ch in settings.analog_channels:
                analog_backend.setup_channel(ch)
        except GPIOBackendError as exc:
            logger.error("Analog input disabled: %s", exc)
            analog_backend = None

    app.state.analog_backend = analog_backend

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
        if output_backend is not None:
            output_backend.cleanup()
        if analog_backend is not None:
            analog_backend.cleanup()

    @app.get("/status")
    async def get_status() -> JSONResponse:
        """Return the most recent snapshot for easy polling UIs."""

        snapshot = app.state.engine.snapshot
        # Ensure datetimes and other non-JSON-native types are encoded.
        return JSONResponse(snapshot.model_dump(mode="json"))

    @app.post("/gpio/{pin}")
    async def set_gpio_output(pin: int, value: int) -> JSONResponse:
        """Set a GPIO output pin to HIGH (1) or LOW (0)."""
        if output_backend is None:
            return JSONResponse(
                {"error": "GPIO output is not configured or unavailable."},
                status_code=503,
            )
        if settings.gpio_output_pins and pin not in settings.gpio_output_pins:
            return JSONResponse(
                {"error": f"Pin {pin} is not configured as an output pin."},
                status_code=400,
            )
        if value not in (0, 1):
            return JSONResponse(
                {"error": "Value must be 0 or 1."},
                status_code=400,
            )
        try:
            output_backend.write(pin, value)
            return JSONResponse({"pin": pin, "value": value, "status": "ok"})
        except GPIOBackendError as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @app.get("/analog")
    async def get_analog_readings() -> JSONResponse:
        """Return current analog readings from all configured ADC channels."""
        if analog_backend is None:
            return JSONResponse(
                {"error": "Analog input is not configured or unavailable."},
                status_code=503,
            )
        readings = {}
        label_map = settings.analog_label_map
        for ch in settings.analog_channels or []:
            try:
                raw = analog_backend.read_raw(ch)
                voltage = analog_backend.read_voltage(ch, v_ref=settings.analog_v_ref)
                from .models import AnalogReading
                reading = AnalogReading(
                    channel=ch, raw=raw, voltage=round(voltage, 4),
                    label=label_map.get(ch),
                )
                readings[ch] = reading.model_dump(mode="json")
                engine.update_analog(reading)
            except GPIOBackendError as exc:
                readings[ch] = {"channel": ch, "error": str(exc)}
        return JSONResponse(readings)

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
