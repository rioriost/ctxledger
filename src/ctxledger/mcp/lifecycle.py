from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

MCP_PROTOCOL_VERSION = "2024-11-05"


@dataclass(slots=True, frozen=True)
class McpServerInfo:
    name: str
    version: str


@dataclass(slots=True, frozen=True)
class McpLifecycleCapabilities:
    tools: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> dict[str, Any]:
        return {
            "tools": dict(self.tools),
            "resources": dict(self.resources),
        }


@dataclass(slots=True, frozen=True)
class McpInitializeResult:
    protocol_version: str
    server_info: McpServerInfo
    capabilities: McpLifecycleCapabilities

    def serialize(self) -> dict[str, Any]:
        return {
            "protocolVersion": self.protocol_version,
            "serverInfo": {
                "name": self.server_info.name,
                "version": self.server_info.version,
            },
            "capabilities": self.capabilities.serialize(),
        }


@dataclass(slots=True, frozen=True)
class McpJsonRpcSuccessResponse:
    request_id: Any
    result: dict[str, Any]

    def serialize(self) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "result": self.result,
        }


@dataclass(slots=True, frozen=True)
class McpJsonRpcError:
    code: int
    message: str
    data: dict[str, Any] | None = None

    def serialize(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.data:
            payload["data"] = dict(self.data)
        return payload


@dataclass(slots=True, frozen=True)
class McpJsonRpcErrorResponse:
    request_id: Any
    error: McpJsonRpcError

    def serialize(self) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "error": self.error.serialize(),
        }


@dataclass(slots=True, frozen=True)
class McpLifecycleState:
    initialized: bool = False
    negotiated_protocol_version: str | None = None


class McpLifecycleRuntime(Protocol):
    settings: Any

    def registered_tools(self) -> tuple[str, ...]: ...
    def registered_resources(self) -> tuple[str, ...]: ...


def build_initialize_result(runtime: McpLifecycleRuntime) -> McpInitializeResult:
    return McpInitializeResult(
        protocol_version=MCP_PROTOCOL_VERSION,
        server_info=McpServerInfo(
            name="ctxledger",
            version=runtime.settings.app_version,
        ),
        capabilities=McpLifecycleCapabilities(
            tools={},
            resources={},
        ),
    )


def handle_initialize_request(
    runtime: McpLifecycleRuntime,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = params
    return build_initialize_result(runtime).serialize()


def handle_initialized_notification(
    state: McpLifecycleState,
    params: dict[str, Any] | None = None,
) -> None:
    _ = params
    object.__setattr__(state, "initialized", True)


def handle_ping_request() -> dict[str, Any]:
    return {}


def handle_shutdown_request() -> None:
    return None


def is_initialized_notification(method: str | None) -> bool:
    return method in {"initialized", "notifications/initialized"}


def dispatch_lifecycle_method(
    runtime: McpLifecycleRuntime,
    state: McpLifecycleState,
    method: str | None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if method == "initialize":
        result = handle_initialize_request(runtime, params)
        object.__setattr__(
            state, "negotiated_protocol_version", result["protocolVersion"]
        )
        return result
    if is_initialized_notification(method):
        handle_initialized_notification(state, params)
        return None
    if method == "ping":
        return handle_ping_request()
    if method == "shutdown":
        return handle_shutdown_request()
    return None


def build_jsonrpc_success_response(
    request_id: Any,
    result: dict[str, Any],
) -> dict[str, Any]:
    return McpJsonRpcSuccessResponse(
        request_id=request_id,
        result=result,
    ).serialize()


def build_jsonrpc_error_response(
    request_id: Any,
    *,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return McpJsonRpcErrorResponse(
        request_id=request_id,
        error=McpJsonRpcError(
            code=code,
            message=message,
            data=data,
        ),
    ).serialize()


__all__ = [
    "MCP_PROTOCOL_VERSION",
    "McpInitializeResult",
    "McpJsonRpcError",
    "McpJsonRpcErrorResponse",
    "McpJsonRpcSuccessResponse",
    "McpLifecycleCapabilities",
    "McpLifecycleRuntime",
    "McpLifecycleState",
    "McpServerInfo",
    "build_initialize_result",
    "build_jsonrpc_error_response",
    "build_jsonrpc_success_response",
    "dispatch_lifecycle_method",
    "handle_initialize_request",
    "handle_initialized_notification",
    "handle_ping_request",
    "handle_shutdown_request",
    "is_initialized_notification",
]
