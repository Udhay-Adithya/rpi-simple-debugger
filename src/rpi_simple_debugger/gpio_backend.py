from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Protocol

logger = logging.getLogger(__name__)


class GPIOBackendError(Exception):
    """Raised when a GPIO backend cannot be initialised."""


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
    """Simple backend used for tests only.

    Always returns 0 for reads. This backend is explicitly selected via
    configuration and is not used as an automatic fallback.
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
    """Backend that uses RPi.GPIO.

    Raises ``GPIOBackendError`` if the RPi.GPIO module cannot be imported
    or initialised, so the caller receives a clear signal instead of
    silently falling back to mock data.
    """

    def __init__(self) -> None:
        try:
            import RPi.GPIO as GPIO  # type: ignore[import]

            self._gpio = GPIO
            self._gpio.setmode(self._gpio.BCM)
        except Exception as exc:
            raise GPIOBackendError(
                "RPi.GPIO is not available. Install it with "
                "'pip install RPi.GPIO' or choose a different backend."
            ) from exc

    def setup_input(
        self,
        pin: int,
        pull: Literal["up", "down", "none"] = "none",
    ) -> None:
        pull_up_down = self._gpio.PUD_OFF
        if pull == "up":
            pull_up_down = self._gpio.PUD_UP
        elif pull == "down":
            pull_up_down = self._gpio.PUD_DOWN
        self._gpio.setup(pin, self._gpio.IN, pull_up_down=pull_up_down)

    def read(self, pin: int) -> int:
        return int(self._gpio.input(pin))

    def cleanup(self) -> None:
        self._gpio.cleanup()


class GPIOZeroBackend:
    """Backend that uses gpiozero.

    gpiozero is a beginner-friendly GPIO library that provides a simpler API
    than RPi.GPIO. It also works with remote GPIO pins and on other platforms.

    Raises ``GPIOBackendError`` if gpiozero cannot be imported.
    """

    def __init__(self) -> None:
        self._pins: Dict[int, Any] = {}  # pin number -> InputDevice

        try:
            import gpiozero  # type: ignore[import]

            self._gpiozero = gpiozero
        except Exception as exc:
            raise GPIOBackendError(
                "gpiozero is not available. Install it with "
                "'pip install gpiozero' or choose a different backend."
            ) from exc

    def setup_input(
        self,
        pin: int,
        pull: Literal["up", "down", "none"] = "none",
    ) -> None:
        # Map pull configuration to gpiozero's pull_up parameter
        pull_up = None  # floating
        if pull == "up":
            pull_up = True
        elif pull == "down":
            pull_up = False

        # Close existing pin if reconfiguring
        if pin in self._pins:
            self._pins[pin].close()

        self._pins[pin] = self._gpiozero.InputDevice(pin, pull_up=pull_up)

    def read(self, pin: int) -> int:
        if pin not in self._pins:
            raise GPIOBackendError(
                f"Pin {pin} has not been set up. Call setup_input() first."
            )
        return 1 if self._pins[pin].value else 0

    def cleanup(self) -> None:
        for device in self._pins.values():
            try:
                device.close()
            except Exception:  # pragma: no cover
                pass
        self._pins.clear()


class LibgpiodBackend:
    """Backend using the Linux kernel GPIO character device via libgpiod.

    This backend works on **any** Linux SBC with GPIO — Raspberry Pi, NVIDIA
    Jetson, BeagleBone, Orange Pi, RISC-V boards, custom ARM boards — because
    the kernel's GPIO subsystem abstracts the hardware.

    Requires the ``gpiod`` Python package (``pip install gpiod``).

    Raises ``GPIOBackendError`` if the ``gpiod`` module or the GPIO chip
    cannot be opened.
    """

    def __init__(self, chip_path: str = "/dev/gpiochip0") -> None:
        self._chip_path = chip_path
        self._lines: Dict[int, Any] = {}  # offset -> gpiod.Line
        self._chip: Any = None

        try:
            import gpiod  # type: ignore[import]

            self._gpiod = gpiod
            self._chip = gpiod.Chip(chip_path)
        except ImportError as exc:
            raise GPIOBackendError(
                "gpiod Python package is not available. Install it with "
                "'pip install gpiod'."
            ) from exc
        except Exception as exc:
            raise GPIOBackendError(
                f"Cannot open GPIO chip at '{chip_path}'. Ensure the device "
                "exists and you have read permissions (try running with sudo "
                "or adding your user to the 'gpio' group)."
            ) from exc

    def setup_input(
        self,
        pin: int,
        pull: Literal["up", "down", "none"] = "none",
    ) -> None:
        # Release existing line if reconfiguring
        if pin in self._lines:
            self._lines[pin].release()

        line = self._chip.get_line(pin)

        # libgpiod v1 API: bias flags depend on library version
        flags = 0
        try:
            if pull == "up":
                flags = self._gpiod.LINE_REQ_FLAG_BIAS_PULL_UP
            elif pull == "down":
                flags = self._gpiod.LINE_REQ_FLAG_BIAS_PULL_DOWN
        except AttributeError:
            # Older libgpiod without bias support — ignore pull config
            pass

        line.request(consumer="rpi-debugger", type=self._gpiod.LINE_REQ_DIR_IN, flags=flags)
        self._lines[pin] = line

    def read(self, pin: int) -> int:
        if pin not in self._lines:
            raise GPIOBackendError(
                f"Pin (line offset) {pin} has not been set up. "
                "Call setup_input() first."
            )
        return self._lines[pin].get_value()

    def cleanup(self) -> None:
        for line in self._lines.values():
            try:
                line.release()
            except Exception:
                pass
        self._lines.clear()
        if self._chip is not None:
            try:
                self._chip.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# GPIO Output Controller
# ---------------------------------------------------------------------------


class GPIOOutputBackend(Protocol):
    """Protocol for GPIO output control."""

    def setup_output(self, pin: int, initial: int = 0) -> None: ...

    def write(self, pin: int, value: int) -> None: ...

    def cleanup(self) -> None: ...


class RPiGPIOOutputBackend:
    """GPIO output using RPi.GPIO."""

    def __init__(self) -> None:
        try:
            import RPi.GPIO as GPIO  # type: ignore[import]

            self._gpio = GPIO
            # setmode may already be called; ignore if so
            try:
                self._gpio.setmode(self._gpio.BCM)
            except Exception:
                pass
        except Exception as exc:
            raise GPIOBackendError(
                "RPi.GPIO is not available for output control."
            ) from exc

    def setup_output(self, pin: int, initial: int = 0) -> None:
        self._gpio.setup(pin, self._gpio.OUT, initial=initial)

    def write(self, pin: int, value: int) -> None:
        self._gpio.output(pin, value)

    def cleanup(self) -> None:
        self._gpio.cleanup()


class LibgpiodOutputBackend:
    """GPIO output using libgpiod — works on any Linux SBC."""

    def __init__(self, chip_path: str = "/dev/gpiochip0") -> None:
        self._lines: Dict[int, Any] = {}

        try:
            import gpiod  # type: ignore[import]

            self._gpiod = gpiod
            self._chip = gpiod.Chip(chip_path)
        except ImportError as exc:
            raise GPIOBackendError(
                "gpiod Python package is not available for output control."
            ) from exc
        except Exception as exc:
            raise GPIOBackendError(
                f"Cannot open GPIO chip at '{chip_path}' for output."
            ) from exc

    def setup_output(self, pin: int, initial: int = 0) -> None:
        if pin in self._lines:
            self._lines[pin].release()

        line = self._chip.get_line(pin)
        line.request(
            consumer="rpi-debugger-out",
            type=self._gpiod.LINE_REQ_DIR_OUT,
            default_vals=[initial],
        )
        self._lines[pin] = line

    def write(self, pin: int, value: int) -> None:
        if pin not in self._lines:
            raise GPIOBackendError(
                f"Output pin {pin} has not been set up. "
                "Call setup_output() first."
            )
        self._lines[pin].set_value(value)

    def cleanup(self) -> None:
        for line in self._lines.values():
            try:
                line.release()
            except Exception:
                pass
        self._lines.clear()
        if self._chip is not None:
            try:
                self._chip.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Analog Input (ADC) Backend
# ---------------------------------------------------------------------------


class AnalogBackend(Protocol):
    """Protocol for reading analog values from ADC chips."""

    def setup_channel(self, channel: int) -> None: ...

    def read_raw(self, channel: int) -> int:
        """Return the raw ADC count (e.g. 0-1023 for 10-bit)."""
        ...

    def read_voltage(self, channel: int, v_ref: float = 3.3) -> float:
        """Return the voltage on the channel."""
        ...

    @property
    def resolution_bits(self) -> int: ...

    def cleanup(self) -> None: ...


class MCP3008Backend:
    """Analog input via the MCP3008 10-bit SPI ADC.

    The MCP3008 is a common, inexpensive 8-channel 10-bit ADC that
    communicates over SPI. It is used in many Raspberry Pi tutorials.

    Requires the ``spidev`` package (``pip install spidev``).
    """

    def __init__(self, bus: int = 0, device: int = 0) -> None:
        self._channels: Dict[int, bool] = {}

        try:
            import spidev  # type: ignore[import]

            self._spi = spidev.SpiDev()
            self._spi.open(bus, device)
            self._spi.max_speed_hz = 1_000_000
        except ImportError as exc:
            raise GPIOBackendError(
                "spidev is not available. Install it with 'pip install spidev'."
            ) from exc
        except Exception as exc:
            raise GPIOBackendError(
                f"Cannot open SPI bus {bus}, device {device} for MCP3008."
            ) from exc

    @property
    def resolution_bits(self) -> int:
        return 10

    def setup_channel(self, channel: int) -> None:
        if not 0 <= channel <= 7:
            raise GPIOBackendError(
                f"MCP3008 channel must be 0-7, got {channel}."
            )
        self._channels[channel] = True

    def read_raw(self, channel: int) -> int:
        if channel not in self._channels:
            raise GPIOBackendError(
                f"ADC channel {channel} has not been set up. "
                "Call setup_channel() first."
            )
        # MCP3008 SPI protocol: start bit, single-ended, channel bits
        cmd = [1, (8 + channel) << 4, 0]
        result = self._spi.xfer2(cmd)
        return ((result[1] & 0x03) << 8) | result[2]

    def read_voltage(self, channel: int, v_ref: float = 3.3) -> float:
        raw = self.read_raw(channel)
        return (raw / 1023.0) * v_ref

    def cleanup(self) -> None:
        try:
            self._spi.close()
        except Exception:
            pass
        self._channels.clear()


class ADS1115Backend:
    """Analog input via the ADS1115 16-bit I²C ADC.

    The ADS1115 is a high-resolution 4-channel 16-bit ADC that communicates
    over I²C. It provides programmable gain and is commonly used for
    precision measurements.

    Requires the ``smbus2`` package (``pip install smbus2``).
    """

    # ADS1115 register addresses
    _REG_CONVERSION = 0x00
    _REG_CONFIG = 0x01

    # Default config: single-shot, ±4.096V, 128SPS
    _GAIN_MAP = {
        2 / 3: 0x0000,  # ±6.144V
        1: 0x0200,      # ±4.096V
        2: 0x0400,      # ±2.048V
        4: 0x0600,      # ±1.024V
        8: 0x0800,      # ±0.512V
        16: 0x0A00,     # ±0.256V
    }

    _CHANNEL_MAP = {
        0: 0x4000,  # AIN0
        1: 0x5000,  # AIN1
        2: 0x6000,  # AIN2
        3: 0x7000,  # AIN3
    }

    def __init__(
        self,
        bus: int = 1,
        address: int = 0x48,
        gain: float = 1,
    ) -> None:
        self._address = address
        self._gain = gain
        self._channels: Dict[int, bool] = {}

        if gain not in self._GAIN_MAP:
            raise GPIOBackendError(
                f"ADS1115 gain must be one of {list(self._GAIN_MAP.keys())}, "
                f"got {gain}."
            )

        try:
            import smbus2  # type: ignore[import]

            self._bus = smbus2.SMBus(bus)
        except ImportError as exc:
            raise GPIOBackendError(
                "smbus2 is not available. Install it with 'pip install smbus2'."
            ) from exc
        except Exception as exc:
            raise GPIOBackendError(
                f"Cannot open I²C bus {bus} for ADS1115 at address "
                f"0x{address:02X}."
            ) from exc

    @property
    def resolution_bits(self) -> int:
        return 16

    def setup_channel(self, channel: int) -> None:
        if channel not in self._CHANNEL_MAP:
            raise GPIOBackendError(
                f"ADS1115 channel must be 0-3, got {channel}."
            )
        self._channels[channel] = True

    def read_raw(self, channel: int) -> int:
        if channel not in self._channels:
            raise GPIOBackendError(
                f"ADC channel {channel} has not been set up. "
                "Call setup_channel() first."
            )
        import time

        config = (
            0x8000                          # Start single conversion
            | self._CHANNEL_MAP[channel]    # Channel select
            | self._GAIN_MAP[self._gain]    # PGA gain
            | 0x0100                        # Single-shot mode
            | 0x0080                        # 128 SPS
        )

        # Write config
        self._bus.write_i2c_block_data(
            self._address,
            self._REG_CONFIG,
            [(config >> 8) & 0xFF, config & 0xFF],
        )

        # Wait for conversion (128 SPS → ~8ms)
        time.sleep(0.01)

        # Read result
        data = self._bus.read_i2c_block_data(
            self._address, self._REG_CONVERSION, 2
        )
        raw = (data[0] << 8) | data[1]

        # Handle two's complement for signed 16-bit
        if raw >= 0x8000:
            raw -= 0x10000

        return raw

    def read_voltage(self, channel: int, v_ref: float = 3.3) -> float:
        # For ADS1115, v_ref is determined by gain setting, not external ref
        gain_voltage = {
            2 / 3: 6.144,
            1: 4.096,
            2: 2.048,
            4: 1.024,
            8: 0.512,
            16: 0.256,
        }
        full_scale = gain_voltage.get(self._gain, 4.096)
        raw = self.read_raw(channel)
        return (raw / 32767.0) * full_scale

    def cleanup(self) -> None:
        try:
            self._bus.close()
        except Exception:
            pass
        self._channels.clear()
