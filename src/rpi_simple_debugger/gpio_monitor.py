from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional

from .gpio_backend import (
    GPIOBackend,
    GPIOBackendError,
    GPIOZeroBackend,
    LibgpiodBackend,
    MockGPIOBackend,
    RPiGPIOBackend,
)
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
        """Create the appropriate GPIO backend based on configuration.

        Raises ``GPIOBackendError`` when the requested (or auto-detected)
        backend cannot be initialised, instead of silently falling back to
        mock data.
        """
        if backend_name == "mock":
            return MockGPIOBackend()

        if backend_name == "rpi":
            return RPiGPIOBackend()

        if backend_name == "gpiozero":
            return GPIOZeroBackend()

        if backend_name == "libgpiod":
            return LibgpiodBackend()

        # Auto mode: try RPi.GPIO → gpiozero → libgpiod
        errors: list[str] = []

        try:
            return RPiGPIOBackend()
        except GPIOBackendError as exc:
            errors.append(f"RPi.GPIO: {exc}")

        try:
            return GPIOZeroBackend()
        except GPIOBackendError as exc:
            errors.append(f"gpiozero: {exc}")

        try:
            return LibgpiodBackend()
        except GPIOBackendError as exc:
            errors.append(f"libgpiod: {exc}")

        raise GPIOBackendError(
            "No GPIO backend could be initialised. Tried:\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n\nSet gpio_enabled=false in configuration if GPIO "
            "monitoring is not needed, or install a supported GPIO library."
        )

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
