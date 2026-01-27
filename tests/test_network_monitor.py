"""Tests for the network monitor module."""

from rpi_simple_debugger.network_monitor import NetworkMonitor
from rpi_simple_debugger.models import WiFiStatus, BluetoothStatus, NetInterfaceStats


def test_network_monitor_collects_wifi() -> None:
    """NetworkMonitor should collect WiFi status."""
    collected_wifi = []

    def on_wifi(status: WiFiStatus) -> None:
        collected_wifi.append(status)

    def on_bt(status: BluetoothStatus) -> None:
        pass

    monitor = NetworkMonitor(interval_s=0.1, on_wifi=on_wifi, on_bt=on_bt)

    # Directly call _get_wifi_status to test collection
    status = monitor._get_wifi_status()

    assert isinstance(status, WiFiStatus)
    assert isinstance(status.connected, bool)


def test_network_monitor_collects_bluetooth() -> None:
    """NetworkMonitor should collect Bluetooth status."""
    collected_bt = []

    def on_wifi(status: WiFiStatus) -> None:
        pass

    def on_bt(status: BluetoothStatus) -> None:
        collected_bt.append(status)

    monitor = NetworkMonitor(interval_s=0.1, on_wifi=on_wifi, on_bt=on_bt)

    # Directly call _get_bt_status to test collection
    status = monitor._get_bt_status()

    assert isinstance(status, BluetoothStatus)
    assert isinstance(status.powered, bool)
    assert isinstance(status.connected, bool)


def test_network_monitor_collects_interfaces() -> None:
    """NetworkMonitor should collect interface statistics."""
    collected_interfaces = []

    def on_wifi(status: WiFiStatus) -> None:
        pass

    def on_bt(status: BluetoothStatus) -> None:
        pass

    def on_interfaces(interfaces):
        collected_interfaces.extend(interfaces)

    monitor = NetworkMonitor(
        interval_s=0.1,
        on_wifi=on_wifi,
        on_bt=on_bt,
        on_interfaces=on_interfaces,
    )

    # Directly call _get_interface_stats to test collection
    interfaces = monitor._get_interface_stats()

    assert isinstance(interfaces, list)
    # Should have at least one interface (loopback)
    if len(interfaces) > 0:
        iface = interfaces[0]
        assert isinstance(iface, NetInterfaceStats)
        assert isinstance(iface.name, str)
        assert isinstance(iface.is_up, bool)
        assert iface.rx_bytes >= 0
        assert iface.tx_bytes >= 0


def test_network_monitor_start_stop() -> None:
    """NetworkMonitor should start and stop without errors."""
    collected_wifi = []
    collected_bt = []

    def on_wifi(status: WiFiStatus) -> None:
        collected_wifi.append(status)

    def on_bt(status: BluetoothStatus) -> None:
        collected_bt.append(status)

    monitor = NetworkMonitor(interval_s=0.05, on_wifi=on_wifi, on_bt=on_bt)

    # Start monitoring
    monitor.start()

    # Wait a bit for at least one collection
    import time
    time.sleep(0.15)

    # Stop monitoring
    monitor.stop()

    # Should have collected readings
    assert len(collected_wifi) >= 1
    assert len(collected_bt) >= 1


def test_network_monitor_double_start() -> None:
    """Starting monitor twice should not create multiple threads."""
    monitor = NetworkMonitor(
        interval_s=0.1,
        on_wifi=lambda w: None,
        on_bt=lambda b: None,
    )

    monitor.start()
    thread1 = monitor._thread

    monitor.start()  # Second start
    thread2 = monitor._thread

    # Should be the same thread
    assert thread1 is thread2

    monitor.stop()


def test_network_monitor_interfaces_callback_optional() -> None:
    """NetworkMonitor should work without on_interfaces callback."""
    monitor = NetworkMonitor(
        interval_s=0.1,
        on_wifi=lambda w: None,
        on_bt=lambda b: None,
        on_interfaces=None,  # Not provided
    )

    # Should not raise when running loop
    monitor.start()
    import time
    time.sleep(0.05)
    monitor.stop()
