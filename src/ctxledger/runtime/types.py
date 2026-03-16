from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class HealthStatus:
    ok: bool
    status: str
    details: dict[str, Any]


@dataclass(slots=True)
class ReadinessStatus:
    ready: bool
    status: str
    details: dict[str, Any]


@dataclass(slots=True)
class WorkflowResumeResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass(slots=True)
class RuntimeIntrospectionResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass(slots=True)
class McpResourceResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass(slots=True)
class McpToolResponse:
    payload: dict[str, Any]


@dataclass(slots=True)
class RuntimeDispatchResult:
    transport: str
    target: str
    status: str
    response: WorkflowResumeResponse | McpToolResponse | McpResourceResponse


@dataclass(slots=True)
class McpHttpResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


__all__ = [
    "HealthStatus",
    "ReadinessStatus",
    "WorkflowResumeResponse",
    "RuntimeIntrospectionResponse",
    "McpResourceResponse",
    "McpToolResponse",
    "RuntimeDispatchResult",
    "McpHttpResponse",
]
