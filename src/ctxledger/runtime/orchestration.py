from __future__ import annotations

import logging
import signal
import sys
from types import FrameType
from typing import Protocol

from ..config import AppSettings, get_settings
from ..runtime.database_health import ServerBootstrapError
from ..runtime.introspection import collect_runtime_introspection
from ..runtime.serializers import serialize_runtime_introspection_collection

logger = logging.getLogger(__name__)


class ServerRuntime(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


def create_runtime(
    settings: AppSettings,
    server,
    *,
    http_runtime_builder,
) -> ServerRuntime | None:
    return http_runtime_builder(server)


def apply_overrides(
    settings: AppSettings,
    *,
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> AppSettings:
    if transport is not None and transport.lower() != "http":
        raise ValueError("transport override must be 'http'")

    if transport is None and host is None and port is None:
        return settings

    http_settings = type(settings.http)(
        host=host if host is not None else settings.http.host,
        port=port if port is not None else settings.http.port,
        path=settings.http.path,
    )

    overridden = type(settings)(
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        database=settings.database,
        http=http_settings,
        debug=settings.debug,
        logging=settings.logging,
        embedding=settings.embedding,
    )
    overridden.validate()
    return overridden


def install_signal_handlers(server) -> None:
    def _handle_signal(signum: int, frame: FrameType | None) -> None:
        logger.info(
            "Received shutdown signal",
            extra={"signal": signum},
        )
        server.shutdown()
        raise SystemExit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except ValueError:
            logger.debug("Signal handler registration skipped", extra={"signal": sig})


def print_runtime_summary(server) -> None:
    readiness = server.readiness()
    health = server.health()
    runtime_introspection = serialize_runtime_introspection_collection(
        collect_runtime_introspection(server.runtime)
    )

    print(
        f"{server.settings.app_name} {server.settings.app_version} started",
        file=sys.stderr,
    )
    print(f"health={health.status}", file=sys.stderr)
    print(f"readiness={readiness.status}", file=sys.stderr)
    print(f"runtime={runtime_introspection}", file=sys.stderr)

    print(f"mcp_endpoint={server.settings.http.mcp_url}", file=sys.stderr)


def run_server(
    *,
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> int:
    try:
        settings = get_settings()
        settings = apply_overrides(
            settings,
            transport=transport,
            host=host,
            port=port,
        )
        from ..server import create_server

        server = create_server(settings)
        install_signal_handlers(server)
        server.startup()
        print_runtime_summary(server)
        return 0
    except ServerBootstrapError as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unhandled server error: {exc}", file=sys.stderr)
        return 1


__all__ = [
    "ServerRuntime",
    "collect_runtime_introspection",
    "create_runtime",
    "apply_overrides",
    "install_signal_handlers",
    "print_runtime_summary",
    "run_server",
]
