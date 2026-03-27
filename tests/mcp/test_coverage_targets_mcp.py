from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.memory.service import MemoryFeature, MemoryItemRecord, SearchMemoryResponse
from ctxledger.runtime.introspection import RuntimeIntrospection

from ..support.coverage_targets_support import make_server, make_settings


def test_mcp_dispatch_rpc_method_exit_raises_system_exit() -> None:
    from ctxledger.mcp.rpc import dispatch_rpc_method

    with pytest.raises(SystemExit) as exc_info:
        dispatch_rpc_method(
            SimpleNamespace(),
            method="exit",
            params={},
        )

    assert exc_info.value.code == 0


def test_mcp_dispatch_rpc_method_raises_for_unknown_method() -> None:
    from ctxledger.mcp.rpc import dispatch_rpc_method

    with pytest.raises(ValueError, match="Unknown method: unknown/method"):
        dispatch_rpc_method(
            SimpleNamespace(),
            method="unknown/method",
            params={},
        )


def test_mcp_dispatch_rpc_method_validates_tools_call_params() -> None:
    from ctxledger.mcp.rpc import dispatch_rpc_method

    runtime = SimpleNamespace()

    with pytest.raises(ValueError, match="tools/call requires 'params' \\(object\\)"):
        dispatch_rpc_method(runtime, method="tools/call", params=None)

    with pytest.raises(ValueError, match="tools/call requires 'name' \\(string\\)"):
        dispatch_rpc_method(runtime, method="tools/call", params={"arguments": {}})

    with pytest.raises(ValueError, match="tools/call requires 'arguments' \\(object\\)"):
        dispatch_rpc_method(
            runtime,
            method="tools/call",
            params={"name": "demo_tool", "arguments": "not-an-object"},
        )


def test_mcp_dispatch_rpc_method_validates_resources_read_params() -> None:
    from ctxledger.mcp.rpc import dispatch_rpc_method

    runtime = SimpleNamespace()

    with pytest.raises(ValueError, match="resources/read requires 'params' \\(object\\)"):
        dispatch_rpc_method(runtime, method="resources/read", params=None)

    with pytest.raises(ValueError, match="resources/read requires 'uri' \\(string\\)"):
        dispatch_rpc_method(runtime, method="resources/read", params={})


def test_mcp_handle_request_returns_none_for_notification_and_lifecycle_none() -> None:
    from ctxledger.mcp.rpc import handle_mcp_rpc_request

    runtime = SimpleNamespace()
    request = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}

    response = handle_mcp_rpc_request(runtime, request)

    assert response is None
    assert hasattr(runtime, "_mcp_lifecycle_state")
    assert runtime._mcp_lifecycle_state.initialized is True


def test_mcp_handle_request_returns_none_for_notification_without_id() -> None:
    from ctxledger.mcp.rpc import handle_mcp_rpc_request

    def dispatch_tool(name: object, arguments: object) -> SimpleNamespace:
        return SimpleNamespace(payload={"ok": True})

    def registered_tools() -> tuple[()]:
        return ()

    def registered_resources() -> tuple[()]:
        return ()

    def tool_schema(tool_name: object) -> SimpleNamespace:
        return SimpleNamespace(
            type="object",
            properties={},
            required=(),
        )

    def dispatch_resource(uri: object) -> SimpleNamespace:
        return SimpleNamespace(payload={"ok": True})

    runtime = SimpleNamespace(
        dispatch_tool=dispatch_tool,
    )
    runtime.registered_tools = registered_tools
    runtime.registered_resources = registered_resources
    runtime.tool_schema = tool_schema
    runtime.dispatch_resource = dispatch_resource

    response = handle_mcp_rpc_request(
        runtime,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "demo_tool", "arguments": {}},
        },
    )

    assert response is None


def test_build_mcp_interaction_request_event_returns_tool_call_payload() -> None:
    from ctxledger.mcp.rpc import build_mcp_interaction_request_event

    event = build_mcp_interaction_request_event(
        method="tools/call",
        params={
            "name": "memory_search",
            "arguments": {
                "query": "resume",
                "filters": {
                    "provenance": ["interaction"],
                    "file_operation": "modify",
                },
            },
        },
    )

    assert event == {
        "interaction_role": "user",
        "interaction_direction": "inbound",
        "transport": "mcp",
        "interaction_kind": "tool_call",
        "method": "tools/call",
        "tool_name": "memory_search",
        "arguments": {
            "query": "resume",
            "filters": {
                "provenance": ["interaction"],
                "file_operation": "modify",
            },
        },
    }


def test_build_mcp_interaction_request_event_returns_resource_read_payload() -> None:
    from ctxledger.mcp.rpc import build_mcp_interaction_request_event

    event = build_mcp_interaction_request_event(
        method="resources/read",
        params={"uri": "workspace://123e4567-e89b-12d3-a456-426614174000/resume"},
    )

    assert event == {
        "interaction_role": "user",
        "interaction_direction": "inbound",
        "transport": "mcp",
        "interaction_kind": "resource_read",
        "method": "resources/read",
        "resource_uri": "workspace://123e4567-e89b-12d3-a456-426614174000/resume",
    }


def test_build_mcp_interaction_request_event_returns_none_for_unsupported_method() -> None:
    from ctxledger.mcp.rpc import build_mcp_interaction_request_event

    event = build_mcp_interaction_request_event(
        method="tools/list",
        params={},
    )

    assert event is None


def test_build_mcp_interaction_response_event_returns_tool_result_payload() -> None:
    from ctxledger.mcp.rpc import build_mcp_interaction_response_event

    result = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {"ok": True, "result": {"message": "captured"}},
                    ensure_ascii=False,
                ),
            }
        ]
    }

    event = build_mcp_interaction_response_event(
        method="tools/call",
        params={
            "name": "memory_search",
            "arguments": {"query": "resume"},
        },
        result=result,
    )

    assert event == {
        "interaction_role": "agent",
        "interaction_direction": "outbound",
        "transport": "mcp",
        "interaction_kind": "tool_result",
        "method": "tools/call",
        "tool_name": "memory_search",
        "arguments": {"query": "resume"},
        "result": result,
    }


def test_build_mcp_interaction_response_event_returns_resource_result_payload() -> None:
    from ctxledger.mcp.rpc import build_mcp_interaction_response_event

    result = {
        "contents": [
            {
                "uri": "workspace://abc/resume",
                "mimeType": "application/json",
                "text": json.dumps({"resource": {"status": "ok"}}, ensure_ascii=False),
            }
        ]
    }

    event = build_mcp_interaction_response_event(
        method="resources/read",
        params={"uri": "workspace://abc/resume"},
        result=result,
    )

    assert event == {
        "interaction_role": "agent",
        "interaction_direction": "outbound",
        "transport": "mcp",
        "interaction_kind": "resource_result",
        "method": "resources/read",
        "resource_uri": "workspace://abc/resume",
        "result": result,
    }


def test_mcp_ensure_lifecycle_state_reuses_existing_state() -> None:
    from ctxledger.mcp.rpc import McpLifecycleState, ensure_lifecycle_state

    existing_state = McpLifecycleState(initialized=True)
    runtime = SimpleNamespace(_mcp_lifecycle_state=existing_state)

    state = ensure_lifecycle_state(runtime)

    assert state is existing_state


def test_mcp_handle_request_stores_last_interaction_events_for_tool_call() -> None:
    from ctxledger.mcp.rpc import handle_mcp_rpc_request

    def dispatch_tool(name: object, arguments: object) -> SimpleNamespace:
        assert name == "demo_tool"
        assert arguments == {"value": "x"}
        return SimpleNamespace(payload={"ok": True, "result": {"message": "hello"}})

    runtime = SimpleNamespace(
        dispatch_tool=dispatch_tool,
        registered_tools=lambda: ("demo_tool",),
        registered_resources=lambda: (),
        tool_schema=lambda tool_name: SimpleNamespace(
            type="object",
            properties={},
            required=(),
        ),
        dispatch_resource=lambda uri: SimpleNamespace(payload={"ok": True}),
    )

    response = handle_mcp_rpc_request(
        runtime,
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "demo_tool",
                "arguments": {"value": "x"},
            },
        },
    )

    assert response is not None
    assert runtime._last_mcp_interaction_request_event == {
        "interaction_role": "user",
        "interaction_direction": "inbound",
        "transport": "mcp",
        "interaction_kind": "tool_call",
        "method": "tools/call",
        "tool_name": "demo_tool",
        "arguments": {"value": "x"},
    }
    assert runtime._last_mcp_interaction_response_event == {
        "interaction_role": "agent",
        "interaction_direction": "outbound",
        "transport": "mcp",
        "interaction_kind": "tool_result",
        "method": "tools/call",
        "tool_name": "demo_tool",
        "arguments": {"value": "x"},
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


def test_mcp_handle_request_stores_last_interaction_events_for_resource_read() -> None:
    from ctxledger.mcp.rpc import handle_mcp_rpc_request

    runtime = SimpleNamespace(
        dispatch_tool=lambda name, arguments: SimpleNamespace(payload={"ok": True}),
        registered_tools=lambda: (),
        registered_resources=lambda: ("workspace://{workspace_id}/resume",),
        tool_schema=lambda tool_name: SimpleNamespace(
            type="object",
            properties={},
            required=(),
        ),
        dispatch_resource=lambda uri: SimpleNamespace(payload={"resource": {"status": "ok"}}),
    )

    response = handle_mcp_rpc_request(
        runtime,
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "resources/read",
            "params": {
                "uri": "workspace://abc/resume",
            },
        },
    )

    assert response is not None
    assert runtime._last_mcp_interaction_request_event == {
        "interaction_role": "user",
        "interaction_direction": "inbound",
        "transport": "mcp",
        "interaction_kind": "resource_read",
        "method": "resources/read",
        "resource_uri": "workspace://abc/resume",
    }
    assert runtime._last_mcp_interaction_response_event == {
        "interaction_role": "agent",
        "interaction_direction": "outbound",
        "transport": "mcp",
        "interaction_kind": "resource_result",
        "method": "resources/read",
        "resource_uri": "workspace://abc/resume",
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


def test_http_runtime_adapter_dispatch_tool_persists_interaction_memory() -> None:
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    created_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    persisted_items: list[MemoryItemRecord] = []

    class FakeMemoryService:
        def search(self, request: object) -> object:
            return SearchMemoryResponse(
                feature=MemoryFeature.SEARCH,
                implemented=True,
                message="ok",
                status="ok",
                available_in_version="0.3.0",
                timestamp=created_at,
                results=(),
                details={},
            )

        def persist_interaction_memory(
            self,
            *,
            content: str,
            interaction_role: str,
            interaction_kind: str,
            workspace_id: str | None = None,
            workflow_instance_id: str | None = None,
            metadata: dict[str, object] | None = None,
        ) -> MemoryItemRecord:
            memory_item = MemoryItemRecord(
                memory_id=uuid4(),
                workspace_id=None,
                episode_id=None,
                type=interaction_kind,
                provenance="interaction",
                content=content,
                metadata=dict(metadata or {}),
                created_at=created_at,
                updated_at=created_at,
            )
            persisted_items.append(memory_item)
            return memory_item

    runtime = HttpRuntimeAdapter(make_settings())
    runtime._server = SimpleNamespace(
        workflow_service=SimpleNamespace(),
    )
    runtime.register_handler(
        "demo",
        lambda path: SimpleNamespace(
            status_code=200,
            payload={"path": path},
            headers={"content-type": "application/json"},
        ),
    )

    import ctxledger.runtime.http_runtime as http_runtime_module

    original_builder = http_runtime_module.build_workflow_backed_memory_service
    http_runtime_module.build_workflow_backed_memory_service = lambda server: FakeMemoryService()

    try:
        runtime.dispatch_tool(
            "memory_search",
            {
                "query": "resume",
                "workspace_id": str(uuid4()),
                "workflow_instance_id": str(uuid4()),
                "filters": {
                    "provenance": ["interaction"],
                    "file_operation": "modify",
                    "file_path": "ctxledger/docs/memory/design/interaction_memory_contract.md",
                    "purpose": "capture interaction-memory contract updates",
                },
            },
        )
    finally:
        http_runtime_module.build_workflow_backed_memory_service = original_builder

    assert len(persisted_items) == 2

    request_item, response_item = persisted_items
    assert request_item.type == "interaction_request"
    assert request_item.provenance == "interaction"
    assert request_item.metadata["transport"] == "http_runtime"
    assert request_item.metadata["tool_name"] == "memory_search"
    assert request_item.content.startswith("tool:memory_search arguments=")

    assert response_item.type == "interaction_response"
    assert response_item.provenance == "interaction"
    assert response_item.metadata["transport"] == "http_runtime"
    assert response_item.metadata["tool_name"] == "memory_search"
    assert response_item.content.startswith("tool:memory_search result=")


def test_http_runtime_adapter_dispatch_tool_ignores_interaction_persistence_errors() -> None:
    from ctxledger.memory.service import MemoryServiceError
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    class FakeMemoryService:
        def search(self, request: object) -> object:
            return SearchMemoryResponse(
                feature=MemoryFeature.SEARCH,
                implemented=True,
                message="ok",
                status="ok",
                available_in_version="0.3.0",
                timestamp=created_at,
                results=(),
                details={},
            )

        def persist_interaction_memory(
            self,
            *,
            content: str,
            interaction_role: str,
            interaction_kind: str,
            workspace_id: str | None = None,
            workflow_instance_id: str | None = None,
            metadata: dict[str, object] | None = None,
        ) -> MemoryItemRecord:
            raise MemoryServiceError(
                code="memory_invalid_request",
                message="bad interaction memory",
                feature="memory_remember_episode",
                details={"field": "content"},
            )

    created_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    runtime = HttpRuntimeAdapter(make_settings())
    runtime._server = SimpleNamespace(
        workflow_service=SimpleNamespace(),
    )

    import ctxledger.runtime.http_runtime as http_runtime_module

    original_builder = http_runtime_module.build_workflow_backed_memory_service
    http_runtime_module.build_workflow_backed_memory_service = lambda server: FakeMemoryService()

    try:
        response = runtime.dispatch_tool(
            "memory_search",
            {
                "query": "resume",
            },
        )
    finally:
        http_runtime_module.build_workflow_backed_memory_service = original_builder

    assert response.payload["ok"] is True
    assert response.payload["result"]["feature"] == "memory_search"


def test_http_runtime_adapter_dispatch_resource_persists_interaction_memory() -> None:
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    created_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    persisted_items: list[MemoryItemRecord] = []
    workspace_id = str(uuid4())
    workflow_instance_id = str(uuid4())

    class FakeMemoryService:
        def persist_interaction_memory(
            self,
            *,
            content: str,
            interaction_role: str,
            interaction_kind: str,
            workspace_id: str | None = None,
            workflow_instance_id: str | None = None,
            metadata: dict[str, object] | None = None,
        ) -> MemoryItemRecord:
            memory_item = MemoryItemRecord(
                memory_id=uuid4(),
                workspace_id=None,
                episode_id=None,
                type=interaction_kind,
                provenance="interaction",
                content=content,
                metadata=dict(metadata or {}),
                created_at=created_at,
                updated_at=created_at,
            )
            persisted_items.append(memory_item)
            return memory_item

    runtime = HttpRuntimeAdapter(make_settings())
    runtime._server = SimpleNamespace(
        workflow_service=SimpleNamespace(),
    )

    resource_uri = f"workspace://{workspace_id}/resume"
    resource_payload = {
        "uri": resource_uri,
        "resource": {
            "workspace": {"workspace_id": workspace_id},
            "workflow": {"workflow_instance_id": workflow_instance_id},
        },
        "selection": {
            "selected_workflow_instance_id": workflow_instance_id,
        },
    }

    original_workspace_handler_builder = __import__(
        "ctxledger.runtime.http_runtime",
        fromlist=["build_workspace_resume_resource_handler"],
    ).build_workspace_resume_resource_handler
    import ctxledger.runtime.http_runtime as http_runtime_module

    original_builder = http_runtime_module.build_workflow_backed_memory_service
    http_runtime_module.build_workflow_backed_memory_service = lambda server: FakeMemoryService()
    http_runtime_module.build_workspace_resume_resource_handler = lambda server: (
        lambda uri: SimpleNamespace(
            status_code=200,
            payload=resource_payload,
            headers={"content-type": "application/json"},
        )
    )

    try:
        response = runtime.dispatch_resource(resource_uri)
    finally:
        http_runtime_module.build_workflow_backed_memory_service = original_builder
        http_runtime_module.build_workspace_resume_resource_handler = (
            original_workspace_handler_builder
        )

    assert response.status_code == 200
    assert len(persisted_items) == 2

    request_item, response_item = persisted_items
    assert request_item.type == "interaction_request"
    assert request_item.provenance == "interaction"
    assert request_item.metadata["transport"] == "http_runtime"
    assert request_item.metadata["resource_uri"] == resource_uri
    assert request_item.metadata["resource_kind"] == "workspace_resume"
    assert request_item.content == f"resource:{resource_uri} read"

    assert response_item.type == "interaction_response"
    assert response_item.provenance == "interaction"
    assert response_item.metadata["transport"] == "http_runtime"
    assert response_item.metadata["resource_uri"] == resource_uri
    assert response_item.metadata["resource_kind"] == "workspace_resume"
    assert response_item.metadata["result"] == resource_payload
    assert response_item.content == f"resource:{resource_uri} result={resource_payload}"


def test_http_runtime_adapter_handler_registration_and_lookup() -> None:
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings())

    handler = object()
    runtime.register_handler("demo", handler)

    assert runtime.handler("demo") is handler
    assert runtime.handler("missing") is None
    assert runtime.require_handler("demo") is handler

    with pytest.raises(KeyError, match="missing"):
        runtime.require_handler("missing")


def test_http_runtime_adapter_introspection_and_schema_defaults() -> None:
    from ctxledger.mcp.tool_schemas import DEFAULT_EMPTY_MCP_TOOL_SCHEMA
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings())

    assert runtime.introspection_endpoints() == ()
    assert "workflow_resume" in runtime.registered_tools()
    assert "workspace://{workspace_id}/resume" in runtime.registered_resources()
    assert runtime.tool_schema("unknown_tool") is DEFAULT_EMPTY_MCP_TOOL_SCHEMA

    runtime.register_handler("zeta", object())
    runtime.register_handler("alpha", object())

    assert runtime.introspection_endpoints() == ("alpha", "zeta")
    assert runtime.introspect().transport == "http"


def test_http_runtime_adapter_dispatch_resource_returns_not_found_for_unknown_uri() -> None:
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings())

    response = runtime.dispatch_resource("workspace://unknown/resource")

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "resource_not_found",
            "message": "unknown MCP resource 'workspace://unknown/resource'",
        }
    }


def test_http_runtime_adapter_dispatch_tool_returns_not_found_for_unknown_tool() -> None:
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings())

    response = runtime.dispatch_tool("unknown_tool", {})

    assert response.payload["error"]["code"] == "tool_not_found"


def test_http_runtime_adapter_dispatch_covers_missing_route_and_mcp_rpc() -> None:
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings(path="/mcp"))

    missing_route_response = runtime.dispatch("missing", "/missing")

    runtime.register_handler(
        "mcp_rpc",
        lambda path, body=None: SimpleNamespace(
            status_code=202,
            payload={"path": path, "body": body},
            headers={"content-type": "application/json"},
        ),
    )
    runtime.register_handler(
        "workflow_resume",
        lambda path: SimpleNamespace(
            status_code=200,
            payload={"path": path},
            headers={"content-type": "application/json"},
        ),
    )

    mcp_response = runtime.dispatch("mcp_rpc", "/mcp", "payload")
    workflow_response = runtime.dispatch("workflow_resume", "/workflow-resume/demo")

    assert missing_route_response.status_code == 404
    assert missing_route_response.payload["error"]["code"] == "route_not_found"
    assert mcp_response.status_code == 202
    assert mcp_response.payload == {"path": "/mcp", "body": "payload"}
    assert workflow_response.status_code == 200
    assert workflow_response.payload == {"path": "/workflow-resume/demo"}


def test_http_runtime_adapter_start_and_stop_cover_idempotent_stop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from ctxledger.runtime.http_runtime import HttpRuntimeAdapter

    runtime = HttpRuntimeAdapter(make_settings())
    caplog.set_level("INFO")

    runtime.stop()
    runtime.start()
    runtime.stop()

    assert runtime._started is False
    assert any("HTTP runtime adapter starting" in message for message in caplog.messages)
    assert any("HTTP runtime adapter stopping" in message for message in caplog.messages)


def test_http_runtime_register_handlers_respects_debug_toggle() -> None:
    from ctxledger.runtime.http_runtime import (
        HttpRuntimeAdapter,
        register_http_runtime_handlers,
    )

    debug_server = make_server(settings=make_settings(debug_enabled=True))
    no_debug_server = make_server(settings=make_settings(debug_enabled=False))

    debug_runtime = register_http_runtime_handlers(
        HttpRuntimeAdapter(debug_server.settings, server=debug_server),
        debug_server,
    )
    no_debug_runtime = register_http_runtime_handlers(
        HttpRuntimeAdapter(no_debug_server.settings, server=no_debug_server),
        no_debug_server,
    )

    assert "mcp_rpc" in debug_runtime.introspection_endpoints()
    assert "runtime_introspection" in debug_runtime.introspection_endpoints()
    assert "runtime_routes" in debug_runtime.introspection_endpoints()
    assert "runtime_tools" in debug_runtime.introspection_endpoints()

    assert "mcp_rpc" in no_debug_runtime.introspection_endpoints()
    assert "runtime_introspection" not in no_debug_runtime.introspection_endpoints()
    assert "runtime_routes" not in no_debug_runtime.introspection_endpoints()
    assert "runtime_tools" not in no_debug_runtime.introspection_endpoints()


def test_http_runtime_build_http_runtime_adapter_returns_registered_runtime() -> None:
    from ctxledger.runtime.http_runtime import (
        HttpRuntimeAdapter,
        build_http_runtime_adapter,
    )

    server = make_server(settings=make_settings())

    runtime = build_http_runtime_adapter(server)

    assert isinstance(runtime, HttpRuntimeAdapter)
    assert runtime.handler("mcp_rpc") is not None
    assert runtime.handler("workflow_resume") is not None


def test_build_runtime_routes_and_tools_responses_include_multiple_non_empty_introspections() -> (
    None
):
    from ctxledger.runtime.server_responses import (
        build_runtime_routes_response,
        build_runtime_tools_response,
    )

    runtime = SimpleNamespace(
        _runtimes=[
            SimpleNamespace(
                introspect=lambda: RuntimeIntrospection(
                    transport="http",
                    routes=("workflow_resume",),
                    tools=("workflow_resume",),
                    resources=(),
                )
            ),
            SimpleNamespace(
                introspect=lambda: RuntimeIntrospection(
                    transport="mcp",
                    routes=("runtime_introspection",),
                    tools=("tool_a", "tool_b"),
                    resources=(),
                )
            ),
        ]
    )
    server = make_server(runtime=runtime)

    routes_response = build_runtime_routes_response(server)
    tools_response = build_runtime_tools_response(server)

    assert routes_response.status_code == 200
    assert routes_response.payload == {
        "routes": [
            {"transport": "http", "routes": ["workflow_resume"]},
            {"transport": "mcp", "routes": ["runtime_introspection"]},
        ]
    }
    assert tools_response.status_code == 200
    assert tools_response.payload == {
        "tools": [
            {"transport": "http", "tools": ["workflow_resume"]},
            {"transport": "mcp", "tools": ["tool_a", "tool_b"]},
        ]
    }
