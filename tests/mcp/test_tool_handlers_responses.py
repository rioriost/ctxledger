from __future__ import annotations

import pytest

from ctxledger.mcp.tool_handlers import (
    _map_workflow_error_to_mcp_response,
    _mcp_tool_response_cls,
    build_mcp_error_response,
    build_mcp_success_response,
)
from ctxledger.runtime.types import McpToolResponse
from ctxledger.workflow.service import WorkflowError


def test_mcp_tool_response_cls_returns_runtime_type() -> None:
    assert _mcp_tool_response_cls() is McpToolResponse


def test_build_mcp_success_response_wraps_result() -> None:
    response = build_mcp_success_response({"value": 1})

    assert response == McpToolResponse(
        payload={
            "ok": True,
            "result": {"value": 1},
        }
    )


def test_build_mcp_error_response_uses_empty_details_by_default() -> None:
    response = build_mcp_error_response(
        code="invalid_request",
        message="bad request",
    )

    assert response == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "bad request",
                "details": {},
            },
        }
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("validation_error", "invalid_request"),
        ("authentication_error", "invalid_request"),
        ("active_workflow_exists", "invalid_request"),
        ("workspace_registration_conflict", "invalid_request"),
        ("invalid_state_transition", "invalid_request"),
        ("workflow_attempt_mismatch", "invalid_request"),
        ("workspace_not_found", "not_found"),
        ("workflow_not_found", "not_found"),
        ("attempt_not_found", "not_found"),
        ("not_found", "not_found"),
        ("unexpected", "server_error"),
    ],
)
def test_map_workflow_error_to_mcp_response_maps_workflow_error_codes(
    code: str,
    expected: str,
) -> None:
    exc = WorkflowError("boom", details={"x": 1})
    exc.code = code

    response = _map_workflow_error_to_mcp_response(
        exc,
        default_message="fallback",
    )

    assert response == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": expected,
                "message": "boom",
                "details": {"x": 1},
            },
        }
    )


@pytest.mark.parametrize(
    ("message", "expected_code"),
    [
        ("resource not found", "not_found"),
        ("invalid transition", "invalid_request"),
        ("attempt mismatch", "invalid_request"),
        ("already exists", "invalid_request"),
        ("internal boom", "server_error"),
    ],
)
def test_map_workflow_error_to_mcp_response_maps_generic_exceptions(
    message: str,
    expected_code: str,
) -> None:
    response = _map_workflow_error_to_mcp_response(
        RuntimeError(message),
        default_message="fallback",
    )

    assert response == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": expected_code,
                "message": message,
                "details": {},
            },
        }
    )


def test_map_workflow_error_to_mcp_response_uses_default_message_for_empty_exception() -> (
    None
):
    response = _map_workflow_error_to_mcp_response(
        RuntimeError(""),
        default_message="fallback",
    )

    assert response == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "server_error",
                "message": "fallback",
                "details": {},
            },
        }
    )
