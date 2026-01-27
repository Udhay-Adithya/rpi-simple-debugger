from __future__ import annotations

import subprocess
import threading
import time
from typing import Callable, List, Optional

import psutil

from .models import NetInterfaceStats, WiFiStatus, BluetoothStatus


class NetworkMonitor:
    def __init__(
        self,
        interval_s: float,
        on_wifi: Callable[[WiFiStatus], None],
        on_bt: Callable[[BluetoothStatus], None],
        on_interfaces: Callable[[List[NetInterfaceStats]], None] | None = None,
    ) -> None:
        self._interval_s = interval_s
        self._on_wifi = on_wifi
        self._on_bt = on_bt
        self._on_interfaces = on_interfaces
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
            self._on_wifi(self._get_wifi_status())
            self._on_bt(self._get_bt_status())
            if self._on_interfaces is not None:
                self._on_interfaces(self._get_interface_stats())
            time.sleep(self._interval_s)

    def _run_command(self, *args: str) -> str:
        try:
            out = subprocess.check_output(args, stderr=subprocess.DEVNULL)
            return out.decode().strip()
        except Exception:
            return ""

    def _get_wifi_status(self) -> WiFiStatus:
        # Uses common Raspberry Pi tools if available; falls back gracefully.
        iw = self._run_command("iwconfig")
        ssid: Optional[str] = None
        signal: Optional[int] = None
        if "ESSID" in iw:
            for line in iw.splitlines():
                if "ESSID" in line:
                    # ESSID:"network"
                    if "ESSID:" in line:
                        ssid_part = line.split("ESSID:")[-1].strip()
                        ssid = ssid_part.strip('"') if ssid_part else None
                if "Signal level" in line:
                    # Signal level=-60 dBm
                    for chunk in line.split():
                        if chunk.startswith("level="):
                            try:
                                signal = int(chunk.split("=")[-1])
                            except ValueError:
                                pass

        ip_addr = None
        ip_output = self._run_command("hostname", "-I")
        if ip_output:
            ip_addr = ip_output.split()[0]

        connected = ssid is not None and ssid != "off/any"
        return WiFiStatus(
            connected=connected,
            ssid=ssid,
            ip_address=ip_addr,
            signal_level_dbm=signal,
        )

    def _get_bt_status(self) -> BluetoothStatus:
        # Basic check via bluetoothctl if available.
        out = self._run_command("bluetoothctl", "show")
        powered = "Powered: yes" in out

        con_out = self._run_command("bluetoothctl", "info")
        connected = "Connected: yes" in con_out

        return BluetoothStatus(powered=powered, connected=connected)

    def _get_interface_stats(self) -> List[NetInterfaceStats]:
        """Collect per-interface network statistics using psutil."""
        result: List[NetInterfaceStats] = []
        try:
            io_counters = psutil.net_io_counters(pernic=True)
            if_stats = psutil.net_if_stats()

            for name, counters in io_counters.items():
                is_up = False
                if name in if_stats:
                    is_up = if_stats[name].isup

                result.append(
                    NetInterfaceStats(
                        name=name,
                        is_up=is_up,
                        rx_bytes=counters.bytes_recv,
                        tx_bytes=counters.bytes_sent,
                        rx_errs=counters.errin,
                        tx_errs=counters.errout,
                    )
                )
        except Exception:
            pass

        return result
