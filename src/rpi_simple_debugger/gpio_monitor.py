from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

try:  # Optional on non-RPi platforms
    import RPi.GPIO as GPIO  # type: ignore[import]
except Exception:  # pragma: no cover - not available on dev machines
    GPIO = None  # type: ignore[assignment]


@dataclass
class GPIOState:
    pin: int
    value: int
    label: Optional[str]


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
    ) -> None:
        self._pins = pins
        self._label_map = label_map
        self._interval_s = interval_s
        self._on_change = on_change
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._last_values: Dict[int, int] = {}

    def start(self) -> None:
        if GPIO is None:
            # Library can still run; GPIO data will just be absent.
            return

        if self._thread and self._thread.is_alive():
            return

        GPIO.setmode(GPIO.BCM)
        for pin in self._pins:
            GPIO.setup(pin, GPIO.IN)

        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        if GPIO is not None:
            GPIO.cleanup()

    def _loop(self) -> None:
        while not self._stop.is_set():
            for pin in self._pins:
                value = GPIO.input(pin) if GPIO is not None else 0
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
