from __future__ import annotations

import logging
import signal
import sys
from types import FrameType
from typing import Protocol

from ..config import AppSettings, TransportMode, get_settings
from ..mcp.resource_handlers import (
    build_workflow_detail_resource_handler,
    build_workspace_resume_resource_handler,
)
from ..mcp.stdio import (
    StdioRuntimeAdapter,
    build_stdio_runtime,
    run_stdio_runtime_if_present,
)
from ..mcp.stdio import (
    build_stdio_runtime_adapter as build_extracted_stdio_runtime_adapter,
)
from ..mcp.tool_handlers import (
    build_memory_get_context_tool_handler,
    build_memory_remember_episode_tool_handler,
    build_memory_search_tool_handler,
    build_projection_failures_ignore_tool_handler,
    build_projection_failures_resolve_tool_handler,
    build_resume_workflow_tool_handler,
    build_workflow_checkpoint_tool_handler,
    build_workflow_complete_tool_handler,
    build_workflow_start_tool_handler,
    build_workspace_register_tool_handler,
)
from ..mcp.tool_schemas import (
    MEMORY_GET_CONTEXT_TOOL_SCHEMA,
    MEMORY_REMEMBER_EPISODE_TOOL_SCHEMA,
    MEMORY_SEARCH_TOOL_SCHEMA,
    PROJECTION_FAILURES_IGNORE_TOOL_SCHEMA,
    PROJECTION_FAILURES_RESOLVE_TOOL_SCHEMA,
    WORKFLOW_CHECKPOINT_TOOL_SCHEMA,
    WORKFLOW_COMPLETE_TOOL_SCHEMA,
    WORKFLOW_RESUME_TOOL_SCHEMA,
    WORKFLOW_START_TOOL_SCHEMA,
    WORKSPACE_REGISTER_TOOL_SCHEMA,
)
from ..memory.service import MemoryService
from ..runtime.introspection import (
    RuntimeIntrospection,
    collect_runtime_introspection,
    serialize_runtime_introspection_collection,
)

logger = logging.getLogger(__name__)


class ServerRuntime(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


def build_stdio_runtime_adapter(server: CtxLedgerServer) -> StdioRuntimeAdapter:
    memory_service = MemoryService()
    return build_extracted_stdio_runtime_adapter(
        server,
        memory_service=memory_service,
        workflow_resume_tool_handler_factory=lambda current_server: (
            build_resume_workflow_tool_handler(current_server),
            WORKFLOW_RESUME_TOOL_SCHEMA,
        ),
        workspace_register_tool_handler_factory=lambda current_server: (
            build_workspace_register_tool_handler(current_server),
            WORKSPACE_REGISTER_TOOL_SCHEMA,
        ),
        workflow_start_tool_handler_factory=lambda current_server: (
            build_workflow_start_tool_handler(current_server),
            WORKFLOW_START_TOOL_SCHEMA,
        ),
        workflow_checkpoint_tool_handler_factory=lambda current_server: (
            build_workflow_checkpoint_tool_handler(current_server),
            WORKFLOW_CHECKPOINT_TOOL_SCHEMA,
        ),
        workflow_complete_tool_handler_factory=lambda current_server: (
            build_workflow_complete_tool_handler(current_server),
            WORKFLOW_COMPLETE_TOOL_SCHEMA,
        ),
        projection_failures_ignore_tool_handler_factory=lambda current_server: (
            build_projection_failures_ignore_tool_handler(current_server),
            PROJECTION_FAILURES_IGNORE_TOOL_SCHEMA,
        ),
        projection_failures_resolve_tool_handler_factory=lambda current_server: (
            build_projection_failures_resolve_tool_handler(current_server),
            PROJECTION_FAILURES_RESOLVE_TOOL_SCHEMA,
        ),
        memory_remember_episode_tool_handler_factory=lambda current_memory_service: (
            build_memory_remember_episode_tool_handler(current_memory_service),
            MEMORY_REMEMBER_EPISODE_TOOL_SCHEMA,
        ),
        memory_search_tool_handler_factory=lambda current_memory_service: (
            build_memory_search_tool_handler(current_memory_service),
            MEMORY_SEARCH_TOOL_SCHEMA,
        ),
        memory_get_context_tool_handler_factory=lambda current_memory_service: (
            build_memory_get_context_tool_handler(current_memory_service),
            MEMORY_GET_CONTEXT_TOOL_SCHEMA,
        ),
        workspace_resume_resource_handler_factory=build_workspace_resume_resource_handler,
        workflow_detail_resource_handler_factory=build_workflow_detail_resource_handler,
    )


def create_runtime(
    settings: AppSettings,
    server,
    *,
    http_runtime_builder,
) -> ServerRuntime | None:
    runtimes: list[ServerRuntime] = []

    if settings.http.enabled:
        if server is not None:
            http_runtime = http_runtime_builder(server)
        else:
            from ..server import HttpRuntimeAdapter

            http_runtime = HttpRuntimeAdapter(settings)
        runtimes.append(http_runtime)

    if settings.stdio.enabled:
        stdio_runtime = build_stdio_runtime(
            settings,
            server=server,
            runtime_builder=build_stdio_runtime_adapter,
        )
        runtimes.append(stdio_runtime)

    if not runtimes:
        return None

    if len(runtimes) == 1:
        return runtimes[0]

    from ..server import CompositeRuntimeAdapter

    return CompositeRuntimeAdapter(runtimes)


def apply_overrides(
    settings: AppSettings,
    *,
    transport: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> AppSettings:
    if transport is None and host is None and port is None:
        return settings

    transport_mode = settings.transport
    http_enabled = settings.http.enabled
    stdio_enabled = settings.stdio.enabled

    if transport is not None:
        transport_mode = TransportMode(transport)
        http_enabled = transport_mode in (TransportMode.HTTP, TransportMode.BOTH)
        stdio_enabled = transport_mode in (TransportMode.STDIO, TransportMode.BOTH)

    http_settings = type(settings.http)(
        enabled=http_enabled,
        host=host if host is not None else settings.http.host,
        port=port if port is not None else settings.http.port,
        path=settings.http.path,
    )

    stdio_settings = type(settings.stdio)(
        enabled=stdio_enabled,
    )

    overridden = type(settings)(
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        transport=transport_mode,
        database=settings.database,
        http=http_settings,
        stdio=stdio_settings,
        auth=settings.auth,
        debug=settings.debug,
        projection=settings.projection,
        logging=settings.logging,
    )
    overridden.validate()
    return overridden


def install_signal_handlers(server: CtxLedgerServer) -> None:
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


def print_runtime_summary(server: CtxLedgerServer) -> None:
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

    if server.settings.http.enabled:
        print(f"mcp_endpoint={server.settings.http.mcp_url}", file=sys.stderr)
    if server.settings.stdio.enabled:
        print("stdio_transport=enabled", file=sys.stderr)


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
        from ..server import ServerBootstrapError, create_server

        server = create_server(settings)
        install_signal_handlers(server)
        server.startup()
        print_runtime_summary(server)

        if settings.stdio.enabled and run_stdio_runtime_if_present(server.runtime):
            return 0

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
    "build_stdio_runtime_adapter",
    "create_runtime",
    "apply_overrides",
    "install_signal_handlers",
    "print_runtime_summary",
    "run_server",
]
