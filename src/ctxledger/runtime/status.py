from __future__ import annotations

from typing import Any

from .introspection import collect_runtime_introspection
from .serializers import serialize_runtime_introspection_collection
from .types import HealthStatus, ReadinessStatus


def build_health_status(server: Any) -> HealthStatus:
    runtime_introspection = collect_runtime_introspection(
        getattr(server, "runtime", None)
    )
    return HealthStatus(
        ok=True,
        status="ok",
        details={
            "service": server.settings.app_name,
            "version": server.settings.app_version,
            "started": server._started,
            "workflow_service_initialized": server.workflow_service is not None,
            "runtime": serialize_runtime_introspection_collection(
                runtime_introspection
            ),
        },
    )


def build_readiness_status(server: Any) -> ReadinessStatus:
    runtime_introspection = collect_runtime_introspection(
        getattr(server, "runtime", None)
    )
    details: dict[str, Any] = {
        "service": server.settings.app_name,
        "version": server.settings.app_version,
        "started": server._started,
        "database_configured": bool(server.settings.database.url),
        "http_enabled": server.settings.http.enabled,
        "stdio_enabled": server.settings.stdio.enabled,
        "workflow_service_initialized": server.workflow_service is not None,
        "runtime": serialize_runtime_introspection_collection(runtime_introspection),
    }

    if not server._started:
        return ReadinessStatus(
            ready=False,
            status="not_started",
            details=details,
        )

    try:
        server.db_health_checker.ping()
        details["database_reachable"] = True
    except Exception as exc:
        details["database_reachable"] = False
        details["error"] = str(exc)
        return ReadinessStatus(
            ready=False,
            status="database_unavailable",
            details=details,
        )

    try:
        schema_ready = server.db_health_checker.schema_ready()
        details["schema_ready"] = schema_ready
    except Exception as exc:
        details["schema_ready"] = False
        details["error"] = str(exc)
        return ReadinessStatus(
            ready=False,
            status="schema_check_failed",
            details=details,
        )

    if not details["schema_ready"]:
        return ReadinessStatus(
            ready=False,
            status="schema_not_ready",
            details=details,
        )

    return ReadinessStatus(
        ready=True,
        status="ready",
        details=details,
    )


__all__ = [
    "build_health_status",
    "build_readiness_status",
]
