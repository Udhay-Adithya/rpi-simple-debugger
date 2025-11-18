# rpi-simple-debugger: Concept, Motivation, and System Design

## 1. Executive Summary

**rpi-simple-debugger** is a lightweight, beginner‑friendly monitoring and debugging helper for **Raspberry Pi** projects.

It runs as a small server on the Raspberry Pi and continuously observes:

- **GPIO** (digital pins) – whether they are HIGH or LOW  
- **Network connectivity** – Wi‑Fi and Bluetooth status  
- **System health** – CPU temperature, CPU load, and disk usage  

This information is exposed through:

- A **REST API** (`GET /status`) for one‑off snapshots  
- A **WebSocket stream** (`/ws`) for real‑time, continuous updates  

Any UI or tooling—simple scripts, dashboards, or more complex applications—can connect to this server, subscribe to the data, and visualize or log what the Raspberry Pi is doing.

The main goal is to make it **much easier for beginners, educators, and rapid prototyping teams** to see what their hardware and system are doing in real time, without needing to write low-level monitoring code over and over again.

---

## 2. Problem Statement and Motivation

### 2.1 Typical Pain Points When Debugging Raspberry Pi Projects

When people build projects on a Raspberry Pi—especially **beginners** or **students**—they run into a few recurring problems:

1. **“What is happening on my pins?”**  
   You connect sensors, buttons, LEDs, and other hardware to GPIO pins. If something is not working, you need to know:
   - Is the button really changing state?
   - Is the LED pin actually switching from 0 to 1?
   - Did I wire the correct pin?

   Checking this usually means writing small, one-off Python scripts, printing values in a loop, and interpreting raw numbers in the terminal.

2. **“Is it a hardware problem or a system problem?”**  
   Sometimes the issue isn’t the circuit at all:
   - The Raspberry Pi might be **overheating** (high CPU temperature).
   - The CPU might be **fully loaded**, causing delays.
   - The disk might be nearly full, leading to weird behavior.
   - The Wi‑Fi may be weak or disconnected, so network-dependent code fails.

   Beginners rarely monitor these system aspects, so they spend time debugging code or hardware when the root cause is environmental.

3. **“I need a UI, but I don’t want to build the whole stack just to debug.”**  
   To build a proper dashboard, you typically need:
   - Low‑level GPIO access code
   - System metrics collection
   - An HTTP or WebSocket server
   - A frontend that consumes that data

   For learning or quick prototyping, that’s a lot of boilerplate and distraction from the actual project goal.

### 2.2 Target Users

- **Students and hobbyists** learning electronics and Raspberry Pi programming  
- **Educators** demonstrating hardware behavior to a classroom  
- **Developers** who want a ready-made “debug layer” they can plug into their own apps  
- **Teams** building prototypes who need quick visibility into GPIO, connectivity, and system health

### 2.3 Design Goals

The library is designed around several key principles:

- **Beginner‑friendly**  
  - Simple Python API and clear configuration model  
  - Clear, commented implementation internally  
  - Uses familiar tools (FastAPI, JSON, WebSockets)

- **Safe by default**  
  - Only monitors **input** GPIO pins by default (no driving outputs, so it’s harder to damage hardware inadvertently)  
  - Gracefully degrades on non‑Raspberry Pi machines (no crashes if GPIO is unavailable)

- **Minimal setup and configuration**  
  - Works out of the box with sensible defaults  
  - Optional single JSON configuration file

- **UI‑agnostic**  
  - Exposes data via generic Web APIs  
  - Consumers can be anything: Python scripts, JavaScript dashboards, native GUI apps, etc.

---

## 3. High-Level System Overview

At a high level, **rpi-simple-debugger** is now structured as a small, embeddable “observability layer” you can attach to any Raspberry Pi project:

1. A **core engine** (`DebuggerEngine`) that owns the current snapshot of system state and manages WebSocket connections.
2. A set of **background monitoring components** that feed the engine with structured data.

- GPIO monitor (board-abstracted) for digital pin state
- Network monitor for Wi‑Fi/Bluetooth + per-interface statistics
- System monitor for CPU, memory, disk, and process-level metrics

3. A **FastAPI application** exposing:

- A **REST endpoint** (`GET /status`) returning the latest snapshot as JSON
- A **WebSocket endpoint** (`/ws`) streaming typed events

4. A **package-level API** so you can start or mount the debugger from your own code with just a few lines.

Conceptually:

1. **Monitors** (GPIO, Network, System) run in background threads.  
2. When something changes or a new reading is taken:

- The monitor emits a Pydantic model (e.g., `GPIOState`, `WiFiStatus`, `SystemHealth`).
- The `DebuggerEngine` updates an in‑memory `DebuggerSnapshot` and computes any derived health flags.
- The engine broadcasts a `DebuggerMessage` over WebSockets to all connected clients.

3. Clients can:

- Subscribe to **real-time updates** via `/ws` and receive structured `{ type, data }` messages.  
- Or periodically poll **current status** via `/status`, which returns the same data as a single snapshot.

This creates a **live, modelled “window” into the Raspberry Pi**, without the client needing direct hardware access, and without your main application needing to manage monitoring itself.

---

## 4. Functional Capabilities

### 4.1 GPIO Monitoring

- **What it does:**
  - Observes a set of Raspberry Pi GPIO pins (using Broadcom/BCM numbering).
  - Detects when any pin changes between LOW (`0`) and HIGH (`1`).
  - When a change is detected, it immediately notifies subscribers via WebSocket.

- **Why this matters:**
  - When debugging circuits (buttons, switches, sensors), you can see:
    - Whether the hardware is wired correctly.
    - Whether the software is seeing the expected transitions in real time.
  - This is extremely valuable in classroom demos or troubleshooting sessions.

- **How it behaves by default:**
  - Monitored pins:  
    `2, 3, 4, 17, 18, 22, 23, 24, 25, 27` (commonly safe input pins on Pi 3/4).
  - Reads every `0.1` seconds (configurable).
  - Only sends WebSocket messages when a pin **actually changes**; this keeps traffic low and meaningful.

- **Semantics of GPIO messages:**
  - WebSocket payload for GPIO change:

    ```json
    {
      "type": "gpio",
      "data": {
        "pin": 17,
        "value": 1,
        "label": "LED"
      }
    }
    ```

  - `label` is a human-readable description (e.g., "Start Button") defined in configuration. This is particularly useful for non-technical audiences interpreting dashboards.
  - `mode` indicates whether the pin is configured as input (`"in"`) or output (`"out"`).
  - `pull` shows the pull resistor configuration (`"up"`, `"down"`, or `"none"`).

- **GPIO Schema:**
  - On startup and in `meta` messages, the debugger sends a `gpio_schema` describing all monitored pins:

    ```json
    {
      "gpio_schema": {
        "17": {
          "pin": 17,
          "label": "LED",
          "mode": "in",
          "pull": "none"
        },
        "27": {
          "pin": 27,
          "label": "Button",
          "mode": "in",
          "pull": "none"
        }
      }
    }
    ```

  - This allows client applications to dynamically build UIs based on the monitored pins without hardcoding pin numbers.

### 4.2 Network Monitoring (Wi‑Fi, Bluetooth & Interface Stats)

- **Wi‑Fi monitoring:**
  - Checks:
    - Connection status (connected/disconnected)
    - SSID (network name)
    - IP address of the Raspberry Pi
    - Signal strength in dBm (for Wi‑Fi quality)

  - Example WebSocket payload:

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

  - Use cases:
    - Knowing whether network‑dependent code failures are due to poor Wi‑Fi.
    - Monitoring classroom or lab environments where multiple Pis connect to a shared AP.

- **Bluetooth monitoring:**
  - Tracks:
    - Whether Bluetooth is powered on.
    - Whether any device is currently connected.

  - Example:

    ```json
    {
      "type": "bluetooth",
      "data": {
        "powered": true,
        "connected": false
      }
    }
    ```

  - Use cases:
    - Basic visibility into whether Bluetooth‑based peripherals (e.g., sensors, controllers) are connected.

- **Polling behavior:**
  - Network status is typically refreshed every **2 seconds** (configurable).
  - On each cycle, the monitor sends the latest Wi‑Fi, Bluetooth, and per-interface statistics.

- **Per-interface network statistics:**
  - The network monitor now collects statistics for each network interface (e.g., `wlan0`, `eth0`):
    - `name`: Interface name
    - `is_up`: Whether the interface is currently active
    - `rx_bytes`: Total bytes received
    - `tx_bytes`: Total bytes transmitted
    - `rx_errs`: Receive errors
    - `tx_errs`: Transmit errors

  - Example payload:

    ```json
    {
      "interfaces": [
        {
          "name": "wlan0",
          "is_up": true,
          "rx_bytes": 1048576,
          "tx_bytes": 524288,
          "rx_errs": 0,
          "tx_errs": 0
        },
        {
          "name": "eth0",
          "is_up": false,
          "rx_bytes": 0,
          "tx_bytes": 0,
          "rx_errs": 0,
          "tx_errs": 0
        }
      ]
    }
    ```

  - Use cases:
    - Monitor bandwidth usage in real-time.
    - Detect interface errors that might indicate hardware or driver issues.
    - Distinguish between wired and wireless network activity.

### 4.3 System Health Monitoring

- **Monitored metrics:**
  - **CPU temperature** (where available—common on Raspberry Pi)
  - **CPU usage percentage**
  - **Disk usage percentage** for the root filesystem (`/`)
  - **Memory usage percentage**
  - **Swap usage percentage**
  - **Load averages** (1/5/15 minute, where supported by the OS)
  - **Uptime** and **boot time** (seconds since epoch)
  - **Process count** and (optionally) top CPU-heavy processes

- **Typical payload (system update message):**

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

- **Why this matters:**
  - CPU temperature and load directly affect performance and stability, especially in enclosed or fanless setups.
  - Disk and memory capacity issues are a common practical problem; near‑full disks can cause hard‑to‑diagnose application failures.
  - Load averages and process counts help you distinguish “my code is slow” from “the system is globally overloaded”.
  - For teaching and demonstrations, it helps students understand the relationship between workload, temperature, memory pressure, and performance.

- **Polling behavior:**
  - Default interval is **2 seconds** (configurable in `DebuggerSettings`).
  - Can be increased (e.g., 10–30 seconds) to reduce overhead or tuned differently per use case.

### 4.4 Health Summary and Alerts

The debugger automatically computes derived health flags based on configurable thresholds:

- **Health flags:**
  - `cpu_hot`: CPU temperature exceeds threshold (default: 80°C)
  - `disk_low`: Disk usage exceeds threshold (default: 90%)
  - `memory_high`: Memory usage exceeds threshold (default: 90%)
  - `wifi_poor`: WiFi signal is below threshold (default: -75 dBm)

- **Example `HealthSummary` in `/status`:**

  ```json
  {
    "health": {
      "cpu_hot": false,
      "disk_low": false,
      "memory_high": false,
      "wifi_poor": true
    }
  }
  ```

- **Why this matters:**
  - Provides at-a-glance status for common issues.
  - Clients can trigger alerts or UI indicators based on these flags.
  - Thresholds can be customized via `DebuggerSettings` for specific environments.

---

## 5. External Interfaces: How Clients Use the System

### 5.1 REST API: Snapshot Endpoint

- **Endpoint:** `GET /status`  
- **Purpose:** Provide a complete, current snapshot of:
  - Latest GPIO states that have ever changed
  - Latest Wi‑Fi status
  - Latest Bluetooth status
  - Latest system health metrics

- **Typical use cases:**
  - Simple scripts or tools that periodically poll and log the state.
  - Integrations where WebSocket streaming is unnecessary or impractical.
  - Quick health checks (e.g., from monitoring systems like cron jobs or external services).

- **Example:**

  ```bash
  curl http://<pi-address>:8000/status
  ```

  Response:

  ```json
  {
    "gpio": {
      "17": { "pin": 17, "value": 1, "label": "LED" },
      "27": { "pin": 27, "value": 0, "label": "Button" }
    },
    "wifi": {
      "connected": true,
      "ssid": "MyNetwork",
      "ip_address": "192.168.1.42",
      "signal_level_dbm": -55
    },
    "bluetooth": {
      "powered": true,
      "connected": false
    },
    "system": {
      "cpu_temp_c": 52.3,
      "cpu_percent": 23.5,
      "disk_used_percent": 41.2
    }
  }
  ```

### 5.2 WebSocket API: Real-Time Stream

- **Endpoint:** `WS /ws`  
- **Purpose:** Push real-time events to all connected clients as they occur.

- **Message structure:**

  ```json
  {
    "type": "<message_type>",  // "gpio", "wifi", "bluetooth", or "system"
    "data": { ... }            // monitor-specific payload
  }
  ```

- **Client behavior:**
  - Connect once, keep the connection open.
  - Handle incoming messages and update UI/logic in real time.

- **Example (JavaScript in a browser):**

  ```javascript
  const ws = new WebSocket('ws://<pi-address>:8000/ws');

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    console.log(`[${msg.type}]`, msg.data);
  };
  ```

- **Example (Python test client provided in repo):**
  - Script: ws_subscriber.py
  - Usage:

    ```bash
    # Pretty output
    python3 tests/ws_subscriber.py --host <pi-address>

    # Raw JSON
    python3 tests/ws_subscriber.py --host <pi-address> --raw
    ```

This dual interface (REST + WebSocket) is intentional: it supports both **simple scripts** and **interactive dashboards**.

---

## 6. Configuration and Customization

### 6.1 Configuration Model

Configuration is defined in a **single JSON file**, for example `rpi_debugger_settings.json`:

```json
{
  "gpio_enabled": true,
  "wifi_enabled": true,
  "bluetooth_enabled": true,
  "system_health_enabled": true,
  "gpio_poll_interval_s": 0.1,
  "network_poll_interval_s": 2.0,
  "system_poll_interval_s": 2.0,
  "gpio_labels": [
    { "pin": 17, "label": "LED" },
    { "pin": 27, "label": "Button" }
  ]
}
```

Configuration options include:

- **Enabled/disabled flags** for each subsystem:
  - `gpio_enabled`
  - `wifi_enabled`
  - `bluetooth_enabled`
  - `system_health_enabled`

- **Polling intervals** (in seconds):
  - `gpio_poll_interval_s`
  - `network_poll_interval_s`
  - `system_poll_interval_s`

- **GPIO pin labels:**
  - `gpio_labels`: mapping of pin numbers to human-readable labels.

### 6.2 Safe Defaults

If no configuration file is present:

- All monitoring features are **enabled**.
- Default polling intervals are used.
- A safe set of GPIO pins is monitored.
- No labels are defined, but monitoring still works.

On non‑Raspberry Pi machines:

- The code detects that GPIO support isn’t available.
- Instead of failing, it simply **skips GPIO monitoring**; network and system monitors still work.
- This makes development and experimentation possible on a laptop or desktop.

---

## 7. Internal Architecture and Implementation Approach

This section is more technical and can support a research‑style analysis of the design decisions.

### 7.1 Core Components

1. **FastAPI Application (app.py)**
   - Creates the FastAPI instance.
   - Initializes monitoring components based on loaded configuration.
   - Maintains a shared in-memory `latest_state` dictionary.
   - Exposes `/status` and `/ws` endpoints.
   - Manages WebSocket connections and broadcasting.

2. **Configuration Layer (config.py)**
   - Defines the `DebuggerSettings` model using Pydantic.
   - Handles JSON configuration loading, validation, and defaults.
   - Provides a convenience method (`gpio_label_map`) to map pin numbers to labels.

3. **GPIO Monitor (gpio_monitor.py)**
   - Encapsulates GPIO polling behavior.
   - Uses a background thread and `RPi.GPIO` library when available.
   - On each poll:
     - Reads each configured pin.
     - Detects changes by comparing to the last observed value.
     - Fires a callback when any pin changes.

4. **Network Monitor (network_monitor.py)**
   - Uses standard system commands (`iwconfig`, `hostname -I`, `bluetoothctl`) to infer:
     - Wi‑Fi SSID, IP address, and signal strength.
     - Bluetooth power and connection status.
   - Runs in a background thread and periodically calls callbacks with the latest status.

5. **System Monitor (system_monitor.py)**
   - Uses the `psutil` library to read:
     - CPU temperature (if exposed by the OS).
     - CPU usage percentage.
     - Disk usage on `/`.
   - Also runs in a background thread and periodically calls a callback with the computed `SystemHealth`.

### 7.2 Concurrency Model

- Each monitor (GPIO, Network, System) runs in its own Python **thread**.
- FastAPI runs on an **asyncio event loop** (as usual with ASGI servers).
- When a monitor has new data, it calls back with a plain Python object (e.g., `GPIOState`, `WiFiStatus`).
- The FastAPI app uses `asyncio.run_coroutine_threadsafe` to:
  - Safely schedule an asynchronous task (`push_update`) on the event loop.
  - That task updates `latest_state` and broadcasts a WebSocket message.

This separation keeps:

- Monitor logic simple and accessible (just loops and sleeps, easy for beginners to understand).
- Network I/O (HTTP/WebSocket) cleanly integrated in Async IO.

### 7.3 Connection Management

- A `ConnectionManager` class maintains a list of active WebSocket connections:
  - `connect`: accepts a new WebSocket and stores it.
  - `disconnect`: removes a WebSocket.
  - `broadcast`: sends a JSON message to all active connections, removing any that fail.

- The WebSocket endpoint:
  - Accepts a connection.
  - Keeps it alive by continuously reading from it (even though the client doesn’t need to send anything).
  - On disconnection, removes the client from the manager.

### 7.4 Error Handling and Robustness

- **GPIO unavailability:** If `RPi.GPIO` cannot be imported (e.g., not on a Pi), the GPIO monitor simply never starts. Other subsystems run normally.
- **System command failures:** Network monitor commands are executed with `subprocess.check_output`. Failures return empty strings, interpreted as “no data” rather than fatal errors.
- **Temperature sensor availability:** If `psutil.sensors_temperatures()` does not provide CPU readings, CPU temperature is set to `null`.

This design emphasizes **robust behavior over strict correctness** in heterogeneous environments: the server aims to keep running and provide as much information as it reliably can, rather than fail if any single piece of data is unavailable.

---

## 8. Example Use Cases

### 8.1 Classroom Demonstration

An instructor may:

1. Install `rpi-simple-debugger` on multiple Raspberry Pis in a lab.
2. Start the server on each Pi.
3. On a central PC, open a custom dashboard or simply run ws_subscriber.py for each device.
4. Students press buttons, connect sensors, or stress‑test CPU on their Pis.
5. The dashboard shows, in real time:
   - Pins toggling as buttons are pressed.
   - Wi‑Fi connectivity changes.
   - CPU temperature climbing under load.

This creates a **visual, interactive learning experience** connecting physical actions to digital measurements.

### 8.2 Rapid Prototyping of Hardware

A developer building a prototype:

1. Attaches multiple sensors and actuators to GPIO.
2. Starts `rpi-simple-debugger` on the Pi.
3. Connects a simple local web app to the `/ws` endpoint.
4. Uses this web UI to:
   - Verify that all sensor pins behave as expected before writing application logic.
   - Monitor system load and temperature while stress‑testing new code.
   - Keep an eye on Wi‑Fi signal while moving the physical device around.

This **decouples** low-level inspection from business logic and speeds up experimentation.

### 8.3 Integration into Larger Systems

Teams can integrate the debugger into their own FastAPI app:

- The debugger app can be created and **mounted under a sub‑path** (e.g., `/debugger`).
- The main application and debugger share the same server process.
- The team’s main app can:
  - Use the debugger’s `/status` programmatically.
  - Expose a custom UI that consumes debugger WebSocket messages.

This allows rpi-simple-debugger to become a **built‑in observability panel** for more complex systems.

---

## 9. Performance and Resource Considerations

- **CPU usage:**
  - Primarily driven by polling intervals.
  - GPIO polling at 0.1 seconds is responsive but can be increased if minimal latency is not required.
  - Network and system polls are much less frequent and relatively cheap.

- **Network usage:**
  - WebSocket messages are small JSON documents.
  - GPIO updates are only sent on state changes, not every poll cycle.
  - In typical scenarios, traffic is modest and suitable even for constrained networks.

- **Scalability:**
  - Designed for a single Raspberry Pi and a **moderate number of clients** (e.g., a few dashboards or tools).
  - For many concurrent clients, a reverse proxy such as nginx can front the application.
  - Nothing in the design prevents scaling up, but this isn’t a primary design goal; the focus is on simplicity and observability for single‑board environments.

---

## 10. Summary and Research Potential

**rpi-simple-debugger** can be seen as a case study in:

- Designing **beginner‑friendly observability tools** for embedded and edge devices.
- Combining:
  - Hardware‑level GPIO monitoring,
  - OS‑level health metrics,
  - Network connectivity insights,
  into a unified, minimal interface.

From a research or teaching perspective, it illustrates:

- A pattern for **decoupling monitoring from application logic** via APIs.
- A practical approach to **making implicit system state explicit and visualizable**, improving debugging efficiency.
- A model for **progressive complexity**: beginners can start by just running the server and using the provided test clients; advanced users can embed or extend the monitors in larger systems.
