"""Tests for the configuration module."""

import json
import tempfile
from pathlib import Path

from rpi_simple_debugger.config import DebuggerSettings, GPIOLabel, load_settings


def test_default_settings() -> None:
    """Default settings should have sensible defaults."""
    settings = DebuggerSettings()

    assert settings.gpio_enabled is True
    assert settings.wifi_enabled is True
    assert settings.bluetooth_enabled is True
    assert settings.system_health_enabled is True
    assert settings.gpio_poll_interval_s == 0.1
    assert settings.network_poll_interval_s == 2.0
    assert settings.system_poll_interval_s == 2.0


def test_gpio_label_map() -> None:
    """gpio_label_map property should return dict of pin to label."""
    settings = DebuggerSettings(
        gpio_labels=[
            GPIOLabel(pin=17, label="LED"),
            GPIOLabel(pin=27, label="Button"),
        ]
    )

    label_map = settings.gpio_label_map
    assert label_map[17] == "LED"
    assert label_map[27] == "Button"


def test_effective_gpio_pins_default() -> None:
    """effective_gpio_pins should return default pins when gpio_pins is None."""
    settings = DebuggerSettings()

    pins = settings.effective_gpio_pins
    assert pins == [2, 3, 4, 17, 18, 22, 23, 24, 25, 27]


def test_effective_gpio_pins_custom() -> None:
    """effective_gpio_pins should return custom pins when configured."""
    settings = DebuggerSettings(gpio_pins=[4, 5, 6])

    pins = settings.effective_gpio_pins
    assert pins == [4, 5, 6]


def test_health_thresholds() -> None:
    """Health thresholds should have sensible defaults."""
    settings = DebuggerSettings()

    assert settings.cpu_temp_threshold_c == 80.0
    assert settings.disk_usage_threshold_percent == 90.0
    assert settings.memory_usage_threshold_percent == 90.0
    assert settings.wifi_signal_threshold_dbm == -75


def test_cors_settings() -> None:
    """CORS settings should be enabled by default."""
    settings = DebuggerSettings()

    assert settings.cors_enabled is True
    assert settings.cors_origins == ["*"]


def test_load_settings_file_not_found() -> None:
    """load_settings should return defaults when file doesn't exist."""
    settings = load_settings(Path("/nonexistent/path/settings.json"))

    assert settings.gpio_enabled is True


def test_load_settings_from_file() -> None:
    """load_settings should load settings from JSON file."""
    config = {
        "gpio_enabled": False,
        "wifi_enabled": False,
        "gpio_pins": [1, 2, 3],
        "cpu_temp_threshold_c": 70.0,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        f.flush()

        settings = load_settings(Path(f.name))

    assert settings.gpio_enabled is False
    assert settings.wifi_enabled is False
    assert settings.gpio_pins == [1, 2, 3]
    assert settings.cpu_temp_threshold_c == 70.0
    # Unspecified settings should use defaults
    assert settings.bluetooth_enabled is True
