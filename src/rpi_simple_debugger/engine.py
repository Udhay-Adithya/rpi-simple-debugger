from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from .config import DebuggerSettings
from .models import (
    AppInfo,
    BluetoothStatus,
    BoardInfo,
    CustomEntry,
    DebuggerMessage,
    DebuggerSnapshot,
    GPIOState,
    SystemHealth,
    WiFiStatus,
)


class ConnectionManager:
    def __init__(self) -> None:
        self._active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._active:
            self._active.remove(websocket)

    async def broadcast(self, message: DebuggerMessage) -> None:
        to_remove: List[WebSocket] = []
        payload = message.model_dump(mode="json")
        for ws in self._active:
            try:
                await ws.send_json(payload)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            self.disconnect(ws)


class DebuggerEngine:
    """Core state and broadcast manager for the debugger.

    Monitors call the public update methods, which keep the snapshot in sync and
    broadcast websocket messages.
    """

    def __init__(self, settings: DebuggerSettings, version: str) -> None:
        self.settings = settings
        self.manager = ConnectionManager()
        self._loop = asyncio.get_event_loop()

        app_info = AppInfo(
            debugger_version=version,
            python_version=sys.version.split()[0],
        )

        self._snapshot = DebuggerSnapshot(
            app=app_info,
            board=self._detect_board(),
        )

    # ----- Snapshot access -----

    @property
    def snapshot(self) -> DebuggerSnapshot:
        return self._snapshot

    # ----- Update methods used by monitors -----

    def update_gpio(self, state: GPIOState) -> None:
        self._snapshot.gpio[state.pin] = state
        self._schedule_broadcast(
            DebuggerMessage(type="gpio", data=state.model_dump(mode="json"))
        )

    def update_wifi(self, status: WiFiStatus) -> None:
        self._snapshot.wifi = status
        self._schedule_broadcast(
            DebuggerMessage(type="wifi", data=status.model_dump(mode="json"))
        )

    def update_bluetooth(self, status: BluetoothStatus) -> None:
        self._snapshot.bluetooth = status
        self._schedule_broadcast(
            DebuggerMessage(type="bluetooth", data=status.model_dump(mode="json"))
        )

    def update_system(self, health: SystemHealth) -> None:
        self._snapshot.system = health
        self._schedule_broadcast(
            DebuggerMessage(type="system", data=health.model_dump(mode="json"))
        )

    def push_custom(self, name: str, payload: Dict[str, Any]) -> None:
        entry = CustomEntry(name=name, payload=payload)
        self._snapshot.custom[name] = entry
        self._schedule_broadcast(
            DebuggerMessage(type="custom", data=entry.model_dump(mode="json"))
        )

    async def send_meta(self) -> None:
        """Broadcast current meta information (board + app + time)."""

        meta: Dict[str, Any] = {
            "board": (
                self._snapshot.board.model_dump(mode="json")
                if self._snapshot.board
                else None
            ),
            "app": self._snapshot.app.model_dump(mode="json"),
            "timestamp": datetime.utcnow().isoformat(),
            "enabled": {
                "gpio": self.settings.gpio_enabled,
                "wifi": self.settings.wifi_enabled,
                "bluetooth": self.settings.bluetooth_enabled,
                "system_health": self.settings.system_health_enabled,
            },
        }
        await self.manager.broadcast(DebuggerMessage(type="meta", data=meta))

    # ----- Internal helpers -----

    def _schedule_broadcast(self, message: DebuggerMessage) -> None:
        asyncio.run_coroutine_threadsafe(self.manager.broadcast(message), self._loop)

    def _detect_board(self) -> Optional[BoardInfo]:
        # Keep this intentionally lightweight and best-effort.
        try:
            import platform

            return BoardInfo(
                name=platform.machine(),
                cpu_arch=platform.processor() or None,
                os=f"{platform.system()} {platform.release()}",
            )
        except Exception:
            return None
