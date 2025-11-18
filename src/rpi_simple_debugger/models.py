from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class GPIOState(BaseModel):
    pin: int = Field(..., description="BCM pin number")
    value: int = Field(..., description="Logical value 0 or 1")
    label: Optional[str] = Field(None, description="Human-readable label for the pin")
    mode: Literal["in", "out"] = Field("in", description="GPIO mode")
    pull: Literal["up", "down", "none"] = Field(
        "none", description="Configured pull resistor mode"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WiFiStatus(BaseModel):
    connected: bool
    ssid: Optional[str] = None
    ip_address: Optional[str] = None
    signal_level_dbm: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BluetoothStatus(BaseModel):
    powered: bool
    connected: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SystemHealth(BaseModel):
    cpu_temp_c: Optional[float] = None
    cpu_percent: float
    disk_used_percent: float
    memory_percent: Optional[float] = None
    swap_percent: Optional[float] = None
    load_1: Optional[float] = None
    load_5: Optional[float] = None
    load_15: Optional[float] = None
    uptime_s: Optional[float] = None
    boot_time: Optional[float] = None
    process_count: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProcessInfo(BaseModel):
    pid: int
    name: Optional[str] = None
    cpu_percent: Optional[float] = None


class HealthSummary(BaseModel):
    cpu_hot: bool = False
    disk_low: bool = False
    memory_high: bool = False
    wifi_poor: bool = False


class BoardInfo(BaseModel):
    name: Optional[str] = None
    revision: Optional[str] = None
    serial: Optional[str] = None
    cpu_arch: Optional[str] = None
    os: Optional[str] = None


class AppInfo(BaseModel):
    debugger_version: str
    python_version: str


class NetInterfaceStats(BaseModel):
    name: str
    is_up: bool
    rx_bytes: int
    tx_bytes: int
    rx_errs: int
    tx_errs: int


class CustomEntry(BaseModel):
    name: str
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class GPIOPinDefinition(BaseModel):
    pin: int
    label: Optional[str] = None
    mode: Literal["in", "out"] = "in"
    pull: Literal["up", "down", "none"] = "none"


class DebuggerSnapshot(BaseModel):
    gpio: Dict[int, GPIOState] = Field(default_factory=dict)
    wifi: Optional[WiFiStatus] = None
    bluetooth: Optional[BluetoothStatus] = None
    system: Optional[SystemHealth] = None
    custom: Dict[str, CustomEntry] = Field(default_factory=dict)
    interfaces: List[NetInterfaceStats] = Field(default_factory=list)
    health: HealthSummary = Field(default_factory=HealthSummary)
    gpio_schema: Dict[int, GPIOPinDefinition] = Field(default_factory=dict)
    board: Optional[BoardInfo] = None
    app: AppInfo


class DebuggerMessage(BaseModel):
    type: Literal["gpio", "wifi", "bluetooth", "system", "custom", "meta"]
    data: Dict[str, Any]
