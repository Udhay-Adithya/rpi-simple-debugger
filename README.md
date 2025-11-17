# rpi-simple-debugger

Beginner-friendly Raspberry Pi debugging helper.

This library exposes a small FastAPI application that streams:

- GPIO digital pin state changes
- WiFi/Bluetooth connection information
- Basic system health (CPU temperature, CPU usage, disk usage)

The data is sent over WebSockets so any UI (web dashboard,
Tkinter / PyQt tool, or another process) can subscribe and
visualize it.

## Installation

On your Raspberry Pi (recommended):

```bash
pip install rpi-simple-debugger
```

For development in this repo:

```bash
pip install -e .[raspberry]
```

## Quick start

Create a simple settings file (optional):

```jsonc
// rpi_debugger_settings.json
{
  "gpio_enabled": true,
  "wifi_enabled": true,
  "bluetooth_enabled": true,
  "system_health_enabled": true,
  "gpio_labels": [
    { "pin": 17, "label": "LED" },
    { "pin": 27, "label": "Button" }
  ]
}
```

Run the server:

```bash
uvicorn rpi_simple_debugger.app:create_app --factory --host 0.0.0.0 --port 8000
```

Then connect a WebSocket client to:

- `ws://<pi-address>:8000/ws` for live updates
- `http://<pi-address>:8000/status` for the latest snapshot

## Data format

Messages sent over WebSockets use simple JSON structures designed
to be easy to inspect and use in beginner projects.

Example GPIO update:

```json
{
  "type": "gpio",
  "data": { "pin": 17, "value": 1, "label": "LED" }
}
```

Example WiFi update:

```json
{
  "type": "wifi",
  "data": {
    "connected": true,
    "ssid": "MyNetwork",
    "ip_address": "192.168.1.42",
    "signal_level_dbm": -55
  }
}
```

System health update:

```json
{
  "type": "system",
  "data": {
    "cpu_temp_c": 52.3,
    "cpu_percent": 23.5,
    "disk_used_percent": 41.2
  }
}
```

## Design goals

- No custom hardware required – uses on-board peripherals only.
- Safe defaults for GPIO (inputs only) and graceful failure when
  running on non-Raspberry Pi machines.
- Minimal configuration via a single JSON file.
- Clear, commented code intended for learners and educators.

You can build any UI you like on top of this backend.
