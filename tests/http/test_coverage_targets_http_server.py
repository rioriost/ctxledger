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


def test_create_server_builds_default_runtime_and_factory_when_omitted() -> None:
    settings = make_settings()

    server = create_server(
        settings,
        db_health_checker=FakeDatabaseHealthChecker(),
    )

    assert isinstance(server, CtxLedgerServer)
    assert server.runtime is not None
    assert server.workflow_service_factory is not None


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
