"""Tests for the engine module."""

from rpi_simple_debugger.config import DebuggerSettings
from rpi_simple_debugger.engine import DebuggerEngine, ConnectionManager
from rpi_simple_debugger.models import (
    BluetoothStatus,
    GPIOState,
    SystemHealth,
    WiFiStatus,
)


def test_engine_initialization() -> None:
    """DebuggerEngine should initialize with default snapshot."""
    settings = DebuggerSettings()
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    snapshot = engine.snapshot
    assert snapshot.gpio == {}
    assert snapshot.wifi is None
    assert snapshot.system is None
    assert snapshot.app.debugger_version == "0.1.0"


def test_engine_update_gpio() -> None:
    """update_gpio should update snapshot GPIO state."""
    settings = DebuggerSettings()
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    state = GPIOState(pin=17, value=1, label="LED")
    engine.update_gpio(state)

    assert 17 in engine.snapshot.gpio
    assert engine.snapshot.gpio[17].value == 1
    assert engine.snapshot.gpio[17].label == "LED"


def test_engine_update_wifi() -> None:
    """update_wifi should update snapshot WiFi state and health."""
    settings = DebuggerSettings()
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    status = WiFiStatus(connected=True, ssid="TestNetwork", signal_level_dbm=-60)
    engine.update_wifi(status)

    assert engine.snapshot.wifi is not None
    assert engine.snapshot.wifi.ssid == "TestNetwork"
    assert engine.snapshot.health.wifi_poor is False  # -60 > -75


def test_engine_update_wifi_poor_signal() -> None:
    """update_wifi should set wifi_poor flag for weak signal."""
    settings = DebuggerSettings(wifi_signal_threshold_dbm=-70)
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    status = WiFiStatus(connected=True, ssid="TestNetwork", signal_level_dbm=-80)
    engine.update_wifi(status)

    assert engine.snapshot.health.wifi_poor is True


def test_engine_update_bluetooth() -> None:
    """update_bluetooth should update snapshot Bluetooth state."""
    settings = DebuggerSettings()
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    status = BluetoothStatus(powered=True, connected=False)
    engine.update_bluetooth(status)

    assert engine.snapshot.bluetooth is not None
    assert engine.snapshot.bluetooth.powered is True
    assert engine.snapshot.bluetooth.connected is False


def test_engine_update_system() -> None:
    """update_system should update snapshot and compute health flags."""
    settings = DebuggerSettings()
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    health = SystemHealth(
        cpu_temp_c=75.0,
        cpu_percent=50.0,
        disk_used_percent=85.0,
        memory_percent=70.0,
    )
    engine.update_system(health)

    assert engine.snapshot.system is not None
    assert engine.snapshot.system.cpu_temp_c == 75.0
    # 75°C < 80°C threshold, so cpu_hot should be False
    assert engine.snapshot.health.cpu_hot is False
    # 85% < 90% threshold, so disk_low should be False
    assert engine.snapshot.health.disk_low is False


def test_engine_health_flags_hot_cpu() -> None:
    """Health flags should indicate hot CPU when above threshold."""
    settings = DebuggerSettings(cpu_temp_threshold_c=70.0)
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    health = SystemHealth(
        cpu_temp_c=75.0,
        cpu_percent=50.0,
        disk_used_percent=50.0,
    )
    engine.update_system(health)

    assert engine.snapshot.health.cpu_hot is True


def test_engine_health_flags_low_disk() -> None:
    """Health flags should indicate low disk when above threshold."""
    settings = DebuggerSettings(disk_usage_threshold_percent=80.0)
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    health = SystemHealth(
        cpu_percent=50.0,
        disk_used_percent=85.0,
    )
    engine.update_system(health)

    assert engine.snapshot.health.disk_low is True


def test_engine_health_flags_high_memory() -> None:
    """Health flags should indicate high memory when above threshold."""
    settings = DebuggerSettings(memory_usage_threshold_percent=80.0)
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    health = SystemHealth(
        cpu_percent=50.0,
        disk_used_percent=50.0,
        memory_percent=85.0,
    )
    engine.update_system(health)

    assert engine.snapshot.health.memory_high is True


def test_engine_set_gpio_schema() -> None:
    """set_gpio_schema should populate gpio_schema in snapshot."""
    settings = DebuggerSettings()
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    pins = [17, 27]
    label_map = {17: "LED", 27: "Button"}
    engine.set_gpio_schema(pins, label_map)

    assert 17 in engine.snapshot.gpio_schema
    assert engine.snapshot.gpio_schema[17].label == "LED"
    assert 27 in engine.snapshot.gpio_schema
    assert engine.snapshot.gpio_schema[27].label == "Button"


def test_engine_push_custom() -> None:
    """push_custom should add custom data to snapshot."""
    settings = DebuggerSettings()
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    engine.push_custom("my_app", {"state": "running", "version": "1.0"})

    assert "my_app" in engine.snapshot.custom
    assert engine.snapshot.custom["my_app"].payload["state"] == "running"


def test_engine_update_interfaces() -> None:
    """update_interfaces should update snapshot interfaces."""
    from rpi_simple_debugger.models import NetInterfaceStats

    settings = DebuggerSettings()
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    interfaces = [
        NetInterfaceStats(
            name="wlan0",
            is_up=True,
            rx_bytes=1000,
            tx_bytes=500,
            rx_errs=0,
            tx_errs=0,
        )
    ]
    engine.update_interfaces(interfaces)

    assert len(engine.snapshot.interfaces) == 1
    assert engine.snapshot.interfaces[0].name == "wlan0"


def test_engine_board_detection() -> None:
    """Engine should detect board info on initialization."""
    settings = DebuggerSettings()
    engine = DebuggerEngine(settings=settings, version="0.1.0")

    # Board info should be populated (may vary by platform)
    assert engine.snapshot.board is not None
    assert engine.snapshot.board.os is not None


def test_connection_manager_disconnect_not_connected() -> None:
    """disconnect should handle websocket not in list gracefully."""
    manager = ConnectionManager()

    # Should not raise when disconnecting non-existent connection
    class FakeWebSocket:
        pass

    manager.disconnect(FakeWebSocket())  # type: ignore
