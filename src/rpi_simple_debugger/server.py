from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import uvicorn

from .app import create_app
from .config import DebuggerSettings, load_settings
from .engine import DebuggerEngine


_engine: DebuggerEngine | None = None


def get_engine() -> DebuggerEngine | None:
    return _engine


class DebuggerHandle:
    def __init__(self, server: uvicorn.Server, thread: threading.Thread) -> None:
        self._server = server
        self._thread = thread

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)


def start_debugger_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    settings_path: Optional[str] = None,
) -> DebuggerHandle:
    """Start the debugger HTTP/WebSocket server in a background thread.

    This is the primary entry point for users who simply want to spin up the
    debugger alongside their own application code.
    """

    global _engine

    settings: DebuggerSettings
    if settings_path is not None:
        settings = load_settings(Path(settings_path))
    else:
        settings = load_settings()

    app = create_app(settings=settings)
    _engine = app.state.engine

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    def _run() -> None:
        server.run()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return DebuggerHandle(server=server, thread=thread)
