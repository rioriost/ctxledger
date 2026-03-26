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
