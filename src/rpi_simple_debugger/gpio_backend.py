from __future__ import annotations

from typing import Literal, Protocol


class GPIOBackend(Protocol):
    """Abstraction over board-specific GPIO access.

    This keeps the rest of the codebase independent from any particular
    Raspberry Pi library and lets advanced users plug in their own backend.
    """

    def setup_input(
        self,
        pin: int,
        pull: Literal["up", "down", "none"] = "none",
    ) -> None: ...

    def read(self, pin: int) -> int: ...

    def cleanup(self) -> None: ...


class MockGPIOBackend:
    """Simple backend used on non-RPi machines and for tests.

    Always returns 0 for reads. This is enough to let the library run
    without requiring GPIO support.
    """

    def setup_input(
        self,
        pin: int,
        pull: Literal["up", "down", "none"] = "none",
    ) -> None:
        return

    def read(self, pin: int) -> int:
        return 0

    def cleanup(self) -> None:
        return


class RPiGPIOBackend:
    """Backend that uses RPi.GPIO when available.

    If the RPi.GPIO module cannot be imported, this backend will behave like
    the mock backend. This keeps initialization simple for beginners.
    """

    def __init__(self) -> None:
        try:  # pragma: no cover - not available on most dev machines
            import RPi.GPIO as GPIO  # type: ignore[import]

            self._gpio = GPIO
            self._gpio.setmode(self._gpio.BCM)
        except Exception:  # pragma: no cover - graceful degrade
            self._gpio = None

    def setup_input(
        self,
        pin: int,
        pull: Literal["up", "down", "none"] = "none",
    ) -> None:
        if self._gpio is None:
            return
        pull_up_down = self._gpio.PUD_OFF
        if pull == "up":
            pull_up_down = self._gpio.PUD_UP
        elif pull == "down":
            pull_up_down = self._gpio.PUD_DOWN
        self._gpio.setup(pin, self._gpio.IN, pull_up_down=pull_up_down)

    def read(self, pin: int) -> int:
        if self._gpio is None:
            return 0
        return int(self._gpio.input(pin))

    def cleanup(self) -> None:
        if self._gpio is None:
            return
        self._gpio.cleanup()
