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


def test_build_workflow_detail_resource_response_propagates_non_success_workflow_response_uow_branch() -> (
    None
):
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
