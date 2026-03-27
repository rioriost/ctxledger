from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ctxledger.memory.service import GetContextResponse, MemoryFeature
from ctxledger.runtime.http_handlers import (
    build_runtime_introspection_http_handler,
    build_workflow_resume_http_handler,
    parse_workflow_resume_request_path,
)
from ctxledger.runtime.http_runtime import (
    HttpRuntimeAdapter,
    build_http_runtime_adapter,
)
from ctxledger.runtime.introspection import (
    RuntimeIntrospection,
    collect_runtime_introspection,
)
from ctxledger.runtime.serializers import (
    serialize_runtime_introspection,
    serialize_runtime_introspection_collection,
    serialize_workflow_resume,
)
from ctxledger.runtime.server_responses import (
    _age_prototype_runtime_details,
    build_runtime_introspection_response,
)
from ctxledger.runtime.types import McpHttpResponse, WorkflowResumeResponse
from tests.support.server_test_support import (
    _EXPLICIT_NONE,
    FakeDatabaseHealthChecker,
    FakeRuntime,
    FakeWorkflowService,
    build_runtime_summary_payload,
    make_http_runtime,
    make_resume_fixture,
    make_server,
    make_settings,
)


def test_parse_workflow_resume_request_path_returns_uuid_for_valid_path() -> None:
    workflow_instance_id = uuid4()

    assert (
        parse_workflow_resume_request_path(f"/workflow-resume/{workflow_instance_id}")
        == workflow_instance_id
    )
    assert (
        parse_workflow_resume_request_path(f"/workflow-resume/{workflow_instance_id}?format=json")
        == workflow_instance_id
    )


def test_parse_workflow_resume_request_path_returns_none_for_invalid_path() -> None:
    assert parse_workflow_resume_request_path("") is None
    assert parse_workflow_resume_request_path("/") is None
    assert parse_workflow_resume_request_path("/workflow-resume") is None
    assert parse_workflow_resume_request_path("/workflow-resume/not-a-uuid") is None
    assert parse_workflow_resume_request_path("/other/endpoint") is None


def test_build_workflow_resume_http_handler_returns_success_response() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = make_server(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    handler = build_workflow_resume_http_handler(server)

    server.startup()

    response = handler(f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}")

    assert isinstance(response, WorkflowResumeResponse)
    assert response.status_code == 200
    assert response.payload == serialize_workflow_resume(resume)
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_http_handler_returns_not_found_for_invalid_path() -> None:
    settings = make_settings()
    server = make_server(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    handler = build_workflow_resume_http_handler(server)

    response = handler("/workflow-resume/not-a-uuid")

    assert isinstance(response, WorkflowResumeResponse)
    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": (
                "workflow resume endpoint requires /workflow-resume/{workflow_instance_id}"
            ),
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_workflow_resume_http_handler_returns_503_when_server_is_not_ready() -> None:
    settings = make_settings()
    server = make_server(settings=settings)
    handler = build_workflow_resume_http_handler(server)

    response = handler(f"/workflow-resume/{uuid4()}")

    assert isinstance(response, WorkflowResumeResponse)
    assert response.status_code == 503
    assert response.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_age_prototype_runtime_details_reports_enabled_ready_graph_state() -> None:
    settings = make_settings()
    settings = replace(
        settings,
        database=replace(
            settings.database,
            age_enabled=True,
            age_graph_name="ctxledger_memory",
        ),
    )
    health_checker = FakeDatabaseHealthChecker(
        age_available_value=True,
        age_graph_available_value=True,
    )
    server = make_server(
        settings=settings,
        db_health_checker=health_checker,
        runtime=FakeRuntime(),
    )

    details = _age_prototype_runtime_details(server)

    assert details == {
        "age_enabled": True,
        "age_graph_name": "ctxledger_memory",
        "observability_routes": [
            "/debug/runtime",
            "/debug/routes",
            "/debug/tools",
        ],
        "summary_graph_mirroring": {
            "enabled": True,
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
            "readiness_state": "ready",
            "stale": False,
            "degraded": False,
            "operator_action": "no_action_required",
            "age_available": True,
            "graph_status": "graph_ready",
            "ready": True,
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
        "age_available": True,
        "age_graph_status": "graph_ready",
    }
    assert health_checker.age_available_calls == 1
    assert health_checker.age_graph_status_calls == 1
    assert health_checker.requested_graph_names == ["ctxledger_memory"]


def test_age_prototype_runtime_details_reports_disabled_graph_state() -> None:
    settings = make_settings()
    health_checker = FakeDatabaseHealthChecker(
        age_available_value=False,
        age_graph_available_value=False,
    )
    server = make_server(
        settings=settings,
        db_health_checker=health_checker,
        runtime=FakeRuntime(),
    )

    details = _age_prototype_runtime_details(server)

    assert details == {
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
            "readiness_state": "degraded",
            "stale": False,
            "degraded": True,
            "operator_action": "verify_age_extension_and_database_image",
            "age_available": False,
            "graph_status": "age_unavailable",
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
        "age_available": False,
        "age_graph_status": "age_unavailable",
    }


def test_build_runtime_introspection_response_includes_age_prototype_details() -> None:
    settings = make_settings()
    settings = replace(
        settings,
        database=replace(
            settings.database,
            age_enabled=True,
            age_graph_name="ctxledger_memory",
        ),
    )
    server = make_server(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(
            age_available_value=True,
            age_graph_available_value=False,
        ),
        runtime=FakeRuntime(),
    )

    response = build_runtime_introspection_response(server)

    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload["age_prototype"] == {
        "age_enabled": True,
        "age_graph_name": "ctxledger_memory",
        "observability_routes": [
            "/debug/runtime",
            "/debug/routes",
            "/debug/tools",
        ],
        "summary_graph_mirroring": {
            "enabled": True,
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
            "readiness_state": "degraded",
            "stale": False,
            "degraded": True,
            "operator_action": "bootstrap_or_refresh_age_summary_graph",
            "age_available": True,
            "graph_status": "graph_unavailable",
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
        "age_available": True,
        "age_graph_status": "graph_unavailable",
    }
    assert "runtime" in response.payload


def test_age_prototype_runtime_details_readiness_payload_surfaces_explainability_fields() -> None:
    settings = make_settings()
    health_checker = FakeDatabaseHealthChecker(
        age_available_value=True,
        age_graph_available_value=True,
    )
    server = make_server(
        settings=settings,
        db_health_checker=health_checker,
        runtime=FakeRuntime(),
    )

    details = _age_prototype_runtime_details(server)

    assert details["summary_graph_mirroring"] == {
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
        "readiness_state": "ready",
        "stale": False,
        "degraded": False,
        "operator_action": "no_action_required",
        "age_available": True,
        "graph_status": "graph_ready",
        "ready": True,
    }


def test_age_prototype_runtime_details_uses_shared_age_readiness_helper_shape_without_health_checker() -> (
    None
):
    settings = make_settings()
    server = make_server(
        settings=settings,
        db_health_checker=_EXPLICIT_NONE,
        runtime=FakeRuntime(),
    )

    details = _age_prototype_runtime_details(server)

    assert details["summary_graph_mirroring"] == {
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
    }
    assert details["age_graph_status"] == "unknown"
    assert "age_available" not in details["summary_graph_mirroring"]


def test_age_prototype_runtime_details_shared_helper_shape_matches_ready_and_unknown_paths() -> (
    None
):
    ready_settings = make_settings()
    ready_server = make_server(
        settings=ready_settings,
        db_health_checker=FakeDatabaseHealthChecker(
            age_available_value=True,
            age_graph_available_value=True,
        ),
        runtime=FakeRuntime(),
    )

    ready_details = _age_prototype_runtime_details(ready_server)

    assert ready_details["summary_graph_mirroring"] == {
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
        "readiness_state": "ready",
        "stale": False,
        "degraded": False,
        "operator_action": "no_action_required",
        "age_available": True,
        "graph_status": "graph_ready",
        "ready": True,
    }

    unknown_settings = make_settings()
    unknown_server = make_server(
        settings=unknown_settings,
        db_health_checker=_EXPLICIT_NONE,
        runtime=FakeRuntime(),
    )

    unknown_details = _age_prototype_runtime_details(unknown_server)

    assert unknown_details["summary_graph_mirroring"] == {
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
    }
    assert "age_available" not in unknown_details["summary_graph_mirroring"]


def test_http_runtime_adapter_dispatches_registered_workflow_resume_handler() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = make_server(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    runtime = HttpRuntimeAdapter(settings)
    runtime.register_handler(
        "workflow_resume",
        build_workflow_resume_http_handler(server),
    )

    server.startup()

    response = runtime.dispatch(
        "workflow_resume",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}",
    )

    assert response.status_code == 200
    assert response.payload == serialize_workflow_resume(resume)
    assert response.headers == {"content-type": "application/json"}
    assert runtime.handler("workflow_resume") is not None
    assert runtime.introspection_endpoints() == ("workflow_resume",)


def test_http_runtime_adapter_returns_404_for_unregistered_route() -> None:
    settings = make_settings()
    runtime = HttpRuntimeAdapter(settings)

    response = runtime.dispatch("missing_route", f"/workflow-resume/{uuid4()}")

    assert response.status_code == 404
    assert response.payload == {
        "error": {
            "code": "route_not_found",
            "message": "no HTTP handler is registered for route 'missing_route'",
        }
    }
    assert response.headers == {"content-type": "application/json"}


def test_build_http_runtime_adapter_registers_workflow_resume_route() -> None:
    settings = make_settings()
    _, runtime, resume, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    assert isinstance(runtime, HttpRuntimeAdapter)
    assert runtime.introspection_endpoints() == (
        "mcp_rpc",
        "runtime_introspection",
        "runtime_routes",
        "runtime_tools",
        "workflow_resume",
    )

    response = runtime.dispatch(
        "workflow_resume",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}",
    )

    assert response.status_code == 200
    assert response.payload == serialize_workflow_resume(resume)


def test_dispatch_http_request_returns_dispatch_result_for_success() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    fake_workflow_service = FakeWorkflowService(resume)
    server = make_server(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
        workflow_service_factory=lambda: fake_workflow_service,
    )
    runtime = build_http_runtime_adapter(server)

    server.startup()

    result = runtime.dispatch(
        "workflow_resume",
        f"/workflow-resume/{resume.workflow_instance.workflow_instance_id}",
    )

    assert isinstance(result, WorkflowResumeResponse)
    assert result.status_code == 200
    assert result.payload == serialize_workflow_resume(resume)


def test_dispatch_http_request_returns_route_not_found_result() -> None:
    settings = make_settings()
    runtime = HttpRuntimeAdapter(settings)

    result = runtime.dispatch(
        "missing_route",
        f"/workflow-resume/{uuid4()}",
    )

    assert isinstance(result, WorkflowResumeResponse)
    assert result.status_code == 404
    assert result.payload == {
        "error": {
            "code": "route_not_found",
            "message": "no HTTP handler is registered for route 'missing_route'",
        }
    }


def test_dispatch_http_request_returns_error_result_for_handler_error_response() -> None:
    settings = make_settings()
    server = make_server(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=FakeRuntime(),
    )
    runtime = build_http_runtime_adapter(server)

    result = runtime.dispatch(
        "workflow_resume",
        f"/workflow-resume/{uuid4()}",
    )

    assert isinstance(result, WorkflowResumeResponse)
    assert result.status_code == 503
    assert result.payload == {
        "error": {
            "code": "server_not_ready",
            "message": "workflow service is not initialized",
        }
    }


def test_http_runtime_adapter_introspect_returns_registered_routes() -> None:
    settings = make_settings()
    runtime = HttpRuntimeAdapter(settings)
    runtime.register_handler(
        "workflow_resume",
        lambda path: WorkflowResumeResponse(
            status_code=200,
            payload={"path": path},
            headers={"content-type": "application/json"},
        ),
    )

    introspection = runtime.introspect()

    assert isinstance(introspection, RuntimeIntrospection)
    assert introspection.transport == "http"
    assert introspection.routes == runtime.introspection_endpoints()
    assert introspection.tools == (
        "memory_get_context",
        "memory_remember_episode",
        "memory_search",
        "workflow_checkpoint",
        "workflow_complete",
        "workflow_resume",
        "workflow_start",
        "workspace_register",
    )
    assert introspection.resources == (
        "workspace://{workspace_id}/resume",
        "workspace://{workspace_id}/workflow/{workflow_instance_id}",
    )


def test_collect_runtime_introspection_returns_empty_tuple_for_none() -> None:
    assert collect_runtime_introspection(None) == ()


def test_collect_runtime_introspection_returns_http_runtime_introspection() -> None:
    settings = make_settings()
    runtime = HttpRuntimeAdapter(settings)
    runtime.register_handler(
        "workflow_resume",
        lambda path: WorkflowResumeResponse(
            status_code=200,
            payload={"path": path},
            headers={"content-type": "application/json"},
        ),
    )

    introspections = collect_runtime_introspection(runtime)

    assert introspections == (
        RuntimeIntrospection(
            transport="http",
            routes=("workflow_resume",),
            tools=(
                "memory_get_context",
                "memory_remember_episode",
                "memory_search",
                "workflow_checkpoint",
                "workflow_complete",
                "workflow_resume",
                "workflow_start",
                "workspace_register",
            ),
            resources=(
                "workspace://{workspace_id}/resume",
                "workspace://{workspace_id}/workflow/{workflow_instance_id}",
            ),
        ),
    )


def test_serialize_runtime_introspection_returns_json_ready_payload() -> None:
    introspection = RuntimeIntrospection(
        transport="http",
        routes=("workflow_resume",),
        tools=(),
    )

    payload = serialize_runtime_introspection(introspection)

    assert payload == {
        "transport": "http",
        "routes": ["workflow_resume"],
        "tools": [],
        "resources": [],
    }


def test_serialize_runtime_introspection_collection_returns_json_ready_payloads() -> None:
    introspections = (
        RuntimeIntrospection(
            transport="http",
            routes=("workflow_resume",),
            tools=(),
            resources=(),
        ),
    )

    payload = serialize_runtime_introspection_collection(introspections)

    assert payload == [
        {
            "transport": "http",
            "routes": ["workflow_resume"],
            "tools": [],
            "resources": [],
        },
    ]


def test_build_runtime_introspection_response_returns_http_payload_for_single_runtime() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    response = build_runtime_introspection_response(server)

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "runtime": build_runtime_summary_payload(),
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
                "readiness_state": "ready",
                "stale": False,
                "degraded": False,
                "operator_action": "no_action_required",
                "age_available": True,
                "graph_status": "graph_ready",
                "ready": True,
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
            "age_available": True,
            "age_graph_status": "graph_ready",
        },
    }


def test_build_runtime_introspection_response_exposes_readiness_explainability_fields() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    response = build_runtime_introspection_response(server)

    summary_graph_mirroring = response.payload["age_prototype"]["summary_graph_mirroring"]
    assert summary_graph_mirroring["relation_type"] == "summarizes"
    assert summary_graph_mirroring["selection_route"] == "graph_summary_auxiliary"
    assert summary_graph_mirroring["explainability_scope"] == "readiness"
    assert summary_graph_mirroring["refresh_command"] == "ctxledger refresh-age-summary-graph"
    assert summary_graph_mirroring["read_path_scope"] == "narrow_auxiliary_summary_member_traversal"


def test_build_runtime_introspection_response_returns_empty_runtime_list_when_runtime_is_missing() -> (
    None
):
    settings = make_settings()
    server = make_server(
        settings=settings,
        db_health_checker=FakeDatabaseHealthChecker(),
        runtime=None,
    )

    response = build_runtime_introspection_response(server)

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "runtime": [],
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
                "readiness_state": "ready",
                "stale": False,
                "degraded": False,
                "operator_action": "no_action_required",
                "age_available": True,
                "graph_status": "graph_ready",
                "ready": True,
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
            "age_available": True,
            "age_graph_status": "graph_ready",
        },
    }


def test_build_runtime_introspection_http_handler_returns_success_response() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )
    handler = build_runtime_introspection_http_handler(server)

    response = handler("/debug/runtime")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "runtime": build_runtime_summary_payload(),
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
                "readiness_state": "ready",
                "stale": False,
                "degraded": False,
                "operator_action": "no_action_required",
                "age_available": True,
                "graph_status": "graph_ready",
                "ready": True,
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
            "age_available": True,
            "age_graph_status": "graph_ready",
        },
    }


def test_build_runtime_introspection_http_handler_returns_not_found_for_invalid_path() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )
    handler = build_runtime_introspection_http_handler(server)

    response = handler("/debug/routes")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 404
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "runtime introspection endpoint requires /debug/runtime",
        }
    }


def test_build_http_runtime_adapter_omits_runtime_introspection_route_when_debug_endpoints_are_disabled() -> (
    None
):
    settings = make_settings()
    settings = replace(
        settings,
        debug=settings.debug.__class__(enabled=False),
    )
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)
    assert server.runtime.handler("runtime_introspection") is None
    assert server.runtime.introspection_endpoints() == (
        "mcp_rpc",
        "workflow_resume",
    )


def test_http_runtime_adapter_dispatches_registered_runtime_introspection_handler() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )
    assert isinstance(server.runtime, HttpRuntimeAdapter)

    response = server.runtime.dispatch(
        "runtime_introspection",
        "/debug/runtime",
    )

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "runtime": build_runtime_summary_payload(),
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
                "readiness_state": "ready",
                "stale": False,
                "degraded": False,
                "operator_action": "no_action_required",
                "age_available": True,
                "graph_status": "graph_ready",
                "ready": True,
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
            "age_available": True,
            "age_graph_status": "graph_ready",
        },
    }


def test_build_debug_routes_http_handler_returns_runtime_routes_only() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    handler = server.runtime.require_handler("runtime_routes")
    response = handler("/debug/routes")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "routes": [
            {
                "transport": "http",
                "routes": [
                    "mcp_rpc",
                    "runtime_introspection",
                    "runtime_routes",
                    "runtime_tools",
                    "workflow_resume",
                ],
            }
        ]
    }


def test_build_debug_routes_http_handler_returns_not_found_for_invalid_path() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    handler = server.runtime.require_handler("runtime_routes")
    response = handler("/debug/runtime")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 404
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "runtime routes endpoint requires /debug/routes",
        }
    }


def test_build_http_runtime_adapter_omits_runtime_routes_handler_when_debug_endpoints_are_disabled() -> (
    None
):
    settings = make_settings()
    settings = replace(
        settings,
        debug=settings.debug.__class__(enabled=False),
    )
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)
    assert server.runtime.handler("runtime_routes") is None
    assert server.runtime.introspection_endpoints() == (
        "mcp_rpc",
        "workflow_resume",
    )


def test_build_debug_tools_http_handler_returns_runtime_tools_only() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    handler = server.runtime.require_handler("runtime_tools")
    response = handler("/debug/tools")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "tools": [
            {
                "transport": "http",
                "tools": [
                    "memory_get_context",
                    "memory_remember_episode",
                    "memory_search",
                    "workflow_checkpoint",
                    "workflow_complete",
                    "workflow_resume",
                    "workflow_start",
                    "workspace_register",
                ],
            }
        ]
    }


def test_build_debug_tools_http_handler_returns_http_only_empty_tools() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    handler = server.runtime.require_handler("runtime_tools")
    response = handler("/debug/tools")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "tools": [
            {
                "transport": "http",
                "tools": [
                    "memory_get_context",
                    "memory_remember_episode",
                    "memory_search",
                    "workflow_checkpoint",
                    "workflow_complete",
                    "workflow_resume",
                    "workflow_start",
                    "workspace_register",
                ],
            }
        ]
    }


def test_build_debug_tools_http_handler_returns_not_found_for_invalid_path() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    handler = server.runtime.require_handler("runtime_tools")
    response = handler("/debug/routes")

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 404
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "runtime tools endpoint requires /debug/tools",
        }
    }


def test_build_http_runtime_adapter_omits_runtime_tools_handler_when_debug_endpoints_are_disabled() -> (
    None
):
    settings = make_settings()
    settings = replace(
        settings,
        debug=settings.debug.__class__(enabled=False),
    )
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    assert isinstance(server.runtime, HttpRuntimeAdapter)
    assert server.runtime.handler("runtime_tools") is None
    assert server.runtime.introspection_endpoints() == (
        "mcp_rpc",
        "workflow_resume",
    )


def test_http_runtime_adapter_dispatches_registered_debug_routes_handler() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    response = server.runtime.dispatch(
        "runtime_routes",
        "/debug/routes",
    )

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "routes": [
            {
                "transport": "http",
                "routes": [
                    "mcp_rpc",
                    "runtime_introspection",
                    "runtime_routes",
                    "runtime_tools",
                    "workflow_resume",
                ],
            }
        ]
    }


def test_http_runtime_adapter_dispatches_registered_debug_tools_handler() -> None:
    settings = make_settings()
    server, _, _, _ = make_http_runtime(
        settings=settings,
    )

    response = server.runtime.dispatch(
        "runtime_tools",
        "/debug/tools",
    )

    assert response.__class__.__name__ == "RuntimeIntrospectionResponse"
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "tools": [
            {
                "transport": "http",
                "tools": [
                    "memory_get_context",
                    "memory_remember_episode",
                    "memory_search",
                    "workflow_checkpoint",
                    "workflow_complete",
                    "workflow_resume",
                    "workflow_start",
                    "workspace_register",
                ],
            }
        ]
    }


def test_http_mcp_route_supports_initialize_over_http() -> None:
    settings = make_settings()
    _, runtime, _, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        (
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{'
            '"protocolVersion":"2024-11-05",'
            '"capabilities":{},'
            '"clientInfo":{"name":"test-client","version":"0.1.0"}'
            "}}"
        ),
    )

    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
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


def test_http_mcp_route_supports_tools_list_over_http() -> None:
    settings = make_settings()
    _, runtime, _, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}',
    )

    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}

    assert response.payload["jsonrpc"] == "2.0"
    assert response.payload["id"] == 2
    tools = response.payload["result"]["tools"]
    tool_names = [tool["name"] for tool in tools]

    assert tool_names == [
        "memory_get_context",
        "memory_remember_episode",
        "memory_search",
        "workflow_checkpoint",
        "workflow_complete",
        "workflow_resume",
        "workflow_start",
        "workspace_register",
    ]

    workspace_register_tool = next(tool for tool in tools if tool["name"] == "workspace_register")
    assert workspace_register_tool["inputSchema"] == {
        "type": "object",
        "properties": {
            "repo_url": {
                "type": "string",
                "minLength": 1,
                "description": "Repository URL for the workspace.",
            },
            "canonical_path": {
                "type": "string",
                "minLength": 1,
                "description": "Canonical local filesystem path for the workspace checkout.",
            },
            "default_branch": {
                "type": "string",
                "minLength": 1,
                "description": "Default branch name for the workspace repository.",
            },
            "workspace_id": {
                "type": "string",
                "format": "uuid",
                "description": "Existing workspace identity for explicit update operations.",
            },
            "metadata": {
                "type": "object",
                "description": "Optional workspace metadata.",
                "additionalProperties": True,
            },
        },
        "required": ["repo_url", "canonical_path", "default_branch"],
        "additionalProperties": False,
    }


def test_http_mcp_route_supports_tools_call_over_http() -> None:
    settings = make_settings()
    _, runtime, resume, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        (
            '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{'
            '"name":"workflow_resume",'
            f'"arguments":{{"workflow_instance_id":"{resume.workflow_instance.workflow_instance_id}"}}'
            "}}"
        ),
    )

    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload["jsonrpc"] == "2.0"
    assert response.payload["id"] == 3
    result = response.payload["result"]
    assert result["content"][0]["type"] == "text"
    payload = json.loads(result["content"][0]["text"])
    assert payload["ok"] is True
    assert payload["result"]["workflow"]["workflow_instance_id"] == str(
        resume.workflow_instance.workflow_instance_id
    )


def test_http_mcp_route_requires_json_rpc_body() -> None:
    settings = make_settings()
    _, runtime, _, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    response = runtime.dispatch("mcp_rpc", "/mcp")

    assert response.status_code == 400
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "error": {
            "code": "invalid_request",
            "message": "HTTP MCP endpoint requires a JSON-RPC request body",
        }
    }


def test_http_mcp_route_requires_configured_mcp_path() -> None:
    settings = make_settings()
    _, runtime, _, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    response = runtime.dispatch(
        "mcp_rpc",
        "/not-mcp",
        '{"jsonrpc":"2.0","id":4,"method":"tools/list","params":{}}',
    )

    assert response.status_code == 404
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "error": {
            "code": "not_found",
            "message": "MCP endpoint requires /mcp",
        }
    }


def test_http_mcp_rpc_initialize_returns_success_payload() -> None:
    settings = make_settings()
    _, runtime, _, _ = make_http_runtime(
        settings=settings,
    )

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        body=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            }
        ),
    )

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "ctxledger",
                "version": "0.1.0",
            },
            "capabilities": {
                "tools": {},
                "resources": {},
            },
        },
    }


def test_http_mcp_rpc_tools_list_returns_registered_tools_with_input_schemas() -> None:
    settings = make_settings()
    _, runtime, _, _ = make_http_runtime(
        settings=settings,
    )

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        body=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
        ),
    )

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    result = response.payload["result"]
    tools = {tool["name"]: tool for tool in result["tools"]}

    assert "workspace_register" in tools
    assert tools["workspace_register"]["inputSchema"]["required"] == [
        "repo_url",
        "canonical_path",
        "default_branch",
    ]
    assert tools["workflow_start"]["inputSchema"]["properties"]["workspace_id"]["format"] == "uuid"
    assert (
        tools["memory_get_context"]["inputSchema"]["properties"]["include_summaries"]["type"]
        == "boolean"
    )
    assert (
        tools["memory_get_context"]["inputSchema"]["properties"]["primary_only"]["type"]
        == "boolean"
    )


def test_http_mcp_rpc_tools_call_returns_memory_get_context_summary_first_payload() -> None:
    settings = make_settings()
    workflow_id = uuid4()
    episode_id = uuid4()
    memory_summary_id = uuid4()
    member_memory_id = uuid4()
    created_at = datetime(2024, 10, 12, 4, 5, 6, tzinfo=UTC)

    _, runtime, _, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    runtime._server = runtime._server  # keep explicit local reference shape stable
    runtime._server.workflow_service._uow_factory = lambda: None  # type: ignore[attr-defined]

    memory_service = GetContextResponse(
        feature=MemoryFeature.GET_CONTEXT,
        implemented=True,
        message="Episode-oriented memory context retrieved successfully.",
        status="ok",
        available_in_version="0.2.0",
        timestamp=created_at,
        episodes=(),
        details={
            "episodes_returned": 0,
            "summary_selection_applied": True,
            "summary_selection_kind": "memory_summary_first",
            "retrieval_routes_present": ["summary_first"],
            "primary_retrieval_routes_present": ["summary_first"],
            "remember_path_relation_reasons": [
                "checkpoint_to_completion_support",
                "summary_member_support",
            ],
            "remember_path_relation_reason_primary": "checkpoint_to_completion_support",
            "readiness_explainability": {
                "graph_summary_auxiliary": {
                    "selection_route": "graph_summary_auxiliary",
                    "relation_type": "summarizes",
                    "source_episode_count": 1,
                    "source_memory_count": 1,
                    "derived_memory_count": 1,
                    "derived_graph_labels": [
                        "memory_summary",
                        "memory_item",
                        "summarizes",
                    ],
                    "canonical_source": [
                        "memory_summaries",
                        "memory_summary_memberships",
                    ],
                    "refresh_command": "ctxledger refresh-age-summary-graph",
                    "read_path_scope": "narrow_auxiliary_summary_member_traversal",
                },
                "summary_graph_mirroring": {
                    "selection_route": "graph_summary_auxiliary",
                    "relation_type": "summarizes",
                    "source_episode_count": 1,
                    "source_memory_count": 1,
                    "derived_memory_count": 1,
                    "derived_graph_labels": [
                        "memory_summary",
                        "memory_item",
                        "summarizes",
                    ],
                    "canonical_source": [
                        "memory_summaries",
                        "memory_summary_memberships",
                    ],
                    "refresh_command": "ctxledger refresh-age-summary-graph",
                    "read_path_scope": "narrow_auxiliary_summary_member_traversal",
                    "ready": True,
                },
            },
            "memory_context_groups": [
                {
                    "scope": "summary",
                    "scope_id": None,
                    "group_id": "summary:memory_summary_first",
                    "parent_scope": "workflow_instance",
                    "parent_scope_id": str(workflow_id),
                    "selection_kind": "memory_summary_first",
                    "selection_route": "summary_first",
                    "child_episode_ids": [str(episode_id)],
                    "child_episode_count": 1,
                    "child_episode_ordering": "returned_episode_order",
                    "child_episode_groups_emitted": True,
                    "child_episode_groups_emission_reason": "memory_items_enabled",
                    "summaries": [
                        {
                            "memory_summary_id": str(memory_summary_id),
                            "episode_id": str(episode_id),
                            "workflow_instance_id": str(workflow_id),
                            "summary_text": "Canonical summary selected first",
                            "summary_kind": "episode_summary",
                            "metadata": {"kind": "canonical"},
                            "member_memory_count": 1,
                            "member_memory_ids": [str(member_memory_id)],
                            "member_memory_items": [
                                {
                                    "memory_id": str(member_memory_id),
                                    "workspace_id": str(workflow_id),
                                    "episode_id": str(episode_id),
                                    "type": "episode_note",
                                    "provenance": "episode",
                                    "content": "Expanded member memory item",
                                    "metadata": {"kind": "member"},
                                    "created_at": created_at.isoformat(),
                                    "updated_at": created_at.isoformat(),
                                }
                            ],
                        }
                    ],
                }
            ],
            "summaries": [
                {
                    "memory_summary_id": str(memory_summary_id),
                    "episode_id": str(episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "summary_text": "Canonical summary selected first",
                    "summary_kind": "episode_summary",
                    "metadata": {"kind": "canonical"},
                    "member_memory_count": 1,
                    "member_memory_ids": [str(member_memory_id)],
                    "member_memory_items": [
                        {
                            "memory_id": str(member_memory_id),
                            "workspace_id": str(workflow_id),
                            "episode_id": str(episode_id),
                            "type": "episode_note",
                            "provenance": "episode",
                            "content": "Expanded member memory item",
                            "metadata": {"kind": "member"},
                            "created_at": created_at.isoformat(),
                            "updated_at": created_at.isoformat(),
                        }
                    ],
                }
            ],
        },
    )

    runtime._server.workflow_service = runtime._server.workflow_service  # type: ignore[attr-defined]

    from ctxledger.runtime import http_runtime as http_runtime_module

    original_builder = http_runtime_module.build_workflow_backed_memory_service

    class FakeMemoryService:
        def __init__(self) -> None:
            self.calls: list[object] = []

        def get_context(self, request: object) -> GetContextResponse:
            self.calls.append(request)
            return memory_service

    fake_memory_service = FakeMemoryService()
    http_runtime_module.build_workflow_backed_memory_service = lambda server: fake_memory_service

    try:
        response = runtime.dispatch(
            "mcp_rpc",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "memory_get_context",
                        "arguments": {
                            "workflow_instance_id": str(workflow_id),
                            "limit": 10,
                            "include_episodes": True,
                            "include_memory_items": True,
                            "include_summaries": True,
                        },
                    },
                }
            ),
        )
    finally:
        http_runtime_module.build_workflow_backed_memory_service = original_builder

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload["jsonrpc"] == "2.0"
    assert response.payload["id"] == 3
    result = response.payload["result"]
    assert result["content"][0]["type"] == "text"
    payload = json.loads(result["content"][0]["text"])

    assert payload["ok"] is True
    assert payload["result"]["feature"] == "memory_get_context"
    assert payload["result"]["details"]["summary_selection_applied"] is True
    assert payload["result"]["details"]["summary_selection_kind"] == "memory_summary_first"
    assert payload["result"]["details"]["retrieval_routes_present"] == ["summary_first"]
    assert payload["result"]["details"]["primary_retrieval_routes_present"] == ["summary_first"]
    assert payload["result"]["details"]["remember_path_relation_reasons"] == [
        "checkpoint_to_completion_support",
        "summary_member_support",
    ]
    assert (
        payload["result"]["details"]["remember_path_relation_reason_primary"]
        == "checkpoint_to_completion_support"
    )
    assert payload["result"]["details"]["readiness_explainability"] == {
        "graph_summary_auxiliary": {
            "selection_route": "graph_summary_auxiliary",
            "relation_type": "summarizes",
            "source_episode_count": 1,
            "source_memory_count": 1,
            "derived_memory_count": 1,
            "derived_graph_labels": [
                "memory_summary",
                "memory_item",
                "summarizes",
            ],
            "canonical_source": [
                "memory_summaries",
                "memory_summary_memberships",
            ],
            "refresh_command": "ctxledger refresh-age-summary-graph",
            "read_path_scope": "narrow_auxiliary_summary_member_traversal",
        },
        "summary_graph_mirroring": {
            "selection_route": "graph_summary_auxiliary",
            "relation_type": "summarizes",
            "source_episode_count": 1,
            "source_memory_count": 1,
            "derived_memory_count": 1,
            "derived_graph_labels": [
                "memory_summary",
                "memory_item",
                "summarizes",
            ],
            "canonical_source": [
                "memory_summaries",
                "memory_summary_memberships",
            ],
            "refresh_command": "ctxledger refresh-age-summary-graph",
            "read_path_scope": "narrow_auxiliary_summary_member_traversal",
            "ready": True,
        },
    }
    assert payload["result"]["details"]["summaries"] == [
        {
            "memory_summary_id": str(memory_summary_id),
            "episode_id": str(episode_id),
            "workflow_instance_id": str(workflow_id),
            "summary_text": "Canonical summary selected first",
            "summary_kind": "episode_summary",
            "metadata": {"kind": "canonical"},
            "member_memory_count": 1,
            "member_memory_ids": [str(member_memory_id)],
            "member_memory_items": [
                {
                    "memory_id": str(member_memory_id),
                    "workspace_id": str(workflow_id),
                    "episode_id": str(episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Expanded member memory item",
                    "metadata": {"kind": "member"},
                    "created_at": created_at.isoformat(),
                    "updated_at": created_at.isoformat(),
                }
            ],
        }
    ]
    assert payload["result"]["details"]["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:memory_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "selection_kind": "memory_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [str(episode_id)],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": True,
            "child_episode_groups_emission_reason": "memory_items_enabled",
            "summaries": [
                {
                    "memory_summary_id": str(memory_summary_id),
                    "episode_id": str(episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "summary_text": "Canonical summary selected first",
                    "summary_kind": "episode_summary",
                    "metadata": {"kind": "canonical"},
                    "member_memory_count": 1,
                    "member_memory_ids": [str(member_memory_id)],
                    "member_memory_items": [
                        {
                            "memory_id": str(member_memory_id),
                            "workspace_id": str(workflow_id),
                            "episode_id": str(episode_id),
                            "type": "episode_note",
                            "provenance": "episode",
                            "content": "Expanded member memory item",
                            "metadata": {"kind": "member"},
                            "created_at": created_at.isoformat(),
                            "updated_at": created_at.isoformat(),
                        }
                    ],
                }
            ],
        }
    ]
    assert len(fake_memory_service.calls) == 1


def test_http_mcp_rpc_tools_call_returns_memory_get_context_summary_only_primary_contract_details() -> (
    None
):
    settings = make_settings()
    workflow_id = uuid4()
    episode_id = uuid4()
    created_at = datetime(2024, 10, 13, 4, 5, 6, tzinfo=UTC)

    _, runtime, _, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    runtime._server = runtime._server  # keep explicit local reference shape stable
    runtime._server.workflow_service._uow_factory = lambda: None  # type: ignore[attr-defined]

    memory_service = GetContextResponse(
        feature=MemoryFeature.GET_CONTEXT,
        implemented=True,
        message="Episode-oriented memory context retrieved successfully.",
        status="ok",
        available_in_version="0.2.0",
        timestamp=created_at,
        episodes=(),
        details={
            "episodes_returned": 1,
            "summary_selection_applied": True,
            "summary_selection_kind": "episode_summary_first",
            "summary_first_has_episode_groups": False,
            "summary_first_is_summary_only": True,
            "summary_first_child_episode_count": 1,
            "summary_first_child_episode_ids": [str(episode_id)],
            "primary_episode_groups_present_after_query_filter": False,
            "auxiliary_only_after_query_filter": False,
            "retrieval_routes_present": ["summary_first"],
            "primary_retrieval_routes_present": ["summary_first"],
            "auxiliary_retrieval_routes_present": [],
            "memory_context_groups": [
                {
                    "scope": "summary",
                    "scope_id": None,
                    "group_id": "summary:episode_summary_first",
                    "parent_scope": "workflow_instance",
                    "parent_scope_id": str(workflow_id),
                    "selection_kind": "episode_summary_first",
                    "selection_route": "summary_first",
                    "child_episode_ids": [str(episode_id)],
                    "child_episode_count": 1,
                    "child_episode_ordering": "returned_episode_order",
                    "child_episode_groups_emitted": False,
                    "child_episode_groups_emission_reason": "memory_items_disabled",
                    "summaries": [
                        {
                            "episode_id": str(episode_id),
                            "workflow_instance_id": str(workflow_id),
                            "memory_item_count": 1,
                            "memory_item_types": ["episode_note"],
                            "memory_item_provenance": ["episode"],
                        }
                    ],
                }
            ],
        },
    )

    runtime._server.workflow_service = runtime._server.workflow_service  # type: ignore[attr-defined]

    from ctxledger.runtime import http_runtime as http_runtime_module

    original_builder = http_runtime_module.build_workflow_backed_memory_service

    class FakeMemoryService:
        def __init__(self) -> None:
            self.calls: list[object] = []

        def get_context(self, request: object) -> GetContextResponse:
            self.calls.append(request)
            return memory_service

    fake_memory_service = FakeMemoryService()
    http_runtime_module.build_workflow_backed_memory_service = lambda server: fake_memory_service

    try:
        response = runtime.dispatch(
            "mcp_rpc",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "memory_get_context",
                        "arguments": {
                            "workflow_instance_id": str(workflow_id),
                            "query": "summary-only primary path",
                            "limit": 10,
                            "include_episodes": True,
                            "include_memory_items": False,
                            "include_summaries": True,
                        },
                    },
                }
            ),
        )
    finally:
        http_runtime_module.build_workflow_backed_memory_service = original_builder

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload["jsonrpc"] == "2.0"
    assert response.payload["id"] == 4
    result = response.payload["result"]
    assert result["content"][0]["type"] == "text"
    payload = json.loads(result["content"][0]["text"])

    assert payload["ok"] is True
    assert payload["result"]["feature"] == "memory_get_context"
    assert payload["result"]["details"]["summary_selection_applied"] is True
    assert payload["result"]["details"]["summary_selection_kind"] == "episode_summary_first"
    assert payload["result"]["details"]["summary_first_has_episode_groups"] is False
    assert payload["result"]["details"]["summary_first_is_summary_only"] is True
    assert payload["result"]["details"]["summary_first_child_episode_count"] == 1
    assert payload["result"]["details"]["summary_first_child_episode_ids"] == [
        str(episode_id),
    ]
    assert (
        payload["result"]["details"]["primary_episode_groups_present_after_query_filter"] is False
    )
    assert payload["result"]["details"]["auxiliary_only_after_query_filter"] is False
    assert payload["result"]["details"]["retrieval_routes_present"] == ["summary_first"]
    assert payload["result"]["details"]["primary_retrieval_routes_present"] == [
        "summary_first",
    ]
    assert payload["result"]["details"]["auxiliary_retrieval_routes_present"] == []
    assert payload["result"]["details"]["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [str(episode_id)],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": False,
            "child_episode_groups_emission_reason": "memory_items_disabled",
            "summaries": [
                {
                    "episode_id": str(episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                }
            ],
        }
    ]
    assert len(fake_memory_service.calls) == 1


def test_http_mcp_rpc_tools_call_returns_memory_get_context_episode_less_narrow_contract_without_summary_first_details() -> (
    None
):
    settings = make_settings()
    workflow_id = uuid4()
    workspace_id = str(uuid4())
    inherited_memory_id = uuid4()
    created_at = datetime(2024, 10, 14, 4, 5, 6, tzinfo=UTC)

    _, runtime, _, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    runtime._server = runtime._server  # keep explicit local reference shape stable
    runtime._server.workflow_service._uow_factory = lambda: None  # type: ignore[attr-defined]

    memory_service = GetContextResponse(
        feature=MemoryFeature.GET_CONTEXT,
        implemented=True,
        message="Episode-oriented memory context retrieved successfully.",
        status="ok",
        available_in_version="0.2.0",
        timestamp=created_at,
        episodes=(),
        details={
            "episodes_returned": 0,
            "summary_selection_applied": False,
            "summary_selection_kind": None,
            "retrieval_routes_present": ["workspace_inherited_auxiliary"],
            "primary_retrieval_routes_present": [],
            "auxiliary_retrieval_routes_present": ["workspace_inherited_auxiliary"],
            "memory_context_groups": [
                {
                    "scope": "workspace",
                    "scope_id": workspace_id,
                    "parent_scope": None,
                    "parent_scope_id": None,
                    "selection_kind": "inherited_workspace",
                    "selection_route": "workspace_inherited_auxiliary",
                    "memory_items": [
                        {
                            "memory_id": str(inherited_memory_id),
                            "workspace_id": workspace_id,
                            "episode_id": None,
                            "type": "workspace_note",
                            "provenance": "workspace",
                            "content": "Inherited workspace item still visible with include_episodes false",
                            "metadata": {"kind": "workspace-item"},
                            "created_at": created_at.isoformat(),
                            "updated_at": created_at.isoformat(),
                        }
                    ],
                }
            ],
        },
    )

    runtime._server.workflow_service = runtime._server.workflow_service  # type: ignore[attr-defined]

    from ctxledger.runtime import http_runtime as http_runtime_module

    original_builder = http_runtime_module.build_workflow_backed_memory_service

    class FakeMemoryService:
        def __init__(self) -> None:
            self.calls: list[object] = []

        def get_context(self, request: object) -> GetContextResponse:
            self.calls.append(request)
            return memory_service

    fake_memory_service = FakeMemoryService()
    http_runtime_module.build_workflow_backed_memory_service = lambda server: fake_memory_service

    try:
        response = runtime.dispatch(
            "mcp_rpc",
            "/mcp",
            body=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "memory_get_context",
                        "arguments": {
                            "workflow_instance_id": str(workflow_id),
                            "query": "hidden shaping",
                            "limit": 10,
                            "include_episodes": False,
                            "include_memory_items": True,
                            "include_summaries": True,
                        },
                    },
                }
            ),
        )
    finally:
        http_runtime_module.build_workflow_backed_memory_service = original_builder

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload["jsonrpc"] == "2.0"
    assert response.payload["id"] == 5
    result = response.payload["result"]
    assert result["content"][0]["type"] == "text"
    payload = json.loads(result["content"][0]["text"])

    assert payload["ok"] is True
    assert payload["result"]["feature"] == "memory_get_context"
    assert payload["result"]["details"]["summary_selection_applied"] is False
    assert payload["result"]["details"]["summary_selection_kind"] is None
    assert payload["result"]["details"]["retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert payload["result"]["details"]["primary_retrieval_routes_present"] == []
    assert payload["result"]["details"]["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert payload["result"]["details"]["memory_context_groups"] == [
        {
            "scope": "workspace",
            "scope_id": workspace_id,
            "parent_scope": None,
            "parent_scope_id": None,
            "selection_kind": "inherited_workspace",
            "selection_route": "workspace_inherited_auxiliary",
            "memory_items": [
                {
                    "memory_id": str(inherited_memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": None,
                    "type": "workspace_note",
                    "provenance": "workspace",
                    "content": "Inherited workspace item still visible with include_episodes false",
                    "metadata": {"kind": "workspace-item"},
                    "created_at": created_at.isoformat(),
                    "updated_at": created_at.isoformat(),
                }
            ],
        }
    ]
    assert "summary_first_has_episode_groups" not in payload["result"]["details"]
    assert "summary_first_is_summary_only" not in payload["result"]["details"]
    assert "summary_first_child_episode_count" not in payload["result"]["details"]
    assert "summary_first_child_episode_ids" not in payload["result"]["details"]
    assert "primary_episode_groups_present_after_query_filter" not in payload["result"]["details"]
    assert "auxiliary_only_after_query_filter" not in payload["result"]["details"]
    assert len(fake_memory_service.calls) == 1


def test_http_mcp_rpc_tools_call_returns_workspace_register_success_payload() -> None:
    settings = make_settings()
    resume = make_resume_fixture()
    registered_workspace = resume.workspace.__class__(
        workspace_id=resume.workspace.workspace_id,
        repo_url="https://example.com/registered.git",
        canonical_path="/tmp/registered",
        default_branch="main",
        metadata={"team": "platform"},
        created_at=resume.workspace.created_at,
        updated_at=resume.workspace.updated_at,
    )
    fake_workflow_service = FakeWorkflowService(
        resume,
        register_workspace_result=registered_workspace,
    )
    _, runtime, _, _ = make_http_runtime(
        settings=settings,
        resume=resume,
        fake_workflow_service=fake_workflow_service,
        started=True,
    )

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        body=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "workspace_register",
                    "arguments": {
                        "repo_url": registered_workspace.repo_url,
                        "canonical_path": registered_workspace.canonical_path,
                        "default_branch": registered_workspace.default_branch,
                        "metadata": {"team": "platform"},
                    },
                },
            }
        ),
    )

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload["jsonrpc"] == "2.0"
    assert response.payload["id"] == 3

    result = response.payload["result"]
    assert result["content"][0]["type"] == "text"
    payload = json.loads(result["content"][0]["text"])

    assert payload["ok"] is True
    assert payload["result"] == {
        "workspace_id": str(registered_workspace.workspace_id),
        "repo_url": registered_workspace.repo_url,
        "canonical_path": registered_workspace.canonical_path,
        "default_branch": registered_workspace.default_branch,
        "metadata": {"team": "platform"},
        "created_at": registered_workspace.created_at.isoformat(),
        "updated_at": registered_workspace.updated_at.isoformat(),
    }


def test_http_mcp_rpc_resources_list_returns_registered_resources() -> None:
    settings = make_settings()
    _, runtime, _, _ = make_http_runtime(
        settings=settings,
    )

    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        body=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "resources/list",
                "params": {},
            }
        ),
    )

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload == {
        "jsonrpc": "2.0",
        "id": 4,
        "result": {
            "resources": [
                {
                    "uri": "workspace://{workspace_id}/resume",
                    "name": "workspace://{workspace_id}/resume",
                    "description": "workspace://{workspace_id}/resume resource",
                },
                {
                    "uri": "workspace://{workspace_id}/workflow/{workflow_instance_id}",
                    "name": "workspace://{workspace_id}/workflow/{workflow_instance_id}",
                    "description": (
                        "workspace://{workspace_id}/workflow/{workflow_instance_id} resource"
                    ),
                },
            ]
        },
    }


def test_http_mcp_rpc_resources_read_returns_workspace_resume_payload() -> None:
    settings = make_settings()
    _, runtime, resume, _ = make_http_runtime(
        settings=settings,
        started=True,
    )

    uri = f"workspace://{resume.workspace.workspace_id}/resume"
    response = runtime.dispatch(
        "mcp_rpc",
        "/mcp",
        body=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "resources/read",
                "params": {
                    "uri": uri,
                },
            }
        ),
    )

    assert isinstance(response, McpHttpResponse)
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.payload["jsonrpc"] == "2.0"
    assert response.payload["id"] == 5

    contents = response.payload["result"]["contents"]
    assert len(contents) == 1
    assert contents[0]["uri"] == uri
    assert contents[0]["mimeType"] == "application/json"

    payload_text = json.loads(contents[0]["text"])
    assert payload_text["uri"] == uri

    resource = payload_text["resource"]
    expected_resource = serialize_workflow_resume(resume)
    for key, value in expected_resource.items():
        assert resource[key] == value
