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
