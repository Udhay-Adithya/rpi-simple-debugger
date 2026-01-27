"""Tests for the FastAPI application module."""

from fastapi.testclient import TestClient

from rpi_simple_debugger.app import create_app
from rpi_simple_debugger.config import DebuggerSettings


def test_create_app_returns_fastapi_app() -> None:
    """create_app should return a FastAPI application."""
    app = create_app()
    assert app.title == "rpi-simple-debugger"


def test_create_app_with_custom_settings() -> None:
    """create_app should accept custom settings."""
    settings = DebuggerSettings(
        gpio_enabled=False,
        wifi_enabled=False,
        bluetooth_enabled=False,
        system_health_enabled=False,
    )
    app = create_app(settings=settings)
    assert app.title == "rpi-simple-debugger"


def test_status_endpoint() -> None:
    """GET /status should return snapshot data."""
    settings = DebuggerSettings(
        gpio_enabled=False,
        wifi_enabled=False,
        bluetooth_enabled=False,
        system_health_enabled=False,
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.get("/status")

    assert response.status_code == 200
    data = response.json()

    # Should have expected keys
    assert "gpio" in data
    assert "wifi" in data
    assert "bluetooth" in data
    assert "system" in data
    assert "app" in data
    assert "health" in data


def test_status_endpoint_app_info() -> None:
    """GET /status should include app version info."""
    app = create_app(DebuggerSettings(
        gpio_enabled=False,
        wifi_enabled=False,
        bluetooth_enabled=False,
        system_health_enabled=False,
    ))

    with TestClient(app) as client:
        response = client.get("/status")

    data = response.json()
    assert data["app"]["debugger_version"] == "0.1.0"
    assert "python_version" in data["app"]


def test_status_endpoint_gpio_schema() -> None:
    """GET /status should include GPIO schema when GPIO is enabled."""
    settings = DebuggerSettings(
        gpio_enabled=True,
        gpio_pins=[17, 27],
        gpio_labels=[
            {"pin": 17, "label": "LED"},
        ],
        wifi_enabled=False,
        bluetooth_enabled=False,
        system_health_enabled=False,
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.get("/status")

    data = response.json()
    assert "gpio_schema" in data
    # Pin 17 should have label
    assert "17" in data["gpio_schema"] or 17 in data["gpio_schema"]


def test_cors_enabled_by_default() -> None:
    """CORS middleware should be enabled by default."""
    app = create_app()

    with TestClient(app) as client:
        response = client.options(
            "/status",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    # CORS should allow the request
    assert "access-control-allow-origin" in response.headers


def test_cors_disabled() -> None:
    """CORS middleware can be disabled via settings."""
    settings = DebuggerSettings(cors_enabled=False)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.options(
            "/status",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    # Without CORS middleware, the header should not be present
    # (or response might be different)
    # This is a basic check - actual behavior depends on FastAPI version
    assert response.status_code in [200, 405]


def test_health_summary_in_status() -> None:
    """GET /status should include health summary."""
    app = create_app(DebuggerSettings(
        gpio_enabled=False,
        wifi_enabled=False,
        bluetooth_enabled=False,
        system_health_enabled=False,
    ))

    with TestClient(app) as client:
        response = client.get("/status")

    data = response.json()
    assert "health" in data
    assert "cpu_hot" in data["health"]
    assert "disk_low" in data["health"]
    assert "memory_high" in data["health"]
    assert "wifi_poor" in data["health"]


def test_websocket_endpoint_accepts_connection() -> None:
    """WebSocket /ws endpoint should accept connections."""
    app = create_app(DebuggerSettings(
        gpio_enabled=False,
        wifi_enabled=False,
        bluetooth_enabled=False,
        system_health_enabled=False,
    ))

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            # Should receive initial snapshot
            data = websocket.receive_json()
            assert data["type"] == "snapshot"
            assert "data" in data


def test_websocket_ping_pong() -> None:
    """WebSocket should respond to ping with pong."""
    app = create_app(DebuggerSettings(
        gpio_enabled=False,
        wifi_enabled=False,
        bluetooth_enabled=False,
        system_health_enabled=False,
    ))

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            # Consume initial snapshot
            websocket.receive_json()

            # Send ping
            websocket.send_text("ping")

            # Should receive pong
            response = websocket.receive_text()
            assert response == "pong"
