from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import psutil


@dataclass
class SystemHealth:
    cpu_temp_c: Optional[float]
    cpu_percent: float
    disk_used_percent: float


class SystemMonitor:
    def __init__(
        self,
        interval_s: float,
        on_update: Callable[[SystemHealth], None],
    ) -> None:
        self._interval_s = interval_s
        self._on_update = on_update
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._on_update(self._get_health())
            time.sleep(self._interval_s)

    def _get_health(self) -> SystemHealth:
        cpu_temp = None
        try:
            temps = psutil.sensors_temperatures()
            # On Raspberry Pi this is often "cpu-thermal" or similar.
            for name, entries in temps.items():
                if entries:
                    cpu_temp = entries[0].current
                    break
        except Exception:
            cpu_temp = None

        cpu_percent = psutil.cpu_percent(interval=None)
        disk = psutil.disk_usage("/")

        return SystemHealth(
            cpu_temp_c=cpu_temp,
            cpu_percent=float(cpu_percent),
            disk_used_percent=float(disk.percent),
        )
