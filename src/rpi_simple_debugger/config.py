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

    @property
    def gpio_label_map(self) -> Dict[int, str]:
        return {item.pin: item.label for item in self.gpio_labels}


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
