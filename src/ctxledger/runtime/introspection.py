from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .protocols import ServerRuntime

if TYPE_CHECKING:
    from ..mcp.stdio import StdioRuntimeAdapter
    from ..server import CompositeRuntimeAdapter, HttpRuntimeAdapter


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


from .serializers import (
    serialize_runtime_introspection,
    serialize_runtime_introspection_collection,
)

__all__ = [
    "RuntimeIntrospection",
    "collect_runtime_introspection",
    "serialize_runtime_introspection",
    "serialize_runtime_introspection_collection",
]
