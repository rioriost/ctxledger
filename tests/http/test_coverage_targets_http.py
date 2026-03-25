from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.runtime.errors import ServerBootstrapError
from ctxledger.runtime.http_handlers import (
    build_mcp_http_handler,
    build_runtime_introspection_http_handler,
    build_runtime_routes_http_handler,
    build_runtime_tools_http_handler,
    build_workflow_resume_http_handler,
    parse_required_uuid_argument,
    parse_workflow_resume_request_path,
)
from ctxledger.runtime.introspection import RuntimeIntrospection
from ctxledger.runtime.server_responses import (
    build_workflow_detail_resource_response,
    build_workflow_resume_response,
    build_workspace_resume_resource_response,
)
from ctxledger.server import CtxLedgerServer, create_server
from ctxledger.workflow.service import ValidationError, WorkflowError

from ..support.coverage_targets_support import make_server, make_settings
from ..support.server_test_support import FakeDatabaseHealthChecker


def _load_http_app_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(),
    )
    sys.modules.pop("ctxledger.http_app", None)
    return importlib.import_module("ctxledger.http_app")


def test_http_app_request_helpers_and_response_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)

    request = SimpleNamespace(
        headers={"authorization": " Bearer test-token "},
        query_params=SimpleNamespace(
            multi_items=lambda: [("x", "1"), ("authorization", "old-token")]
        ),
        url=SimpleNamespace(path="/debug/runtime"),
    )

    assert http_app._authorization_query_value(request) == "Bearer test-token"
    assert http_app._query_items_with_authorization(request) == [
        ("x", "1"),
        ("authorization", "Bearer test-token"),
    ]
    assert http_app._query_string_from_request(request) == "x=1&authorization=Bearer+test-token"
    assert (
        http_app._full_path_with_query(request)
        == "/debug/runtime?x=1&authorization=Bearer+test-token"
    )
    assert http_app._request_body_text(b"hello") == "hello"
    assert http_app._request_body_text(b"") is None
    assert http_app._encode_payload({"message": "hello"}).decode("utf-8") == '{"message": "hello"}'

    response = http_app._response_from_runtime_result(
        SimpleNamespace(
            payload={"ok": True},
            status_code=201,
            headers={"x-test": "1"},
        )
    )

    assert response.status_code == 201
    assert response.headers["x-test"] == "1"
    assert response.headers["content-type"].startswith("application/json")
    assert json.loads(response.body.decode("utf-8")) == {"ok": True}


def test_http_app_server_not_ready_response_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)

    response = http_app._server_not_ready_response()

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    assert json.loads(response.body.decode("utf-8")) == {
        "error": {
            "code": "server_not_ready",
            "message": "runtime is not initialized",
        }
    }


def test_http_app_build_get_and_post_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)
    server = make_server(runtime=object())

    def get_factory(_server: object):
        def handler(path: str) -> object:
            return SimpleNamespace(
                payload={"path": path},
                status_code=200,
                headers={"x-kind": "get"},
            )

        return handler

    def post_factory(_runtime: object, _server: object):
        def handler(path: str, body: str | None) -> object:
            return SimpleNamespace(
                payload={"path": path, "body": body},
                status_code=202,
                headers={"x-kind": "post"},
            )

        return handler

    get_route = http_app._build_get_route(server, get_factory)
    post_route = http_app._build_post_route(server, post_factory)

    get_request = SimpleNamespace(
        headers={"authorization": "Bearer abc"},
        query_params=SimpleNamespace(multi_items=lambda: [("q", "1")]),
        url=SimpleNamespace(path="/debug/runtime"),
    )

    async def body_bytes() -> bytes:
        return b'{"hello":"world"}'

    post_request = SimpleNamespace(
        headers={},
        query_params=SimpleNamespace(multi_items=lambda: []),
        url=SimpleNamespace(path="/mcp"),
        body=body_bytes,
    )

    get_response = asyncio.run(get_route(get_request))
    post_response = asyncio.run(post_route(post_request))

    assert get_response.status_code == 200
    assert json.loads(get_response.body.decode("utf-8")) == {
        "path": "/debug/runtime?q=1&authorization=Bearer+abc"
    }
    assert post_response.status_code == 202
    assert json.loads(post_response.body.decode("utf-8")) == {
        "path": "/mcp",
        "body": '{"hello":"world"}',
    }


def test_http_app_create_fastapi_app_from_settings_and_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)
    settings = make_settings()

    created_servers: list[object] = []
    created_apps: list[object] = []

    sentinel_server = object()
    sentinel_app_1 = object()
    sentinel_app_2 = object()

    original_create_server = http_app.create_server
    original_create_fastapi_app = http_app.create_fastapi_app

    def fake_create_server(received_settings):
        created_servers.append(received_settings)
        return sentinel_server

    def fake_create_fastapi_app(server: object) -> object:
        created_apps.append(server)
        return sentinel_app_1 if len(created_apps) == 1 else sentinel_app_2

    try:
        http_app.create_server = fake_create_server
        http_app.create_fastapi_app = fake_create_fastapi_app
        app_from_settings = http_app.create_fastapi_app_from_settings(settings)
        default_app = http_app.create_default_fastapi_app()
    finally:
        http_app.create_server = original_create_server
        http_app.create_fastapi_app = original_create_fastapi_app

    assert app_from_settings is sentinel_app_1
    assert default_app is sentinel_app_2
    assert created_servers[0] is settings
    assert created_apps == [sentinel_server, sentinel_server]


def test_http_app_create_default_fastapi_app_does_not_start_server_eagerly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)
    sentinel_app = object()
    startup_calls = 0

    class FakeServer:
        def __init__(self) -> None:
            self.settings = make_settings()

        def startup(self) -> None:
            nonlocal startup_calls
            startup_calls += 1

    original_create_server = http_app.create_server
    original_create_fastapi_app = http_app.create_fastapi_app

    def fake_create_server(received_settings):
        return FakeServer()

    def fake_create_fastapi_app(server: object) -> object:
        assert isinstance(server, FakeServer)
        return sentinel_app

    try:
        http_app.create_server = fake_create_server
        http_app.create_fastapi_app = fake_create_fastapi_app
        app = http_app.create_default_fastapi_app()
    finally:
        http_app.create_server = original_create_server
        http_app.create_fastapi_app = original_create_fastapi_app

    assert app is sentinel_app
    assert startup_calls == 0


def test_http_app_create_fastapi_app_registers_expected_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)
    server = make_server(settings=make_settings(path="mcp"))

    app = http_app.create_fastapi_app(server)

    paths = {route.path for route in app.routes}
    assert "/mcp" in paths
    assert "/debug/runtime" in paths
    assert "/debug/routes" in paths
    assert "/debug/tools" in paths
    assert "/workflow-resume/{workflow_instance_id}" in paths


def test_http_app_request_helpers_cover_missing_authorization_and_default_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)

    request = SimpleNamespace(
        headers={"authorization": "   "},
        query_params=SimpleNamespace(multi_items=lambda: [("x", "1")]),
        url=SimpleNamespace(path="/debug/runtime"),
    )

    assert http_app._authorization_query_value(request) is None
    assert http_app._query_items_with_authorization(request) == [("x", "1")]
    assert http_app._query_string_from_request(request) == "x=1"
    assert http_app._full_path_with_query(request) == "/debug/runtime?x=1"

    response = http_app._response_from_runtime_result(
        SimpleNamespace(
            payload={"ok": True},
            status_code=200,
            headers=None,
        )
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert json.loads(response.body.decode("utf-8")) == {"ok": True}


def test_http_app_build_get_and_post_routes_return_server_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http_app = _load_http_app_module(monkeypatch)
    server = make_server(runtime=None)

    def get_factory(_server: object):
        def handler(path: str) -> object:
            raise AssertionError("get handler should not be called")

        return handler

    def post_factory(_runtime: object, _server: object):
        def handler(path: str, body: str | None) -> object:
            raise AssertionError("post handler should not be called")

        return handler

    get_route = http_app._build_get_route(server, get_factory)
    post_route = http_app._build_post_route(server, post_factory)

    request = SimpleNamespace(
        headers={},
        query_params=SimpleNamespace(multi_items=lambda: []),
        url=SimpleNamespace(path="/mcp"),
        body=lambda: None,
    )

    get_response = asyncio.run(get_route(request))
    post_response = asyncio.run(post_route(request))

    assert get_response.status_code == 503
    assert post_response.status_code == 503
    assert json.loads(get_response.body.decode("utf-8")) == {
        "error": {
            "code": "server_not_ready",
            "message": "runtime is not initialized",
        }
    }
    assert json.loads(post_response.body.decode("utf-8")) == {
        "error": {
            "code": "server_not_ready",
            "message": "runtime is not initialized",
        }
    }


def test_http_handlers_parse_required_uuid_argument_success() -> None:
    value = uuid4()

    parsed = parse_required_uuid_argument({"workspace_id": str(value)}, "workspace_id")

    assert parsed == value


def test_http_handlers_parse_required_uuid_argument_rejects_missing_value() -> None:
    response = parse_required_uuid_argument({}, "workspace_id")

    assert response.payload["error"]["code"] == "invalid_request"
    assert response.payload["error"]["message"] == "workspace_id must be a non-empty string"


def test_http_handlers_parse_required_uuid_argument_rejects_invalid_uuid() -> None:
    response = parse_required_uuid_argument(
        {"workspace_id": "not-a-uuid"},
        "workspace_id",
    )

    assert response.payload["error"]["code"] == "invalid_request"
    assert response.payload["error"]["message"] == "workspace_id must be a valid UUID"


def test_http_handlers_parse_request_paths_cover_success_and_invalid_cases() -> None:
    workflow_instance_id = uuid4()

    assert (
        parse_workflow_resume_request_path(f"/workflow-resume/{workflow_instance_id}?x=1")
        == workflow_instance_id
    )
    assert parse_workflow_resume_request_path("/workflow-resume/not-a-uuid") is None
    assert parse_workflow_resume_request_path("/wrong/path") is None


def test_http_handlers_build_workflow_resume_http_handler_returns_404_for_invalid_path() -> None:
    response = build_workflow_resume_http_handler(make_server())("/wrong/path")

    assert response.status_code == 404
    assert response.payload["error"]["code"] == "not_found"


def test_http_handlers_build_runtime_debug_handlers_return_404_for_wrong_paths() -> None:
    server = make_server()

    assert build_runtime_introspection_http_handler(server)("/wrong").status_code == 404
    assert build_runtime_routes_http_handler(server)("/wrong").status_code == 404
    assert build_runtime_tools_http_handler(server)("/wrong").status_code == 404


def test_http_handlers_build_runtime_debug_handlers_accept_query_string() -> None:
    runtime = types.SimpleNamespace(
        introspect=lambda: RuntimeIntrospection(
            transport="http",
            routes=("workflow_resume",),
            tools=("workflow_resume",),
            resources=("workspace://{workspace_id}/resume",),
        )
    )
    server = make_server(runtime=runtime)

    introspection_response = build_runtime_introspection_http_handler(server)(
        "/debug/runtime?verbose=1"
    )
    routes_response = build_runtime_routes_http_handler(server)("/debug/routes?x=1")
    tools_response = build_runtime_tools_http_handler(server)("/debug/tools?x=1")

    assert introspection_response.status_code == 200
    assert introspection_response.payload == {
        "runtime": [
            {
                "transport": "http",
                "routes": ["workflow_resume"],
                "tools": ["workflow_resume"],
                "resources": ["workspace://{workspace_id}/resume"],
            }
        ],
        "age_prototype": {
            "age_enabled": False,
            "age_graph_name": "ctxledger_memory",
            "observability_routes": [
                "/debug/runtime",
                "/debug/routes",
                "/debug/tools",
            ],
            "summary_graph_mirroring": {
                "enabled": False,
                "canonical_source": [
                    "memory_summaries",
                    "memory_summary_memberships",
                ],
                "derived_graph_labels": [
                    "memory_summary",
                    "memory_item",
                    "summarizes",
                ],
                "refresh_command": "ctxledger refresh-age-summary-graph",
                "read_path_scope": "narrow_auxiliary_summary_member_traversal",
                "graph_status": "unknown",
                "ready": False,
            },
            "workflow_summary_automation": {
                "orchestration_point": "workflow_completion_auto_memory",
                "default_requested": False,
                "request_field": "latest_checkpoint.checkpoint_json.build_episode_summary",
                "trigger": "latest_checkpoint.build_episode_summary_true",
                "target_scope": "workflow_completion_auto_memory_episode",
                "summary_kind": "episode_summary",
                "replace_existing": True,
                "non_fatal": True,
            },
            "age_graph_status": "unknown",
        },
    }
    assert routes_response.status_code == 200
    assert routes_response.payload == {
        "routes": [{"transport": "http", "routes": ["workflow_resume"]}]
    }
    assert tools_response.status_code == 200
    assert tools_response.payload == {
        "tools": [{"transport": "http", "tools": ["workflow_resume"]}]
    }


def test_http_handlers_build_mcp_http_handler_adapts_streamable_http_endpoint() -> None:
    runtime = SimpleNamespace(settings=SimpleNamespace(app_name="ctxledger", app_version="0.1.0"))
    server = make_server(settings=make_settings(path="/mcp"))
    handler = build_mcp_http_handler(runtime, server)

    initialize_response = handler(
        "/mcp",
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        ),
    )
    invalid_json_response = handler("/mcp", "{invalid json")

    assert initialize_response.status_code == 200
    assert initialize_response.payload["result"]["protocolVersion"] == "2024-11-05"
    assert invalid_json_response.status_code == 400
    assert invalid_json_response.payload["error"]["code"] == "invalid_request"


def test_build_workflow_resume_response_returns_server_not_ready() -> None:
    workflow_instance_id = uuid4()
    server = make_server()

    response = build_workflow_resume_response(server, workflow_instance_id)

    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_response_returns_not_found_when_workflow_is_missing() -> None:
    workflow_instance_id = uuid4()
    server = make_server()

    def raise_workflow_not_found(
        _workflow_instance_id: object,
    ) -> object:
        raise ValidationError(
            "workflow not found",
            details={"workflow_instance_id": str(workflow_instance_id)},
        )

    server.get_workflow_resume = raise_workflow_not_found

    response = build_workflow_resume_response(server, workflow_instance_id)

    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "workflow not found",
            "details": {
                "workflow_instance_id": str(workflow_instance_id),
            },
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_response_returns_invalid_request_for_workspace_id_misuse() -> None:
    workflow_instance_id = uuid4()
    workspace_id = uuid4()
    server = make_server()

    def raise_workspace_id_misuse(
        _workflow_instance_id: object,
    ) -> object:
        raise ValidationError(
            "provided workflow_instance_id appears to be a workspace_id; "
            "use workspace://{workspace_id}/resume or provide a real "
            "workflow_instance_id",
            details={
                "workflow_instance_id": str(workflow_instance_id),
                "workspace_id": str(workspace_id),
            },
        )

    server.get_workflow_resume = raise_workspace_id_misuse

    response = build_workflow_resume_response(server, workflow_instance_id)

    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": (
                "provided workflow_instance_id appears to be a workspace_id; "
                "use workspace://{workspace_id}/resume or provide a real "
                "workflow_instance_id"
            ),
            "details": {
                "workflow_instance_id": str(workflow_instance_id),
                "workspace_id": str(workspace_id),
            },
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_response_uses_default_string_when_bootstrap_error_has_no_message() -> (
    None
):
    workflow_instance_id = uuid4()
    server = make_server()

    class SilentBootstrapError(ServerBootstrapError):
        def __str__(self) -> str:
            return ""

    def raise_silent_bootstrap_error(
        _workflow_instance_id: object,
    ) -> object:
        return (_ for _ in ()).throw(SilentBootstrapError("silent"))

    server.get_workflow_resume = raise_silent_bootstrap_error

    response = build_workflow_resume_response(server, workflow_instance_id)

    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_response_serializes_resume_payload() -> None:
    workflow_instance_id = uuid4()
    expected_payload = {"workflow_instance_id": str(workflow_instance_id)}
    server = make_server()
    server.workflow_service = SimpleNamespace(
        resume_workflow=lambda data: SimpleNamespace(workflow_instance_id=data.workflow_instance_id)
    )

    serializers_module = importlib.import_module("ctxledger.runtime.serializers")
    original_serializer = serializers_module.serialize_workflow_resume

    def fake_serialize_workflow_resume(
        resume: object,
    ) -> dict[str, object]:
        assert getattr(resume, "workflow_instance_id") == workflow_instance_id
        return expected_payload

    serializers_module.serialize_workflow_resume = fake_serialize_workflow_resume

    try:
        response = build_workflow_resume_response(server, workflow_instance_id)
    finally:
        serializers_module.serialize_workflow_resume = original_serializer

    assert response.status_code == 200
    assert response.payload == expected_payload
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uses_resume_result_branch() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workspace=SimpleNamespace(workspace_id=workspace_id),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={
                "workspace": {
                    "workspace_id": str(workspace_id),
                },
                "workflow_instance_id": str(workflow_instance_id),
            },
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workspace": {
                "workspace_id": str(workspace_id),
            },
            "workflow_instance_id": str(workflow_instance_id),
        },
        "selection": {
            "strategy": "resume_result",
            "candidate_count": 1,
            "selected_workflow_instance_id": str(workflow_instance_id),
            "running_workflow_instance_id": None,
            "latest_workflow_instance_id": str(workflow_instance_id),
            "selected_reason": "used workflow returned by resume result branch",
            "latest_deprioritized": False,
            "signals": {
                "running_workflow_available": False,
                "latest_workflow_terminal": False,
                "non_terminal_candidate_available": False,
                "selected_equals_latest": True,
                "selected_equals_running": False,
                "latest_ticket_detour_like": False,
                "latest_checkpoint_detour_like": False,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": False,
                "ranking_details_present": False,
                "explanations_present": False,
            },
            "explanations": [],
            "ranking_details": [],
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_returns_not_found_for_workspace_mismatch() -> (
    None
):
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workspace=SimpleNamespace(workspace_id=other_workspace_id),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=other_workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={
                "workspace": {
                    "workspace_id": str(other_workspace_id),
                },
                "workflow_instance_id": str(workflow_instance_id),
            },
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"workspace '{workspace_id}' was not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_uses_resume_result_branch() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workflow_detail_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workflow_detail_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workflow_detail_resource_response(
            server,
            workspace_id,
            workflow_instance_id,
        )
    finally:
        build_workflow_detail_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/workflow/{workflow_instance_id}",
        "resource": {
            "workflow_instance_id": str(workflow_instance_id),
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_returns_not_found_for_missing_workflow() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()
    other_workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=other_workflow_instance_id,
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> dict[str, object]:
            return {"workflow_instance_id": str(data.workflow_instance_id)}

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)

    response = build_workflow_detail_resource_response(
        server,
        workspace_id,
        workflow_instance_id,
    )

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"workflow '{workflow_instance_id}' was not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_returns_invalid_request_for_workspace_mismatch() -> (
    None
):
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=other_workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> dict[str, object]:
            return {"workflow_instance_id": str(data.workflow_instance_id)}

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)

    response = build_workflow_detail_resource_response(
        server,
        workspace_id,
        workflow_instance_id,
    )

    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "workflow instance does not belong to workspace",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_propagates_non_success_workflow_response() -> (
    None
):
    workspace_id = uuid4()

    resume_result = SimpleNamespace(
        workspace=SimpleNamespace(workspace_id=workspace_id),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=uuid4(),
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == resume_result.workflow_instance.workflow_instance_id
        return SimpleNamespace(
            status_code=503,
            payload={
                "error": {
                    "code": "server_not_ready",
                    "message": "workflow service is not initialized",
                }
            },
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_returns_workspace_not_found() -> None:
    workspace_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(get_by_id=lambda _workspace_id: None)
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: None,
                list_by_workspace_id=lambda _workspace_id, *, limit: (),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda _workflow_instance_id: None,
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())

    response = build_workspace_resume_resource_response(server, workspace_id)

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"workspace '{workspace_id}' was not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_response_returns_not_found_for_explicit_workflow_not_found_code() -> (
    None
):
    workflow_instance_id = uuid4()
    server = make_server()

    class WorkflowNotFoundError(WorkflowError):
        code = "workflow_not_found"

        def __init__(self) -> None:
            super().__init__("workflow missing", details={})

    def raise_workflow_not_found(
        _workflow_instance_id: object,
    ) -> object:
        raise WorkflowNotFoundError()

    server.get_workflow_resume = raise_workflow_not_found

    response = build_workflow_resume_response(server, workflow_instance_id)

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "workflow missing",
            "details": {
                "workflow_instance_id": str(workflow_instance_id),
            },
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_response_returns_server_error_for_unknown_workflow_error() -> None:
    workflow_instance_id = uuid4()
    server = make_server()

    class UnknownWorkflowError(WorkflowError):
        code = "unexpected_failure"

        def __init__(self) -> None:
            super().__init__("failed to resume", details={"reason": "boom"})

    def raise_unknown_workflow_error(
        _workflow_instance_id: object,
    ) -> object:
        raise UnknownWorkflowError()

    server.get_workflow_resume = raise_unknown_workflow_error

    response = build_workflow_resume_response(server, workflow_instance_id)

    assert response.status_code == 500
    assert response.payload == {
        "error": {
            "code": "server_error",
            "message": "failed to resume",
            "details": {
                "reason": "boom",
            },
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_response_uses_default_server_error_message_when_workflow_error_string_is_empty() -> (
    None
):
    workflow_instance_id = uuid4()
    server = make_server()

    class SilentWorkflowError(WorkflowError):
        code = "unexpected_failure"

        def __init__(self) -> None:
            super().__init__("", details={})

    def raise_silent_workflow_error(
        _workflow_instance_id: object,
    ) -> object:
        raise SilentWorkflowError()

    server.get_workflow_resume = raise_silent_workflow_error

    response = build_workflow_resume_response(server, workflow_instance_id)

    assert response.status_code == 500
    assert response.payload == {
        "error": {
            "code": "server_error",
            "message": "failed to resume workflow",
            "details": {},
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_propagates_non_success_workflow_response() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> dict[str, object]:
            return {"workflow_instance_id": str(data.workflow_instance_id)}

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workflow_detail_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=503,
            payload={
                "error": {
                    "code": "server_not_ready",
                    "message": "workflow service is not initialized",
                }
            },
            headers={"content-type": "application/json"},
        )

    build_workflow_detail_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workflow_detail_resource_response(
            server,
            workspace_id,
            workflow_instance_id,
        )
    finally:
        build_workflow_detail_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_create_server_uses_provided_runtime_and_workflow_service_factory() -> None:
    settings = make_settings()
    sentinel_runtime = object()
    sentinel_factory = object()

    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=sentinel_runtime,
        workflow_service_factory=sentinel_factory,
    )

    assert isinstance(server, CtxLedgerServer)
    assert server.runtime is sentinel_runtime
    assert server.workflow_service_factory is sentinel_factory


def test_create_server_builds_default_runtime_and_factory_when_omitted() -> None:
    settings = make_settings()

    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
    )

    assert isinstance(server, CtxLedgerServer)
    assert server.runtime is not None
    assert server.workflow_service_factory is not None


def test_build_workspace_resume_resource_response_uow_branch_returns_no_workflow() -> None:
    workspace_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(workspace_id=workspace_id)
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: None,
                list_by_workspace_id=lambda _workspace_id, *, limit: (),
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())

    response = build_workspace_resume_resource_response(server, workspace_id)

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"no workflow is available for workspace '{workspace_id}'",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_uses_latest_when_running_missing() -> (
    None
):
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            latest_workflow = SimpleNamespace(workflow_instance_id=workflow_instance_id)
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(workspace_id=workspace_id)
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: latest_workflow,
                list_by_workspace_id=lambda _workspace_id, *, limit: (latest_workflow,),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda _workflow_instance_id: None,
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workflow_instance_id": str(workflow_instance_id),
        },
        "selection": {
            "strategy": "running_or_latest",
            "candidate_count": 1,
            "selected_workflow_instance_id": str(workflow_instance_id),
            "running_workflow_instance_id": None,
            "latest_workflow_instance_id": str(workflow_instance_id),
            "selected_reason": "selected latest workflow because no running workflow was available",
            "latest_deprioritized": False,
            "signals": {
                "running_workflow_available": False,
                "latest_workflow_terminal": False,
                "non_terminal_candidate_available": True,
                "selected_equals_latest": True,
                "selected_equals_running": False,
                "latest_ticket_detour_like": False,
                "latest_checkpoint_detour_like": False,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": False,
                "ranking_details_present": True,
                "explanations_present": False,
            },
            "explanations": [],
            "ranking_details": [
                {
                    "workflow_instance_id": str(workflow_instance_id),
                    "is_latest": True,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": False,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 35,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "latest_candidate",
                            "message": "candidate is the latest workflow considered for resume",
                        },
                        {
                            "code": "selected_candidate",
                            "message": "candidate was selected after applying workspace resume heuristics",
                        },
                    ],
                    "selected": True,
                },
            ],
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_prefers_running_workflow() -> None:
    workspace_id = uuid4()
    running_workflow_instance_id = uuid4()
    latest_workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            running_workflow = SimpleNamespace(workflow_instance_id=running_workflow_instance_id)
            latest_workflow = SimpleNamespace(workflow_instance_id=latest_workflow_instance_id)
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(workspace_id=workspace_id)
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: running_workflow,
                get_latest_by_workspace_id=lambda _workspace_id: latest_workflow,
                list_by_workspace_id=lambda _workspace_id, *, limit: (
                    latest_workflow,
                    running_workflow,
                ),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda _workflow_instance_id: None,
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == running_workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(running_workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workflow_instance_id": str(running_workflow_instance_id),
        },
        "selection": {
            "strategy": "running_or_latest",
            "candidate_count": 2,
            "selected_workflow_instance_id": str(running_workflow_instance_id),
            "running_workflow_instance_id": str(running_workflow_instance_id),
            "latest_workflow_instance_id": str(latest_workflow_instance_id),
            "selected_reason": "selected running workflow for workspace resume",
            "latest_deprioritized": True,
            "signals": {
                "running_workflow_available": True,
                "latest_workflow_terminal": False,
                "non_terminal_candidate_available": True,
                "selected_equals_latest": False,
                "selected_equals_running": True,
                "latest_ticket_detour_like": False,
                "latest_checkpoint_detour_like": False,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": False,
                "ranking_details_present": True,
                "explanations_present": False,
            },
            "explanations": [],
            "ranking_details": [
                {
                    "workflow_instance_id": str(latest_workflow_instance_id),
                    "is_latest": True,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": False,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 35,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "latest_candidate",
                            "message": "candidate is the latest workflow considered for resume",
                        },
                    ],
                    "selected": False,
                },
                {
                    "workflow_instance_id": str(running_workflow_instance_id),
                    "is_latest": False,
                    "is_running": True,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": False,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 135,
                    "reason_list": [
                        {
                            "code": "running_workflow_priority",
                            "message": "running workflows are prioritized for continuation",
                            "impact": 100,
                        },
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "selected_candidate",
                            "message": "candidate was selected after applying workspace resume heuristics",
                        },
                    ],
                    "selected": True,
                },
            ],
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_surfaces_resumability_explanations_for_latest_selected_candidate() -> (
    None
):
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            latest_workflow = SimpleNamespace(
                workflow_instance_id=workflow_instance_id,
                status="running",
                ticket_id="TASK-PRIMARY-RESUME-HTTP-1",
                latest_attempt=SimpleNamespace(status="running"),
            )
            latest_checkpoint = SimpleNamespace(
                summary="Resume primary workflow implementation",
                step_name="implement_task_recall",
                checkpoint_json={},
            )
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(workspace_id=workspace_id)
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: latest_workflow,
                list_by_workspace_id=lambda _workspace_id, *, limit: (latest_workflow,),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda _workflow_instance_id: latest_checkpoint,
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workflow_instance_id": str(workflow_instance_id),
        },
        "selection": {
            "strategy": "running_or_latest",
            "candidate_count": 1,
            "selected_workflow_instance_id": str(workflow_instance_id),
            "running_workflow_instance_id": None,
            "latest_workflow_instance_id": str(workflow_instance_id),
            "selected_reason": "selected latest workflow because no running workflow was available",
            "latest_deprioritized": False,
            "signals": {
                "running_workflow_available": False,
                "latest_workflow_terminal": False,
                "non_terminal_candidate_available": True,
                "selected_equals_latest": True,
                "selected_equals_running": False,
                "latest_ticket_detour_like": False,
                "latest_checkpoint_detour_like": False,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": False,
                "ranking_details_present": True,
                "explanations_present": True,
            },
            "explanations": [
                {
                    "code": "latest_attempt_present",
                    "message": "candidate has a latest attempt signal that improves resumability confidence",
                },
                {
                    "code": "latest_checkpoint_present",
                    "message": "candidate has checkpoint history that improves resumability confidence",
                },
            ],
            "ranking_details": [
                {
                    "workflow_instance_id": str(workflow_instance_id),
                    "is_latest": True,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": True,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": True,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 45,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "latest_attempt_present_bonus",
                            "message": "candidate has a latest attempt signal available",
                            "impact": 5,
                        },
                        {
                            "code": "latest_checkpoint_present_bonus",
                            "message": "candidate has checkpoint history for resumability",
                            "impact": 5,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "latest_candidate",
                            "message": "candidate is the latest workflow considered for resume",
                        },
                        {
                            "code": "selected_candidate",
                            "message": "candidate was selected after applying workspace resume heuristics",
                        },
                    ],
                    "selected": True,
                },
            ],
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_prefers_non_terminal_candidate_over_latest_terminal() -> (
    None
):
    workspace_id = uuid4()
    older_non_terminal_workflow_instance_id = uuid4()
    latest_terminal_workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            latest_terminal_workflow = SimpleNamespace(
                workflow_instance_id=latest_terminal_workflow_instance_id,
                status="completed",
            )
            older_non_terminal_workflow = SimpleNamespace(
                workflow_instance_id=older_non_terminal_workflow_instance_id,
                status="running",
            )
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(workspace_id=workspace_id)
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: latest_terminal_workflow,
                list_by_workspace_id=lambda _workspace_id, *, limit: (
                    latest_terminal_workflow,
                    older_non_terminal_workflow,
                ),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda _workflow_instance_id: None,
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == older_non_terminal_workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(older_non_terminal_workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workflow_instance_id": str(older_non_terminal_workflow_instance_id),
        },
        "selection": {
            "strategy": "running_or_latest",
            "candidate_count": 2,
            "selected_workflow_instance_id": str(older_non_terminal_workflow_instance_id),
            "running_workflow_instance_id": None,
            "latest_workflow_instance_id": str(latest_terminal_workflow_instance_id),
            "selected_reason": "selected non-terminal workflow candidate instead of latest terminal workflow",
            "latest_deprioritized": True,
            "signals": {
                "running_workflow_available": False,
                "latest_workflow_terminal": True,
                "non_terminal_candidate_available": True,
                "selected_equals_latest": False,
                "selected_equals_running": False,
                "latest_ticket_detour_like": False,
                "latest_checkpoint_detour_like": False,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": False,
                "ranking_details_present": True,
                "explanations_present": True,
            },
            "explanations": [
                {
                    "code": "latest_workflow_terminal",
                    "message": "latest workflow was terminal",
                },
                {
                    "code": "selected_non_terminal_candidate",
                    "message": "selected a non-terminal candidate instead",
                },
            ],
            "ranking_details": [
                {
                    "workflow_instance_id": str(latest_terminal_workflow_instance_id),
                    "is_latest": True,
                    "is_running": False,
                    "workflow_terminal": True,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": False,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": -15,
                    "reason_list": [
                        {
                            "code": "workflow_terminal_penalty",
                            "message": "terminal workflows are less suitable for continuation",
                            "impact": -25,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "latest_candidate",
                            "message": "candidate is the latest workflow considered for resume",
                        },
                    ],
                    "selected": False,
                },
                {
                    "workflow_instance_id": str(older_non_terminal_workflow_instance_id),
                    "is_latest": False,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": False,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 35,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "selected_candidate",
                            "message": "candidate was selected after applying workspace resume heuristics",
                        },
                    ],
                    "selected": True,
                },
            ],
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workspace_resume_resource_response_uow_branch_prefers_non_detour_like_ticket_over_latest_detour_like_ticket() -> (
    None
):
    workspace_id = uuid4()
    mainline_workflow_instance_id = uuid4()
    latest_detour_workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            latest_detour_workflow = SimpleNamespace(
                workflow_instance_id=latest_detour_workflow_instance_id,
                status="running",
                ticket_id="COVERAGE-DET-1",
            )
            mainline_workflow = SimpleNamespace(
                workflow_instance_id=mainline_workflow_instance_id,
                status="running",
                ticket_id="TASK-PRIMARY-1",
            )
            self.workspaces = SimpleNamespace(
                get_by_id=lambda _workspace_id: SimpleNamespace(workspace_id=workspace_id)
            )
            self.workflow_instances = SimpleNamespace(
                get_running_by_workspace_id=lambda _workspace_id: None,
                get_latest_by_workspace_id=lambda _workspace_id: latest_detour_workflow,
                list_by_workspace_id=lambda _workspace_id, *, limit: (
                    latest_detour_workflow,
                    mainline_workflow,
                ),
            )
            self.workflow_checkpoints = SimpleNamespace(
                get_latest_by_workflow_id=lambda workflow_instance_id: {
                    latest_detour_workflow_instance_id: SimpleNamespace(
                        summary="Coverage follow-up for workspace resume selection",
                        step_name="coverage_followup",
                        checkpoint_json={},
                    ),
                    mainline_workflow_instance_id: SimpleNamespace(
                        summary="Resume primary task recall implementation",
                        step_name="implement_task_recall",
                        checkpoint_json={},
                    ),
                }.get(workflow_instance_id),
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workspace_resume_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == mainline_workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(mainline_workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workspace_resume_resource_response(server, workspace_id)
    finally:
        build_workspace_resume_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/resume",
        "resource": {
            "workflow_instance_id": str(mainline_workflow_instance_id),
        },
        "selection": {
            "strategy": "running_or_latest",
            "candidate_count": 2,
            "selected_workflow_instance_id": str(mainline_workflow_instance_id),
            "running_workflow_instance_id": None,
            "latest_workflow_instance_id": str(latest_detour_workflow_instance_id),
            "selected_reason": "selected non-detour-like workflow candidate instead of latest detour-like workflow",
            "latest_deprioritized": True,
            "signals": {
                "running_workflow_available": False,
                "latest_workflow_terminal": False,
                "non_terminal_candidate_available": True,
                "selected_equals_latest": False,
                "selected_equals_running": False,
                "latest_ticket_detour_like": True,
                "latest_checkpoint_detour_like": True,
                "selected_ticket_detour_like": False,
                "selected_checkpoint_detour_like": False,
                "detour_override_applied": True,
                "ranking_details_present": True,
                "explanations_present": True,
            },
            "explanations": [
                {
                    "code": "latest_ticket_detour_like",
                    "message": "latest workflow ticket looked detour-like",
                },
                {
                    "code": "latest_checkpoint_detour_like",
                    "message": "latest workflow checkpoint looked detour-like",
                },
                {
                    "code": "selected_non_detour_candidate",
                    "message": "selected a non-detour-like candidate instead",
                },
                {
                    "code": "candidate_reason_details_available",
                    "message": "ranking details include candidate-level reasons for the selection outcome",
                },
            ],
            "ranking_details": [
                {
                    "workflow_instance_id": str(latest_detour_workflow_instance_id),
                    "is_latest": True,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": True,
                    "ticket_detour_like": True,
                    "checkpoint_detour_like": True,
                    "detour_like": True,
                    "score": 20,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "latest_checkpoint_present_bonus",
                            "message": "candidate has checkpoint history for resumability",
                            "impact": 5,
                        },
                        {
                            "code": "ticket_detour_like_penalty",
                            "message": "workflow ticket looked detour-like",
                            "impact": -10,
                        },
                        {
                            "code": "checkpoint_detour_like_penalty",
                            "message": "latest checkpoint looked detour-like",
                            "impact": -10,
                        },
                        {
                            "code": "latest_candidate",
                            "message": "candidate is the latest workflow considered for resume",
                        },
                    ],
                    "selected": False,
                },
                {
                    "workflow_instance_id": str(mainline_workflow_instance_id),
                    "is_latest": False,
                    "is_running": False,
                    "workflow_terminal": False,
                    "has_latest_attempt": False,
                    "latest_attempt_terminal": False,
                    "has_latest_checkpoint": True,
                    "ticket_detour_like": False,
                    "checkpoint_detour_like": False,
                    "detour_like": False,
                    "score": 40,
                    "reason_list": [
                        {
                            "code": "workflow_non_terminal_bonus",
                            "message": "non-terminal workflows are preferred for continuation",
                            "impact": 25,
                        },
                        {
                            "code": "latest_checkpoint_present_bonus",
                            "message": "candidate has checkpoint history for resumability",
                            "impact": 5,
                        },
                        {
                            "code": "mainline_like_bonus",
                            "message": "candidate looks aligned with the main task line",
                            "impact": 10,
                        },
                        {
                            "code": "selected_candidate",
                            "message": "candidate was selected after applying workspace resume heuristics",
                        },
                    ],
                    "selected": True,
                },
            ],
        },
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_propagates_non_success_workflow_response() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    resume_result = SimpleNamespace(
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
        ),
    )

    class ResumeResultWorkflowService:
        def __init__(self, resume_result: object) -> None:
            self.resume_result = resume_result

        def resume_workflow(self, data: object) -> object:
            return self.resume_result

    server = make_server()
    server.workflow_service = ResumeResultWorkflowService(resume_result)
    original_builder = build_workflow_detail_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=503,
            payload={
                "error": {
                    "code": "server_not_ready",
                    "message": "workflow service is not initialized",
                }
            },
            headers={"content-type": "application/json"},
        )

    build_workflow_detail_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workflow_detail_resource_response(
            server,
            workspace_id,
            workflow_instance_id,
        )
    finally:
        build_workflow_detail_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_uow_branch_returns_not_found() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workflow_instances = SimpleNamespace(get_by_id=lambda _workflow_instance_id: None)

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())

    response = build_workflow_detail_resource_response(
        server,
        workspace_id,
        workflow_instance_id,
    )

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": f"workflow '{workflow_instance_id}' was not found",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_uow_branch_returns_invalid_request_on_workspace_mismatch() -> (
    None
):
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workflow_instances = SimpleNamespace(
                get_by_id=lambda _workflow_instance_id: SimpleNamespace(
                    workflow_instance_id=workflow_instance_id,
                    workspace_id=other_workspace_id,
                )
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())

    response = build_workflow_detail_resource_response(
        server,
        workspace_id,
        workflow_instance_id,
    )

    assert response.status_code == 400
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "workflow instance does not belong to workspace",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_detail_resource_response_uow_branch_propagates_success() -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    class FakeUow:
        def __init__(self) -> None:
            self.workflow_instances = SimpleNamespace(
                get_by_id=lambda _workflow_instance_id: SimpleNamespace(
                    workflow_instance_id=workflow_instance_id,
                    workspace_id=workspace_id,
                )
            )

        def __enter__(self) -> "FakeUow":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    server = make_server()
    server.workflow_service = SimpleNamespace(_uow_factory=lambda: FakeUow())
    original_builder = build_workflow_detail_resource_response.__globals__[
        "build_workflow_resume_response"
    ]

    def fake_build_workflow_resume_response(_server: object, workflow_id: object) -> object:
        assert workflow_id == workflow_instance_id
        return SimpleNamespace(
            status_code=200,
            payload={"workflow_instance_id": str(workflow_instance_id)},
            headers={"content-type": "application/json"},
        )

    build_workflow_detail_resource_response.__globals__["build_workflow_resume_response"] = (
        fake_build_workflow_resume_response
    )
    try:
        response = build_workflow_detail_resource_response(
            server,
            workspace_id,
            workflow_instance_id,
        )
    finally:
        build_workflow_detail_resource_response.__globals__["build_workflow_resume_response"] = (
            original_builder
        )

    assert response.status_code == 200
    assert response.payload == {
        "uri": f"workspace://{workspace_id}/workflow/{workflow_instance_id}",
        "resource": {
            "workflow_instance_id": str(workflow_instance_id),
        },
    }
    assert response.headers == {"content-type": "application/json"}
