"""CLI entry point for rpi-simple-debugger.

This allows running the debugger server from the command line:
    python -m rpi_simple_debugger
    python -m rpi_simple_debugger --host 0.0.0.0 --port 8000
    python -m rpi_simple_debugger --config /path/to/settings.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="rpi-simple-debugger",
        description="Beginner-friendly Raspberry Pi debugging server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m rpi_simple_debugger
  python -m rpi_simple_debugger --host 0.0.0.0 --port 8000
  python -m rpi_simple_debugger --config settings.json
  python -m rpi_simple_debugger --no-gpio --no-bluetooth

For more information, visit: https://github.com/Ponsriram/rpi-simple-debugger
""",
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host address to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON configuration file",
    )
    parser.add_argument(
        "--no-gpio",
        action="store_true",
        help="Disable GPIO monitoring",
    )
    parser.add_argument(
        "--no-wifi",
        action="store_true",
        help="Disable WiFi monitoring",
    )
    parser.add_argument(
        "--no-bluetooth",
        action="store_true",
        help="Disable Bluetooth monitoring",
    )
    parser.add_argument(
        "--no-system",
        action="store_true",
        help="Disable system health monitoring",
    )
    parser.add_argument(
        "--gpio-backend",
        choices=["auto", "rpi", "gpiozero", "mock"],
        default="auto",
        help="GPIO backend to use (default: auto)",
    )
    parser.add_argument(
        "--gpio-interval",
        type=float,
        default=0.1,
        help="GPIO polling interval in seconds (default: 0.1)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    args = parser.parse_args()

    if args.version:
        print("rpi-simple-debugger 0.1.0")
        return 0

    # Import here to avoid slow startup for --help/--version
    import uvicorn

    from .config import DebuggerSettings, load_settings

    # Load settings from file or create from CLI args
    if args.config:
        settings = load_settings(Path(args.config))
    else:
        settings = DebuggerSettings()

    # Apply CLI overrides
    if args.no_gpio:
        settings.gpio_enabled = False
    if args.no_wifi:
        settings.wifi_enabled = False
    if args.no_bluetooth:
        settings.bluetooth_enabled = False
    if args.no_system:
        settings.system_health_enabled = False
    if args.gpio_backend != "auto":
        settings.gpio_backend = args.gpio_backend
    if args.gpio_interval != 0.1:
        settings.gpio_poll_interval_s = args.gpio_interval

    # Store settings in environment for the app factory
    import json
    import os

    os.environ["_RPI_DEBUGGER_SETTINGS"] = settings.model_dump_json()

    print(f"🔧 Starting rpi-simple-debugger on http://{args.host}:{args.port}")
    print(f"   GPIO: {'enabled' if settings.gpio_enabled else 'disabled'}")
    print(f"   WiFi: {'enabled' if settings.wifi_enabled else 'disabled'}")
    print(f"   Bluetooth: {'enabled' if settings.bluetooth_enabled else 'disabled'}")
    print(f"   System Health: {'enabled' if settings.system_health_enabled else 'disabled'}")
    print()

    # Run uvicorn
    uvicorn.run(
        "rpi_simple_debugger.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
