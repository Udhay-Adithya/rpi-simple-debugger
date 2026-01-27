"""Tests for the GPIO backend module."""

from rpi_simple_debugger.gpio_backend import (
    MockGPIOBackend,
    RPiGPIOBackend,
    GPIOZeroBackend,
)


def test_mock_backend_read() -> None:
    """MockGPIOBackend should always return 0."""
    backend = MockGPIOBackend()

    # Setup should not raise
    backend.setup_input(17)
    backend.setup_input(18, pull="up")
    backend.setup_input(19, pull="down")

    # Read should always return 0
    assert backend.read(17) == 0
    assert backend.read(18) == 0
    assert backend.read(99) == 0

    # Cleanup should not raise
    backend.cleanup()


def test_rpi_backend_graceful_fallback() -> None:
    """RPiGPIOBackend should work when RPi.GPIO is available or gracefully fall back."""
    backend = RPiGPIOBackend()

    # Operations should not raise regardless of GPIO availability
    backend.setup_input(17)
    backend.setup_input(18, pull="up")

    # Should return a valid value (0 or 1)
    result = backend.read(17)
    assert result in (0, 1)

    # Cleanup should not raise
    backend.cleanup()


def test_gpiozero_backend_graceful_fallback() -> None:
    """GPIOZeroBackend should gracefully handle missing gpiozero."""
    backend = GPIOZeroBackend()

    # On non-Raspberry Pi machines or without gpiozero installed,
    # _available will be False and operations should not raise
    backend.setup_input(17)
    backend.setup_input(18, pull="up")
    backend.setup_input(19, pull="down")

    # Should return 0 when gpiozero not available
    result = backend.read(17)
    assert result == 0

    # Cleanup should not raise
    backend.cleanup()


def test_mock_backend_pull_configurations() -> None:
    """MockGPIOBackend should accept all pull configurations."""
    backend = MockGPIOBackend()

    # All pull configurations should be accepted
    backend.setup_input(17, pull="none")
    backend.setup_input(18, pull="up")
    backend.setup_input(19, pull="down")

    # Should not raise any errors
    backend.cleanup()
