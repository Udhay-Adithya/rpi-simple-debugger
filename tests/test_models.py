"""Tests for the models module."""

from datetime import datetime

from rpi_simple_debugger.models import (
    BluetoothStatus,
    DebuggerSnapshot,
    GPIOPinDefinition,
    GPIOState,
    HealthSummary,
    NetInterfaceStats,
    ProcessInfo,
    SystemHealth,
    WiFiStatus,
    AppInfo,
)


def test_gpio_state_defaults() -> None:
    """GPIOState should have sensible defaults."""
    state = GPIOState(pin=17, value=1)

    assert state.pin == 17
    assert state.value == 1
    assert state.label is None
    assert state.mode == "in"
    assert state.pull == "none"
    assert isinstance(state.timestamp, datetime)


def test_gpio_state_with_label() -> None:
    """GPIOState should accept optional label."""
    state = GPIOState(pin=17, value=0, label="LED")

    assert state.label == "LED"


def test_wifi_status() -> None:
    """WiFiStatus should capture connection info."""
    status = WiFiStatus(
        connected=True,
        ssid="MyNetwork",
        ip_address="192.168.1.42",
        signal_level_dbm=-55,
    )

    assert status.connected is True
    assert status.ssid == "MyNetwork"
    assert status.ip_address == "192.168.1.42"
    assert status.signal_level_dbm == -55


def test_wifi_status_disconnected() -> None:
    """WiFiStatus should handle disconnected state."""
    status = WiFiStatus(connected=False)

    assert status.connected is False
    assert status.ssid is None
    assert status.ip_address is None


def test_bluetooth_status() -> None:
    """BluetoothStatus should capture powered and connected state."""
    status = BluetoothStatus(powered=True, connected=False)

    assert status.powered is True
    assert status.connected is False


def test_system_health() -> None:
    """SystemHealth should capture system metrics."""
    health = SystemHealth(
        cpu_temp_c=52.3,
        cpu_percent=23.5,
        disk_used_percent=41.2,
        memory_percent=32.1,
        swap_percent=0.0,
        load_1=0.18,
        load_5=0.12,
        load_15=0.05,
        uptime_s=12345.6,
        process_count=112,
    )

    assert health.cpu_temp_c == 52.3
    assert health.cpu_percent == 23.5
    assert health.disk_used_percent == 41.2
    assert health.memory_percent == 32.1


def test_system_health_with_top_processes() -> None:
    """SystemHealth should include top_processes field."""
    processes = [
        ProcessInfo(pid=1, name="systemd", cpu_percent=2.0),
        ProcessInfo(pid=100, name="python", cpu_percent=5.0),
    ]
    health = SystemHealth(
        cpu_percent=10.0,
        disk_used_percent=50.0,
        top_processes=processes,
    )

    assert health.top_processes is not None
    assert len(health.top_processes) == 2
    assert health.top_processes[0].name == "systemd"


def test_health_summary_defaults() -> None:
    """HealthSummary should default all flags to False."""
    summary = HealthSummary()

    assert summary.cpu_hot is False
    assert summary.disk_low is False
    assert summary.memory_high is False
    assert summary.wifi_poor is False


def test_net_interface_stats() -> None:
    """NetInterfaceStats should capture interface metrics."""
    stats = NetInterfaceStats(
        name="wlan0",
        is_up=True,
        rx_bytes=1048576,
        tx_bytes=524288,
        rx_errs=0,
        tx_errs=0,
    )

    assert stats.name == "wlan0"
    assert stats.is_up is True
    assert stats.rx_bytes == 1048576


def test_gpio_pin_definition() -> None:
    """GPIOPinDefinition should define pin configuration."""
    pin_def = GPIOPinDefinition(pin=17, label="LED", mode="in", pull="up")

    assert pin_def.pin == 17
    assert pin_def.label == "LED"
    assert pin_def.mode == "in"
    assert pin_def.pull == "up"


def test_debugger_snapshot() -> None:
    """DebuggerSnapshot should aggregate all state."""
    app_info = AppInfo(debugger_version="0.1.0", python_version="3.9.0")
    snapshot = DebuggerSnapshot(app=app_info)

    assert snapshot.gpio == {}
    assert snapshot.wifi is None
    assert snapshot.bluetooth is None
    assert snapshot.system is None
    assert snapshot.custom == {}
    assert snapshot.interfaces == []
    assert snapshot.health.cpu_hot is False


def test_debugger_snapshot_serialization() -> None:
    """DebuggerSnapshot should serialize to JSON correctly."""
    app_info = AppInfo(debugger_version="0.1.0", python_version="3.9.0")
    snapshot = DebuggerSnapshot(app=app_info)
    snapshot.gpio[17] = GPIOState(pin=17, value=1, label="LED")
    snapshot.wifi = WiFiStatus(connected=True, ssid="Test")

    data = snapshot.model_dump(mode="json")

    assert "gpio" in data
    assert "17" in data["gpio"] or 17 in data["gpio"]
    assert data["wifi"]["connected"] is True
