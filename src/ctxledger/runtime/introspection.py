from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .protocols import ServerRuntime


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

    nested_runtimes = getattr(runtime, "_runtimes", None)
    if isinstance(nested_runtimes, list):
        collected: list[RuntimeIntrospection] = []
        for nested_runtime in nested_runtimes:
            collected.extend(collect_runtime_introspection(nested_runtime))
        return tuple(collected)

    introspect = getattr(runtime, "introspect", None)
    if callable(introspect):
        introspection = introspect()
        if _is_runtime_introspection_like(introspection):
            return (
                RuntimeIntrospection(
                    transport=str(introspection.transport),
                    routes=tuple(getattr(introspection, "routes", ())),
                    tools=tuple(getattr(introspection, "tools", ())),
                    resources=tuple(getattr(introspection, "resources", ())),
                ),
            )

    return ()


def _is_runtime_introspection_like(value: Any) -> bool:
    return (
        hasattr(value, "transport")
        and hasattr(value, "routes")
        and hasattr(value, "tools")
        and hasattr(value, "resources")
    )


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
