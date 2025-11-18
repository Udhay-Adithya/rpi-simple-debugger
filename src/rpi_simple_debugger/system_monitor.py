from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

import os
import time

import psutil

from .models import ProcessInfo, SystemHealth


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
            for _name, entries in temps.items():
                if entries:
                    cpu_temp = entries[0].current
                    break
        except Exception:
            cpu_temp = None

        cpu_percent = psutil.cpu_percent(interval=None)
        disk = psutil.disk_usage("/")

        mem = psutil.virtual_memory()
        memory_percent = float(mem.percent)

        swap_percent = None
        try:
            swap = psutil.swap_memory()
            swap_percent = float(swap.percent)
        except Exception:
            swap_percent = None

        load_1 = load_5 = load_15 = None
        try:
            load_1, load_5, load_15 = os.getloadavg()
        except (OSError, AttributeError):
            pass

        uptime_s = None
        boot_time = None
        try:
            boot_time = float(psutil.boot_time())
            uptime_s = float(time.time() - boot_time)
        except Exception:
            pass

        process_count = None
        top_processes: list[ProcessInfo] | None = None
        try:
            procs = []
            for p in psutil.process_iter(attrs=["pid", "name", "cpu_percent"]):
                info = p.info
                procs.append(
                    ProcessInfo(
                        pid=info.get("pid"),
                        name=info.get("name"),
                        cpu_percent=info.get("cpu_percent"),
                    )
                )
            process_count = len(procs)
            procs.sort(key=lambda x: (x.cpu_percent or 0.0), reverse=True)
            top_processes = procs[:3]
        except Exception:
            process_count = None
            top_processes = None

        return SystemHealth(
            cpu_temp_c=cpu_temp,
            cpu_percent=float(cpu_percent),
            disk_used_percent=float(disk.percent),
            memory_percent=memory_percent,
            swap_percent=swap_percent,
            load_1=load_1,
            load_5=load_5,
            load_15=load_15,
            uptime_s=uptime_s,
            boot_time=boot_time,
            process_count=process_count,
        )
