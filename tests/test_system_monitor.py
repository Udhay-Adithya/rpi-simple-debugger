"""Tests for the system monitor module."""

from rpi_simple_debugger.system_monitor import SystemMonitor
from rpi_simple_debugger.models import SystemHealth


def test_system_monitor_collects_health() -> None:
    """SystemMonitor should collect system health data."""
    collected_health = []

    def on_update(health: SystemHealth) -> None:
        collected_health.append(health)

    monitor = SystemMonitor(interval_s=0.1, on_update=on_update)

    # Directly call _get_health to test collection without threading
    health = monitor._get_health()

    assert isinstance(health, SystemHealth)
    assert health.cpu_percent >= 0
    assert health.disk_used_percent >= 0
    # Memory percent should be set
    assert health.memory_percent is not None
    assert health.memory_percent >= 0


def test_system_monitor_health_fields() -> None:
    """SystemMonitor should populate expected health fields."""
    monitor = SystemMonitor(interval_s=0.1, on_update=lambda h: None)
    health = monitor._get_health()

    # These should always be available
    assert hasattr(health, "cpu_percent")
    assert hasattr(health, "disk_used_percent")
    assert hasattr(health, "memory_percent")
    assert hasattr(health, "swap_percent")
    assert hasattr(health, "process_count")
    assert hasattr(health, "top_processes")


def test_system_monitor_top_processes() -> None:
    """SystemMonitor should collect top processes."""
    monitor = SystemMonitor(interval_s=0.1, on_update=lambda h: None)
    health = monitor._get_health()

    # top_processes should be populated (may be None on some systems)
    if health.top_processes is not None:
        assert isinstance(health.top_processes, list)
        # Should have at most 3 processes
        assert len(health.top_processes) <= 3
        for proc in health.top_processes:
            assert proc.pid > 0


def test_system_monitor_start_stop() -> None:
    """SystemMonitor should start and stop without errors."""
    collected = []

    def on_update(health: SystemHealth) -> None:
        collected.append(health)

    monitor = SystemMonitor(interval_s=0.05, on_update=on_update)

    # Start monitoring
    monitor.start()

    # Wait a bit for at least one collection
    import time
    time.sleep(0.15)

    # Stop monitoring
    monitor.stop()

    # Should have collected at least one health reading
    assert len(collected) >= 1


def test_system_monitor_double_start() -> None:
    """Starting monitor twice should not create multiple threads."""
    monitor = SystemMonitor(interval_s=0.1, on_update=lambda h: None)

    monitor.start()
    thread1 = monitor._thread

    monitor.start()  # Second start
    thread2 = monitor._thread

    # Should be the same thread
    assert thread1 is thread2

    monitor.stop()
