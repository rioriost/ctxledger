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
                "relation_type": "summarizes",
                "selection_route": "graph_summary_auxiliary",
                "explainability_scope": "readiness",
                "refresh_command": "ctxledger refresh-age-summary-graph",
                "read_path_scope": "narrow_auxiliary_summary_member_traversal",
                "readiness_state": "unknown",
                "stale": False,
                "degraded": False,
                "operator_action": "inspect_age_graph_readiness",
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
