from __future__ import annotations

from typing import TYPE_CHECKING

from .http_handlers import (
    build_closed_projection_failures_http_handler,
    build_mcp_http_handler,
    build_projection_failures_ignore_http_handler,
    build_projection_failures_resolve_http_handler,
    build_runtime_introspection_http_handler,
    build_runtime_routes_http_handler,
    build_runtime_tools_http_handler,
    build_workflow_resume_http_handler,
)
from .protocols import HttpHandlerFactoryServer

if TYPE_CHECKING:
    from .protocols import HttpRuntimeAdapterProtocol


def register_http_runtime_handlers(
    runtime: HttpRuntimeAdapterProtocol,
    server: HttpHandlerFactoryServer,
) -> HttpRuntimeAdapterProtocol:
    mcp_runtime = runtime
    debug_settings = getattr(server.settings, "debug", None)
    debug_http_endpoints_enabled = (
        True if debug_settings is None else getattr(debug_settings, "enabled", True)
    )

    runtime.register_handler(
        "mcp_rpc",
        build_mcp_http_handler(mcp_runtime, server),
    )

    if debug_http_endpoints_enabled:
        runtime.register_handler(
            "runtime_introspection",
            build_runtime_introspection_http_handler(server),
        )
        runtime.register_handler(
            "runtime_routes",
            build_runtime_routes_http_handler(server),
        )
        runtime.register_handler(
            "runtime_tools",
            build_runtime_tools_http_handler(server),
        )

    runtime.register_handler(
        "workflow_resume",
        build_workflow_resume_http_handler(server),
    )
    runtime.register_handler(
        "workflow_closed_projection_failures",
        build_closed_projection_failures_http_handler(server),
    )
    runtime.register_handler(
        "projection_failures_ignore",
        build_projection_failures_ignore_http_handler(server),
    )
    runtime.register_handler(
        "projection_failures_resolve",
        build_projection_failures_resolve_http_handler(server),
    )
    return runtime


def build_http_runtime_adapter(
    server: HttpHandlerFactoryServer,
) -> HttpRuntimeAdapterProtocol:
    from ..server import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(server.settings)
    return register_http_runtime_handlers(runtime, server)


__all__ = [
    "build_http_runtime_adapter",
    "register_http_runtime_handlers",
]
