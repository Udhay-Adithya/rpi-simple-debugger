from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional

from .gpio_backend import GPIOBackend, GPIOZeroBackend, MockGPIOBackend, RPiGPIOBackend
from .models import GPIOState


class GPIOMonitor:
    """Polls GPIO pins and reports changes via a callback.

    This uses simple polling instead of interrupts so it behaves
    consistently across boards and is easier to explain to beginners.
    """

    def __init__(
        self,
        pins: List[int],
        label_map: Dict[int, str],
        interval_s: float,
        on_change: Callable[[GPIOState], None],
        backend: str = "auto",
    ) -> None:
        self._pins = pins
        self._label_map = label_map
        self._interval_s = interval_s
        self._on_change = on_change
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._last_values: Dict[int, int] = {}
        self._backend = self._create_backend(backend)

    def _create_backend(self, backend_name: str) -> GPIOBackend:
        """Create the appropriate GPIO backend based on configuration."""
        if backend_name == "mock":
            return MockGPIOBackend()

        if backend_name == "rpi":
            candidate = RPiGPIOBackend()
            if candidate._gpio is not None:
                return candidate
            # Fall back to mock if RPi.GPIO not available
            return MockGPIOBackend()

        if backend_name == "gpiozero":
            candidate = GPIOZeroBackend()
            if candidate._available:
                return candidate
            # Fall back to mock if gpiozero not available
            return MockGPIOBackend()

        # Auto mode: try RPi.GPIO first, then gpiozero, then mock
        rpi_candidate = RPiGPIOBackend()
        if rpi_candidate._gpio is not None:
            return rpi_candidate

        gpiozero_candidate = GPIOZeroBackend()
        if gpiozero_candidate._available:
            return gpiozero_candidate

        return MockGPIOBackend()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        for pin in self._pins:
            self._backend.setup_input(pin)

        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._backend.cleanup()

    def _loop(self) -> None:
        while not self._stop.is_set():
            for pin in self._pins:
                value = self._backend.read(pin)
                last = self._last_values.get(pin)
                if last is None or last != value:
                    self._last_values[pin] = value
                    self._on_change(
                        GPIOState(
                            pin=pin,
                            value=int(value),
                            label=self._label_map.get(pin),
                        )
                    )
            time.sleep(self._interval_s)
