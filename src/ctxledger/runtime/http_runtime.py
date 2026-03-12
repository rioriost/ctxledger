from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..server import CtxLedgerServer, HttpRuntimeAdapter
    from .introspection import RuntimeIntrospection
    from .orchestration import ServerRuntime


def build_http_runtime_adapter(server: CtxLedgerServer) -> HttpRuntimeAdapter:
    from ..server import (
        HttpRuntimeAdapter,
        build_closed_projection_failures_http_handler,
        build_mcp_http_handler,
        build_projection_failures_ignore_http_handler,
        build_projection_failures_resolve_http_handler,
        build_runtime_introspection_http_handler,
        build_runtime_routes_http_handler,
        build_runtime_tools_http_handler,
        build_workflow_resume_http_handler,
    )
    from .orchestration import build_stdio_runtime_adapter

    runtime = HttpRuntimeAdapter(server.settings)
    mcp_runtime = build_stdio_runtime_adapter(server)
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


__all__ = [
    "build_http_runtime_adapter",
]
