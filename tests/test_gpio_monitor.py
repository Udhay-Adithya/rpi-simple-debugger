"""Tests for the GPIO monitor module."""

from rpi_simple_debugger.gpio_monitor import GPIOMonitor
from rpi_simple_debugger.models import GPIOState


def test_gpio_monitor_initialization() -> None:
    """GPIOMonitor should initialize with mock backend on non-Pi machines."""
    collected = []

    def on_change(state: GPIOState) -> None:
        collected.append(state)

    monitor = GPIOMonitor(
        pins=[17, 27],
        label_map={17: "LED", 27: "Button"},
        interval_s=0.1,
        on_change=on_change,
    )

    # Should have created a backend
    assert monitor._backend is not None


def test_gpio_monitor_explicit_mock_backend() -> None:
    """GPIOMonitor should use mock backend when specified."""
    monitor = GPIOMonitor(
        pins=[17],
        label_map={},
        interval_s=0.1,
        on_change=lambda s: None,
        backend="mock",
    )

    from rpi_simple_debugger.gpio_backend import MockGPIOBackend
    assert isinstance(monitor._backend, MockGPIOBackend)


def test_gpio_monitor_start_stop() -> None:
    """GPIOMonitor should start and stop without errors."""
    collected = []

    def on_change(state: GPIOState) -> None:
        collected.append(state)

    monitor = GPIOMonitor(
        pins=[17, 27],
        label_map={17: "LED"},
        interval_s=0.05,
        on_change=on_change,
        backend="mock",
    )

    # Start monitoring
    monitor.start()

    # Wait for initial state collection
    import time
    time.sleep(0.15)

    # Stop monitoring
    monitor.stop()

    # Should have reported initial state for each pin
    # (mock backend always returns 0, so initial state should be reported)
    assert len(collected) >= 2  # At least one for each pin


def test_gpio_monitor_double_start() -> None:
    """Starting monitor twice should not create multiple threads."""
    monitor = GPIOMonitor(
        pins=[17],
        label_map={},
        interval_s=0.1,
        on_change=lambda s: None,
        backend="mock",
    )

    monitor.start()
    thread1 = monitor._thread

    monitor.start()  # Second start
    thread2 = monitor._thread

    # Should be the same thread
    assert thread1 is thread2

    monitor.stop()


def test_gpio_monitor_labels_in_state() -> None:
    """GPIOMonitor should include labels in reported state."""
    collected = []

    def on_change(state: GPIOState) -> None:
        collected.append(state)

    monitor = GPIOMonitor(
        pins=[17, 27],
        label_map={17: "LED", 27: "Button"},
        interval_s=0.05,
        on_change=on_change,
        backend="mock",
    )

    monitor.start()
    import time
    time.sleep(0.1)
    monitor.stop()

    # Find the state for pin 17
    pin17_states = [s for s in collected if s.pin == 17]
    assert len(pin17_states) > 0
    assert pin17_states[0].label == "LED"


def test_gpio_monitor_auto_backend_fallback() -> None:
    """Auto backend should select an appropriate backend."""
    monitor = GPIOMonitor(
        pins=[17],
        label_map={},
        interval_s=0.1,
        on_change=lambda s: None,
        backend="auto",
    )

    # Should have created a valid backend
    assert monitor._backend is not None

    # Setup the pin before reading (as the monitor does in start())
    monitor._backend.setup_input(17)

    # Read should work without errors and return a valid value
    result = monitor._backend.read(17)
    assert result in (0, 1)

    # Cleanup
    monitor._backend.cleanup()


def test_gpio_monitor_rpi_backend_fallback() -> None:
    """RPi backend should fall back to mock when RPi.GPIO unavailable."""
    monitor = GPIOMonitor(
        pins=[17],
        label_map={},
        interval_s=0.1,
        on_change=lambda s: None,
        backend="rpi",
    )

    # On non-Pi machines, should fall back to mock
    assert monitor._backend is not None


def test_gpio_monitor_gpiozero_backend_fallback() -> None:
    """gpiozero backend should fall back to mock when gpiozero unavailable."""
    monitor = GPIOMonitor(
        pins=[17],
        label_map={},
        interval_s=0.1,
        on_change=lambda s: None,
        backend="gpiozero",
    )

    # On machines without gpiozero, should fall back to mock
    assert monitor._backend is not None
