from __future__ import annotations

import json
from dataclasses import dataclass

from ctxledger.config import (
    AppSettings,
    AuthSettings,
    DatabaseSettings,
    DebugSettings,
    HttpSettings,
    LoggingSettings,
    LogLevel,
    ProjectionSettings,
)
from ctxledger.mcp.lifecycle import (
    MCP_PROTOCOL_VERSION,
    McpLifecycleState,
    build_initialize_result,
    build_jsonrpc_error_response,
    build_jsonrpc_success_response,
    dispatch_lifecycle_method,
)
from ctxledger.mcp.rpc import handle_mcp_rpc_request
from ctxledger.mcp.streamable_http import (
    StreamableHttpRequest,
    StreamableHttpResponse,
    build_streamable_http_endpoint,
    build_streamable_http_invalid_request_response,
    build_streamable_http_not_found_response,
    build_streamable_http_rpc_error_response,
)
from ctxledger.runtime.types import McpResourceResponse, McpToolResponse


def make_settings(
    *,
    database_url: str = "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger",
    host: str = "127.0.0.1",
    port: int = 8080,
    auth_bearer_token: str | None = None,
    require_auth: bool = False,
) -> AppSettings:
    return AppSettings(
        app_name="ctxledger",
        app_version="0.1.0",
        environment="test",
        database=DatabaseSettings(
            url=database_url,
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
        ),
        http=HttpSettings(
            host=host,
            port=port,
            path="/mcp",
        ),
        auth=AuthSettings(
            bearer_token=auth_bearer_token,
            require_auth=require_auth,
        ),
        debug=DebugSettings(
            enabled=True,
        ),
        projection=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
        logging=LoggingSettings(
            level=LogLevel.INFO,
            structured=True,
        ),
    )


def test_build_initialize_result_returns_expected_payload() -> None:
    settings = make_settings()

    class FakeLifecycleRuntime:
        def __init__(self, settings: AppSettings) -> None:
            self.settings = settings

        def registered_tools(self) -> tuple[str, ...]:
            return ()

        def registered_resources(self) -> tuple[str, ...]:
            return ()

    runtime = FakeLifecycleRuntime(settings)

    result = build_initialize_result(runtime).serialize()

    assert result == {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "serverInfo": {
            "name": "ctxledger",
            "version": settings.app_version,
        },
        "capabilities": {
            "tools": {},
            "resources": {},
        },
    }


def test_dispatch_lifecycle_method_records_initialize_protocol_version() -> None:
    settings = make_settings()

    class FakeLifecycleRuntime:
        def __init__(self, settings: AppSettings) -> None:
            self.settings = settings

        def registered_tools(self) -> tuple[str, ...]:
            return ()

        def registered_resources(self) -> tuple[str, ...]:
            return ()

    runtime = FakeLifecycleRuntime(settings)
    state = McpLifecycleState()

    result = dispatch_lifecycle_method(runtime, state, "initialize", {})

    assert result == {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "serverInfo": {
            "name": "ctxledger",
            "version": settings.app_version,
        },
        "capabilities": {
            "tools": {},
            "resources": {},
        },
    }
    assert state.negotiated_protocol_version == MCP_PROTOCOL_VERSION
    assert state.initialized is False


def test_dispatch_lifecycle_method_marks_initialized_for_notification_method() -> None:
    settings = make_settings()

    class FakeLifecycleRuntime:
        def __init__(self, settings: AppSettings) -> None:
            self.settings = settings

        def registered_tools(self) -> tuple[str, ...]:
            return ()

        def registered_resources(self) -> tuple[str, ...]:
            return ()

    runtime = FakeLifecycleRuntime(settings)
    state = McpLifecycleState()

    result = dispatch_lifecycle_method(
        runtime,
        state,
        "notifications/initialized",
        {},
    )

    assert result is None
    assert state.initialized is True


def test_build_jsonrpc_success_response_returns_expected_envelope() -> None:
    response = build_jsonrpc_success_response(
        7,
        {"ok": True},
    )

    assert response == {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {"ok": True},
    }


def test_build_jsonrpc_error_response_returns_expected_envelope() -> None:
    response = build_jsonrpc_error_response(
        9,
        code=-32001,
        message="boom",
        data={"field": "value"},
    )

    assert response == {
        "jsonrpc": "2.0",
        "id": 9,
        "error": {
            "code": -32001,
            "message": "boom",
            "data": {"field": "value"},
        },
    }


def test_build_streamable_http_not_found_response_returns_expected_payload() -> None:
    response = build_streamable_http_not_found_response("/mcp")

    assert response == StreamableHttpResponse(
        status_code=404,
        payload={
            "error": {
                "code": "not_found",
                "message": "MCP endpoint requires /mcp",
            }
        },
        headers={"content-type": "application/json"},
    )


def test_build_streamable_http_invalid_request_response_returns_expected_payload() -> (
    None
):
    response = build_streamable_http_invalid_request_response("bad request")

    assert response == StreamableHttpResponse(
        status_code=400,
        payload={
            "error": {
                "code": "invalid_request",
                "message": "bad request",
            }
        },
        headers={"content-type": "application/json"},
    )


def test_build_streamable_http_rpc_error_response_returns_expected_payload() -> None:
    response = build_streamable_http_rpc_error_response(
        request_id=11,
        code=-32000,
        message="rpc failed",
        data={"reason": "test"},
    )

    assert response == StreamableHttpResponse(
        status_code=400,
        payload={
            "jsonrpc": "2.0",
            "id": 11,
            "error": {
                "code": -32000,
                "message": "rpc failed",
                "data": {"reason": "test"},
            },
        },
        headers={"content-type": "application/json"},
    )


def test_streamable_http_endpoint_returns_202_for_notification() -> None:
    class FakeStreamableRuntime:
        settings = None

        def handle_rpc_request(self, request: dict[str, object]) -> None:
            assert request["method"] == "notifications/initialized"
            return None

    endpoint = build_streamable_http_endpoint(
        FakeStreamableRuntime(),
        mcp_path="/mcp",
    )

    response = endpoint.handle(
        StreamableHttpRequest(
            path="/mcp",
            body='{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}',
        )
    )

    assert response == StreamableHttpResponse(
        status_code=202,
        payload={},
        headers={"content-type": "application/json"},
    )


def test_streamable_http_endpoint_returns_rpc_error_payload_on_exception() -> None:
    class FakeStreamableRuntime:
        settings = None

        def handle_rpc_request(self, request: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("rpc exploded")

    endpoint = build_streamable_http_endpoint(
        FakeStreamableRuntime(),
        mcp_path="/mcp",
    )

    response = endpoint.handle(
        StreamableHttpRequest(
            path="/mcp",
            body='{"jsonrpc":"2.0","id":5,"method":"tools/list","params":{}}',
        )
    )

    assert response == StreamableHttpResponse(
        status_code=400,
        payload={
            "jsonrpc": "2.0",
            "id": 5,
            "error": {
                "code": -32000,
                "message": "rpc exploded",
            },
        },
        headers={"content-type": "application/json"},
    )


def test_streamable_http_endpoint_uses_auth_validator_before_rpc_handler() -> None:
    class FakeStreamableRuntime:
        settings = None

        def handle_rpc_request(self, request: dict[str, object]) -> dict[str, object]:
            raise AssertionError("rpc handler should not be called")

    endpoint = build_streamable_http_endpoint(
        FakeStreamableRuntime(),
        mcp_path="/mcp",
        auth_validator=lambda path: StreamableHttpResponse(
            status_code=401,
            payload={
                "error": {
                    "code": "authentication_error",
                    "message": f"denied for {path}",
                }
            },
            headers={"content-type": "application/json"},
        ),
    )

    response = endpoint.handle(
        StreamableHttpRequest(
            path="/mcp?authorization=Bearer wrong",
            body='{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}',
        )
    )

    assert response == StreamableHttpResponse(
        status_code=401,
        payload={
            "error": {
                "code": "authentication_error",
                "message": "denied for /mcp?authorization=Bearer wrong",
            }
        },
        headers={"content-type": "application/json"},
    )


@dataclass
class FakeRpcRuntime:
    settings: AppSettings
    _mcp_lifecycle_state: McpLifecycleState = McpLifecycleState()
    tool_response: McpToolResponse | None = None
    resource_response: McpResourceResponse | None = None
    tool_calls: list[tuple[str, dict[str, object]]] | None = None
    resource_calls: list[str] | None = None

    def __post_init__(self) -> None:
        if self.tool_calls is None:
            self.tool_calls = []
        if self.resource_calls is None:
            self.resource_calls = []
        if self.tool_response is None:
            self.tool_response = McpToolResponse(
                payload={"ok": True, "result": {"echo": "tool"}}
            )
        if self.resource_response is None:
            self.resource_response = McpResourceResponse(
                status_code=200,
                payload={"ok": True, "result": {"echo": "resource"}},
                headers={"content-type": "application/json"},
            )

    def registered_tools(self) -> tuple[str, ...]:
        return ("demo_tool",)

    def registered_resources(self) -> tuple[str, ...]:
        return ("workspace://{workspace_id}/resume",)

    def tool_schema(self, tool_name: str):  # type: ignore[no-untyped-def]
        from ctxledger.mcp.tool_schemas import DEFAULT_EMPTY_MCP_TOOL_SCHEMA

        return DEFAULT_EMPTY_MCP_TOOL_SCHEMA

    def dispatch_tool(
        self,
        tool_name: str,
        arguments: dict[str, object],
    ) -> McpToolResponse:
        assert self.tool_calls is not None
        self.tool_calls.append((tool_name, arguments))
        assert self.tool_response is not None
        return self.tool_response

    def dispatch_resource(self, uri: str) -> McpResourceResponse:
        assert self.resource_calls is not None
        self.resource_calls.append(uri)
        assert self.resource_response is not None
        return self.resource_response


def test_handle_mcp_rpc_request_accepts_notifications_initialized() -> None:
    runtime = FakeRpcRuntime(settings=make_settings())

    response = handle_mcp_rpc_request(
        runtime,
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
    )

    assert response is None
    assert runtime._mcp_lifecycle_state.initialized is True


def test_handle_mcp_rpc_request_returns_initialize_success_payload() -> None:
    settings = make_settings()
    runtime = FakeRpcRuntime(settings=settings)

    response = handle_mcp_rpc_request(
        runtime,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        },
    )

    assert response == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "serverInfo": {
                "name": "ctxledger",
                "version": settings.app_version,
            },
            "capabilities": {
                "tools": {},
                "resources": {},
            },
        },
    }
    assert runtime._mcp_lifecycle_state.negotiated_protocol_version == (
        MCP_PROTOCOL_VERSION
    )


def test_handle_mcp_rpc_request_returns_tools_list_payload() -> None:
    settings = make_settings()
    runtime = FakeRpcRuntime(settings=settings)

    response = handle_mcp_rpc_request(
        runtime,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    )

    assert response is not None
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 2
    tools = response["result"]["tools"]
    assert len(tools) == 1
    assert tools[0]["name"] == "demo_tool"
    assert tools[0]["description"] == "demo_tool tool"
    assert tools[0]["inputSchema"] == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }


def test_handle_mcp_rpc_request_returns_tools_call_payload() -> None:
    settings = make_settings()
    runtime = FakeRpcRuntime(
        settings=settings,
        tool_response=McpToolResponse(
            payload={"ok": True, "result": {"message": "hello"}}
        ),
    )

    response = handle_mcp_rpc_request(
        runtime,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "demo_tool",
                "arguments": {"value": "x"},
            },
        },
    )

    assert response == {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"ok": True, "result": {"message": "hello"}},
                        ensure_ascii=False,
                    ),
                }
            ]
        },
    }
    assert runtime.tool_calls == [("demo_tool", {"value": "x"})]


def test_handle_mcp_rpc_request_returns_resources_list_payload() -> None:
    runtime = FakeRpcRuntime(settings=make_settings())

    response = handle_mcp_rpc_request(
        runtime,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/list",
            "params": {},
        },
    )

    assert response == {
        "jsonrpc": "2.0",
        "id": 4,
        "result": {
            "resources": [
                {
                    "uri": "workspace://{workspace_id}/resume",
                    "name": "workspace://{workspace_id}/resume",
                    "description": "workspace://{workspace_id}/resume resource",
                }
            ]
        },
    }


def test_handle_mcp_rpc_request_returns_resources_read_payload() -> None:
    runtime = FakeRpcRuntime(
        settings=make_settings(),
        resource_response=McpResourceResponse(
            status_code=200,
            payload={"resource": {"status": "ok"}},
            headers={"content-type": "application/json"},
        ),
    )

    response = handle_mcp_rpc_request(
        runtime,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "workspace://abc/resume"},
        },
    )

    assert response == {
        "jsonrpc": "2.0",
        "id": 5,
        "result": {
            "contents": [
                {
                    "uri": "workspace://abc/resume",
                    "mimeType": "application/json",
                    "text": json.dumps(
                        {"resource": {"status": "ok"}},
                        ensure_ascii=False,
                    ),
                }
            ]
        },
    }
    assert runtime.resource_calls == ["workspace://abc/resume"]
