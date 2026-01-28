# rpi-simple-debugger

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

Beginner-friendly Raspberry Pi debugging helper.

This library exposes a small FastAPI application that streams:

- **GPIO** digital pin state changes
- **WiFi/Bluetooth** connection information
- **System health** (CPU temperature, CPU usage, disk usage)

The data is sent over WebSockets so any UI (web dashboard, Tkinter/PyQt tool, or another process) can subscribe and visualize it in real-time.

## Installation

**On your Raspberry Pi (recommended):**

```bash
pip install rpi-simple-debugger
```

**For development in this repo:**

```bash
# Clone the repository
git clone https://github.com/Ponsriram/rpi-simple-debugger.git
cd rpi-simple-debugger

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with Raspberry Pi dependencies
pip install -e .[raspberry]

# Install WebSocket support for uvicorn
pip install websockets
```

## Quick Start

**Option 1: Start from Python code (recommended for library usage)**

```python
from rpi_simple_debugger import start_debugger_server, DebuggerSettings, push_custom

# Optional: customize settings
settings = DebuggerSettings(
    gpio_enabled=True,
    wifi_enabled=True,
    bluetooth_enabled=True,
    system_health_enabled=True,
    gpio_labels=[
        {"pin": 17, "label": "LED"},
        {"pin": 27, "label": "Button"},
    ],
)

# Start the debugger server in a background thread
handle = start_debugger_server(
    host="0.0.0.0",
    port=8000,
    settings=settings,
)

# Your application code here
# ...

# Push custom debug data
push_custom("my_app", {"state": "running", "jobs": 5})

# Optional: stop the server on shutdown
# handle.stop()
```

**Option 2: Run from command line (CLI)**

```bash
# Basic usage
python -m rpi_simple_debugger

# With custom host and port
python -m rpi_simple_debugger --host 0.0.0.0 --port 8000

# Disable specific monitors
python -m rpi_simple_debugger --no-gpio --no-bluetooth

# Use a config file
python -m rpi_simple_debugger --config settings.json

# Or use uvicorn directly
uvicorn rpi_simple_debugger.app:create_app --factory --host 0.0.0.0 --port 8000
```

**Option 3: Mount in existing FastAPI app**

```python
from fastapi import FastAPI
from rpi_simple_debugger import create_app, DebuggerSettings

main_app = FastAPI()
debug_app = create_app(DebuggerSettings())
main_app.mount("/debug", debug_app)
```

**3. Connect to the API:**

- **WebSocket:** `ws://<pi-address>:8000/ws` for live updates
- **REST API:** `http://<pi-address>:8000/status` for the latest snapshot

## API Reference

### REST Endpoints

#### `GET /status`

Returns the most recent snapshot of all monitoring data.

**Response Format:**

```json
{
  "gpio": {
    "17": {
      "pin": 17,
      "value": 1,
      "label": "LED",
      "mode": "in",
      "pull": "none",
      "timestamp": "2025-11-18T12:34:56.789Z"
    }
  },
  "wifi": {
    "connected": true,
    "ssid": "MyNetwork",
    "ip_address": "192.168.1.42",
    "signal_level_dbm": -55,
    "timestamp": "2025-11-18T12:34:56.789Z"
  },
  "bluetooth": {
    "powered": true,
    "connected": false,
    "timestamp": "2025-11-18T12:34:56.789Z"
  },
  "system": {
    "cpu_temp_c": 52.3,
    "cpu_percent": 23.5,
    "disk_used_percent": 41.2,
    "memory_percent": 32.1,
    "swap_percent": 0.0,
    "load_1": 0.18,
    "load_5": 0.12,
    "load_15": 0.05,
    "uptime_s": 12345.6,
    "boot_time": 1699700000.0,
    "process_count": 112,
    "timestamp": "2025-11-18T12:34:56.789Z"
  },
  "interfaces": [
    {
      "name": "wlan0",
      "is_up": true,
      "rx_bytes": 1048576,
      "tx_bytes": 524288,
      "rx_errs": 0,
      "tx_errs": 0
    }
  ],
  "health": {
    "cpu_hot": false,
    "disk_low": false,
    "memory_high": false,
    "wifi_poor": false
  },
  "gpio_schema": {
    "17": {
      "pin": 17,
      "label": "LED",
      "mode": "in",
      "pull": "none"
    }
  },
  "board": {
    "name": "armv7l",
    "cpu_arch": "armv7l",
    "os": "Linux 5.10.63"
  },
  "app": {
    "debugger_version": "0.1.0",
    "python_version": "3.9.2"
  },
  "custom": {}
}
```

**Field Descriptions:**

- `gpio`: Latest state of each monitored GPIO pin with mode and pull configuration
- `wifi`: WiFi connection status with signal strength
- `bluetooth`: Bluetooth adapter status
- `system`: System health metrics including CPU, memory, disk, load averages, uptime
- `interfaces`: Per-interface network statistics (RX/TX bytes and errors)
- `health`: Derived health flags based on configured thresholds
- `gpio_schema`: Pin definitions for building dynamic UIs
- `board`: Board and OS information
- `app`: Debugger and Python version
- `custom`: User-provided debug data via `push_custom()`

### WebSocket Endpoint

#### `WS /ws`

Establishes a WebSocket connection that broadcasts real-time updates whenever monitored values change.

**Message Types:**

All WebSocket messages follow this structure:

```json
{
  "type": "<message_type>",
  "data": { ... }
}
```

#### GPIO Update

Sent whenever a GPIO pin changes state (0→1 or 1→0).

```json
{
  "type": "gpio",
  "data": {
    "pin": 17,
    "value": 1,
    "label": "LED",
    "mode": "in",
    "pull": "none",
    "timestamp": "2025-11-18T12:34:56.789Z"
  }
}
```

**Fields:**

- `pin` (integer): BCM pin number
- `value` (integer): Current pin state (0 = LOW, 1 = HIGH)
- `label` (string|null): Human-readable label from configuration, or `null` if not set
- `mode` (string): GPIO mode (`"in"` or `"out"`)
- `pull` (string): Pull resistor configuration (`"up"`, `"down"`, or `"none"`)
- `timestamp` (string): ISO 8601 timestamp

**Note:** GPIO updates are only sent when pin states change. Connect a button, switch, or wire to trigger updates.

#### WiFi Update

Sent periodically (default: every 2 seconds) with WiFi connection status.

```json
{
  "type": "wifi",
  "data": {
    "connected": true,
    "ssid": "MyNetwork",
    "ip_address": "192.168.1.42",
    "signal_level_dbm": -67
  }
}
```

**Fields:**

- `connected` (boolean): Whether WiFi is currently connected
- `ssid` (string|null): Network name, or `null` if disconnected
- `ip_address` (string|null): Current IP address, or `null` if disconnected
- `signal_level_dbm` (integer|null): Signal strength in dBm (typically -30 to -90), or `null` if unavailable

#### Bluetooth Update

Sent periodically (default: every 2 seconds) with Bluetooth status.

```json
{
  "type": "bluetooth",
  "data": {
    "powered": true,
    "connected": false,
    "timestamp": "2025-11-18T12:34:56.789Z"
  }
}
```

**Fields:**

- `powered` (boolean): Whether Bluetooth adapter is powered on
- `connected` (boolean): Whether any Bluetooth device is currently connected
- `timestamp` (string): ISO 8601 timestamp

#### Meta Update

Sent on server startup and when clients connect, providing board capabilities and current state.

```json
{
  "type": "meta",
  "data": {
    "board": {
      "name": "armv7l",
      "cpu_arch": "armv7l",
      "os": "Linux 5.10.63"
    },
    "app": {
      "debugger_version": "0.1.0",
      "python_version": "3.9.2"
    },
    "timestamp": "2025-11-18T12:34:56.789Z",
    "enabled": {
      "gpio": true,
      "wifi": true,
      "bluetooth": true,
      "system_health": true
    }
  }
}
```

**Fields:**

- `board`: Hardware and OS information
- `app`: Debugger and Python version
- `enabled`: Which monitoring subsystems are active
- `timestamp`: ISO 8601 timestamp

#### Custom Data Update

Sent when user code calls `push_custom()` to stream application-specific debug data.

```json
{
  "type": "custom",
  "data": {
    "name": "my_app",
    "payload": {
      "state": "running",
      "jobs": 5
    },
    "timestamp": "2025-11-18T12:34:56.789Z"
  }
}
```

**Fields:**

- `name` (string): Custom data stream name
- `payload` (object): Arbitrary JSON data provided by user
- `timestamp` (string): ISO 8601 timestamp

#### System Health Update

Sent periodically (default: every 2 seconds) with system health metrics.

```json
{
  "type": "system",
  "data": {
    "cpu_temp_c": 47.2,
    "cpu_percent": 6.6,
    "disk_used_percent": 18.8,
    "memory_percent": 32.1,
    "swap_percent": 0.0,
    "load_1": 0.18,
    "load_5": 0.12,
    "load_15": 0.05,
    "uptime_s": 12345.6,
    "boot_time": 1699700000.0,
    "process_count": 112,
    "timestamp": "2025-11-18T12:34:56.789Z"
  }
}
```

**Fields:**

- `cpu_temp_c` (float|null): CPU temperature in Celsius, or `null` if unavailable
- `cpu_percent` (float): CPU usage percentage (0-100)
- `disk_used_percent` (float): Disk usage percentage (0-100)
- `memory_percent` (float): Memory usage percentage (0-100)
- `swap_percent` (float|null): Swap usage percentage (0-100)
- `load_1`, `load_5`, `load_15` (float|null): System load averages (1/5/15 min)
- `uptime_s` (float|null): System uptime in seconds
- `boot_time` (float|null): Boot time as Unix timestamp
- `process_count` (int|null): Total number of running processes
- `timestamp` (string): ISO 8601 timestamp

## Example Client

A WebSocket subscriber client is included in `tests/ws_subscriber.py`:

```bash
# View formatted output
python3 tests/ws_subscriber.py --host <pi-address>

# View raw JSON output
python3 tests/ws_subscriber.py --host <pi-address> --raw
```

## Configuration

All configuration is optional. If no `rpi_debugger_settings.json` file is present, the application uses sensible defaults.

**Configuration Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `gpio_enabled` | boolean | `true` | Enable GPIO monitoring |
| `wifi_enabled` | boolean | `true` | Enable WiFi monitoring |
| `bluetooth_enabled` | boolean | `true` | Enable Bluetooth monitoring |
| `system_health_enabled` | boolean | `true` | Enable system health monitoring |
| `gpio_poll_interval_s` | float | `0.1` | GPIO polling interval in seconds |
| `network_poll_interval_s` | float | `2.0` | Network polling interval in seconds |
| `system_poll_interval_s` | float | `2.0` | System health polling interval in seconds |
| `gpio_labels` | array | `[]` | Array of pin labels: `[{"pin": 17, "label": "LED"}]` |
| `gpio_pins` | array | `null` | Custom list of BCM pins to monitor (uses defaults if null) |
| `gpio_backend` | string | `"auto"` | GPIO backend: `"auto"`, `"rpi"`, `"gpiozero"`, or `"mock"` |
| `cpu_temp_threshold_c` | float | `80.0` | CPU temperature threshold for `cpu_hot` health flag |
| `disk_usage_threshold_percent` | float | `90.0` | Disk usage threshold for `disk_low` health flag |
| `memory_usage_threshold_percent` | float | `90.0` | Memory usage threshold for `memory_high` health flag |
| `wifi_signal_threshold_dbm` | int | `-75` | WiFi signal threshold for `wifi_poor` health flag |
| `cors_enabled` | boolean | `true` | Enable CORS for web dashboards |
| `cors_origins` | array | `["*"]` | Allowed CORS origins |

**Default Monitored GPIO Pins (BCM numbering):**
`2, 3, 4, 17, 18, 22, 23, 24, 25, 27`

These are generally safe input pins on Raspberry Pi 3/4 models. You can customize this with `gpio_pins`.

## Design Goals

- **No custom hardware required** – uses on-board peripherals only
- **Safe defaults** – GPIO configured as inputs only, graceful failure on non-Raspberry Pi machines
- **Board-agnostic** – pluggable GPIO backends support custom boards and mock testing
- **Minimal configuration** – programmatic settings or optional JSON file
- **Type-safe** – all data modeled with Pydantic for validation and schema generation
- **Embeddable** – start from code or mount in existing FastAPI apps
- **Clear, commented code** – intended for learners and educators
- **Build any UI** – FastAPI backend works with any frontend framework

## Documentation

- [Full Guide](docs/GUIDE.md) - Comprehensive setup and usage guide
- [Contributing](CONTRIBUTING.md) - How to contribute to this project
- [License](LICENSE) - MIT License

## Requirements

- Python 3.9+
- Raspberry Pi OS (or any Linux distribution for development)
- FastAPI 0.115.0+
- uvicorn 0.30.0+
- pydantic 2.7.0+
- psutil 6.0.0+
- RPi.GPIO 0.7.0+ (Raspberry Pi only, optional)
- gpiozero 2.0.0+ (alternative GPIO backend, optional)
- websockets (for WebSocket support)

## CLI Reference

```
usage: python -m rpi_simple_debugger [-h] [--host HOST] [--port PORT]
                                     [--config CONFIG] [--no-gpio] [--no-wifi]
                                     [--no-bluetooth] [--no-system]
                                     [--gpio-backend {auto,rpi,gpiozero,mock}]
                                     [--gpio-interval INTERVAL] [--reload]
                                     [--version]

Options:
  --host HOST           Host address to bind to (default: 0.0.0.0)
  --port PORT           Port to bind to (default: 8000)
  --config CONFIG       Path to JSON configuration file
  --no-gpio             Disable GPIO monitoring
  --no-wifi             Disable WiFi monitoring
  --no-bluetooth        Disable Bluetooth monitoring
  --no-system           Disable system health monitoring
  --gpio-backend        GPIO backend: auto, rpi, gpiozero, or mock
  --gpio-interval       GPIO polling interval in seconds (default: 0.1)
  --reload              Enable auto-reload for development
  --version             Show version and exit
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
