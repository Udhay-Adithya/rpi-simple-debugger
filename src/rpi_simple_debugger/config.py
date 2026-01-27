from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class GPIOLabel(BaseModel):
    pin: int = Field(..., description="BCM pin number")
    label: str = Field(..., description="Human-readable purpose label")


class DebuggerSettings(BaseModel):
    gpio_enabled: bool = True
    wifi_enabled: bool = True
    bluetooth_enabled: bool = True
    system_health_enabled: bool = True

    gpio_poll_interval_s: float = 0.1
    network_poll_interval_s: float = 2.0
    system_poll_interval_s: float = 2.0

    gpio_labels: List[GPIOLabel] = Field(default_factory=list)
    gpio_pins: Optional[List[int]] = Field(
        default=None,
        description=(
            "List of BCM pin numbers to monitor. If None, uses default safe pins: "
            "[2, 3, 4, 17, 18, 22, 23, 24, 25, 27]"
        ),
    )
    gpio_backend: str = Field(
        "auto",
        description=(
            "Which GPIO backend to use: 'auto', 'rpi', 'gpiozero', 'mock', or a "
            "custom backend string understood by the host application."
        ),
    )

    # Health thresholds for HealthSummary flags
    cpu_temp_threshold_c: float = Field(
        80.0,
        description="CPU temperature threshold in Celsius. Above this, cpu_hot=True.",
    )
    disk_usage_threshold_percent: float = Field(
        90.0,
        description="Disk usage threshold percentage. Above this, disk_low=True.",
    )
    memory_usage_threshold_percent: float = Field(
        90.0,
        description="Memory usage threshold percentage. Above this, memory_high=True.",
    )
    wifi_signal_threshold_dbm: int = Field(
        -75,
        description="WiFi signal threshold in dBm. Below this, wifi_poor=True.",
    )

    # CORS settings for web dashboards
    cors_enabled: bool = Field(
        True,
        description="Enable CORS middleware for cross-origin requests from web dashboards.",
    )
    cors_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="List of allowed origins for CORS. Use ['*'] to allow all origins.",
    )

    @property
    def gpio_label_map(self) -> Dict[int, str]:
        return {item.pin: item.label for item in self.gpio_labels}

    @property
    def effective_gpio_pins(self) -> List[int]:
        """Return configured pins or default safe pins for Pi 3/4."""
        if self.gpio_pins is not None:
            return self.gpio_pins
        return [2, 3, 4, 17, 18, 22, 23, 24, 25, 27]


DEFAULT_CONFIG_PATH = Path("rpi_debugger_settings.json")


def load_settings(path: Optional[Path] = None) -> DebuggerSettings:
    """Load settings from a JSON file or return defaults.

    This keeps configuration simple for beginners while still allowing
    customization when needed.
    """

    import json

    target = path or DEFAULT_CONFIG_PATH
    if target.is_file():
        data = json.loads(target.read_text())
        return DebuggerSettings.model_validate(data)

    return DebuggerSettings()
