from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ..mcp.stdio import StdioRuntimeAdapter
    from ..server import CompositeRuntimeAdapter, HttpRuntimeAdapter


class ServerRuntime(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


@dataclass(slots=True)
class RuntimeIntrospection:
    transport: str
    routes: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()


def collect_runtime_introspection(
    runtime: ServerRuntime | None,
) -> tuple[RuntimeIntrospection, ...]:
    if runtime is None:
        return ()

    from ..mcp.stdio import StdioRuntimeAdapter
    from ..server import CompositeRuntimeAdapter, HttpRuntimeAdapter

    if isinstance(runtime, CompositeRuntimeAdapter):
        collected: list[RuntimeIntrospection] = []
        for nested_runtime in runtime._runtimes:
            collected.extend(collect_runtime_introspection(nested_runtime))
        return tuple(collected)

    if isinstance(runtime, HttpRuntimeAdapter):
        return (runtime.introspect(),)

    if isinstance(runtime, StdioRuntimeAdapter):
        introspection = runtime.introspect()
        return (
            RuntimeIntrospection(
                transport=introspection.transport,
                routes=tuple(getattr(introspection, "routes", ())),
                tools=tuple(introspection.tools),
                resources=tuple(introspection.resources),
            ),
        )

    return ()


def serialize_runtime_introspection(
    introspection: RuntimeIntrospection,
) -> dict[str, Any]:
    return {
        "transport": introspection.transport,
        "routes": list(introspection.routes),
        "tools": list(introspection.tools),
        "resources": list(introspection.resources),
    }


def serialize_runtime_introspection_collection(
    introspections: tuple[RuntimeIntrospection, ...],
) -> list[dict[str, Any]]:
    return [
        serialize_runtime_introspection(introspection)
        for introspection in introspections
    ]


__all__ = [
    "RuntimeIntrospection",
    "collect_runtime_introspection",
    "serialize_runtime_introspection",
    "serialize_runtime_introspection_collection",
]
