from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True, frozen=True)
class StreamableHttpRequest:
    path: str
    body: str | None = None
    headers: dict[str, str] | None = None
    query: dict[str, list[str]] | None = None


@dataclass(slots=True, frozen=True)
class StreamableHttpResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass(slots=True)
class StreamableHttpEndpoint:
    """
    Thin MCP Streamable HTTP scaffold.

    This is intentionally minimal: it validates the configured MCP endpoint path,
    requires a JSON-RPC request body, delegates request handling to the supplied
    RPC handler, and normalizes transport-level error responses.
    """

    mcp_path: str
    rpc_handler: Callable[[dict[str, Any]], dict[str, Any] | None]
    auth_validator: Callable[[str], StreamableHttpResponse | None] | None = None

    def handle(self, request: StreamableHttpRequest) -> StreamableHttpResponse:
        if self.auth_validator is not None:
            auth_error = self.auth_validator(request.path)
            if auth_error is not None:
                return auth_error

        if not _path_matches(request.path, self.mcp_path):
            return build_streamable_http_not_found_response(self.mcp_path)

        if request.body is None or not request.body.strip():
            return build_streamable_http_invalid_request_response(
                "HTTP MCP endpoint requires a JSON-RPC request body"
            )

        try:
            parsed = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return build_streamable_http_invalid_request_response(
                f"request body must be valid JSON: {exc.msg}"
            )

        if not isinstance(parsed, dict):
            return build_streamable_http_invalid_request_response(
                "request body must be a JSON object"
            )

        req_id = parsed.get("id")
        try:
            response = self.rpc_handler(parsed)
        except SystemExit:
            raise
        except Exception as exc:
            return build_streamable_http_rpc_error_response(
                request_id=req_id,
                code=-32000,
                message=str(exc),
            )

        if response is None:
            return StreamableHttpResponse(
                status_code=202,
                payload={},
                headers=default_streamable_http_headers(),
            )

        return StreamableHttpResponse(
            status_code=200,
            payload=response,
            headers=default_streamable_http_headers(),
        )


class StreamableHttpRuntime(Protocol):
    settings: Any

    def handle_rpc_request(self, request: dict[str, Any]) -> dict[str, Any] | None: ...


def build_streamable_http_endpoint(
    runtime: StreamableHttpRuntime,
    *,
    mcp_path: str,
    auth_validator: Callable[[str], StreamableHttpResponse | None] | None = None,
) -> StreamableHttpEndpoint:
    return StreamableHttpEndpoint(
        mcp_path=mcp_path,
        rpc_handler=runtime.handle_rpc_request,
        auth_validator=auth_validator,
    )


def default_streamable_http_headers() -> dict[str, str]:
    return {"content-type": "application/json"}


def build_streamable_http_not_found_response(
    mcp_path: str,
) -> StreamableHttpResponse:
    return StreamableHttpResponse(
        status_code=404,
        payload={
            "error": {
                "code": "not_found",
                "message": f"MCP endpoint requires {mcp_path}",
            }
        },
        headers=default_streamable_http_headers(),
    )


def build_streamable_http_invalid_request_response(
    message: str,
) -> StreamableHttpResponse:
    return StreamableHttpResponse(
        status_code=400,
        payload={
            "error": {
                "code": "invalid_request",
                "message": message,
            }
        },
        headers=default_streamable_http_headers(),
    )


def build_streamable_http_rpc_error_response(
    *,
    request_id: Any,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> StreamableHttpResponse:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if data:
        error["data"] = dict(data)

    return StreamableHttpResponse(
        status_code=400,
        payload={
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error,
        },
        headers=default_streamable_http_headers(),
    )


def _path_matches(actual_path: str, expected_path: str) -> bool:
    normalized_path = actual_path.strip()
    path_without_query = normalized_path.split("?", 1)[0].strip("/")

    normalized_expected = expected_path.strip()
    expected_without_query = normalized_expected.split("?", 1)[0].strip("/")

    return path_without_query == expected_without_query


__all__ = [
    "StreamableHttpEndpoint",
    "StreamableHttpRequest",
    "StreamableHttpResponse",
    "StreamableHttpRuntime",
    "build_streamable_http_endpoint",
    "build_streamable_http_invalid_request_response",
    "build_streamable_http_not_found_response",
    "build_streamable_http_rpc_error_response",
    "default_streamable_http_headers",
]
