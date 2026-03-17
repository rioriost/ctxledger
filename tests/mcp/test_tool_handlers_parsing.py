from __future__ import annotations

from uuid import uuid4

import pytest

from ctxledger.mcp.tool_handlers import (
    _parse_optional_dict_argument,
    _parse_optional_string_argument,
    _parse_optional_verify_status_argument,
    _parse_required_string_argument,
    _parse_required_uuid_argument,
    _parse_required_workflow_status_argument,
)
from ctxledger.runtime.types import McpToolResponse
from ctxledger.workflow.service import VerifyStatus, WorkflowInstanceStatus


@pytest.mark.parametrize("raw_value", [None, "", "   ", 123])
def test_parse_required_uuid_argument_rejects_missing_or_invalid_type(
    raw_value: object,
) -> None:
    result = _parse_required_uuid_argument(
        {"workflow_instance_id": raw_value},
        "workflow_instance_id",
    )

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "workflow_instance_id must be a non-empty string",
                "details": {"field": "workflow_instance_id"},
            },
        }
    )


def test_parse_required_uuid_argument_rejects_invalid_uuid() -> None:
    result = _parse_required_uuid_argument(
        {"workflow_instance_id": "not-a-uuid"},
        "workflow_instance_id",
    )

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "workflow_instance_id must be a valid UUID",
                "details": {"field": "workflow_instance_id"},
            },
        }
    )


def test_parse_required_uuid_argument_returns_uuid() -> None:
    value = uuid4()

    result = _parse_required_uuid_argument(
        {"workflow_instance_id": str(value)},
        "workflow_instance_id",
    )

    assert result == value


@pytest.mark.parametrize("raw_value", [None, "", "   ", 1])
def test_parse_required_string_argument_rejects_invalid_values(
    raw_value: object,
) -> None:
    result = _parse_required_string_argument({"field": raw_value}, "field")

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "field must be a non-empty string",
                "details": {"field": "field"},
            },
        }
    )


def test_parse_required_string_argument_strips_value() -> None:
    assert _parse_required_string_argument({"field": "  hello  "}, "field") == "hello"


def test_parse_optional_string_argument_returns_none_when_missing() -> None:
    assert _parse_optional_string_argument({}, "summary") is None


def test_parse_optional_string_argument_rejects_non_string() -> None:
    result = _parse_optional_string_argument({"summary": 1}, "summary")

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "summary must be a string when provided",
                "details": {"field": "summary"},
            },
        }
    )


def test_parse_optional_string_argument_returns_string_without_stripping() -> None:
    assert (
        _parse_optional_string_argument({"summary": "  value  "}, "summary")
        == "  value  "
    )


def test_parse_optional_dict_argument_returns_empty_dict_when_missing() -> None:
    assert _parse_optional_dict_argument({}, "metadata") == {}


def test_parse_optional_dict_argument_rejects_non_dict() -> None:
    result = _parse_optional_dict_argument({"metadata": []}, "metadata")

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "metadata must be an object when provided",
                "details": {"field": "metadata"},
            },
        }
    )


def test_parse_optional_dict_argument_returns_copied_dict() -> None:
    source = {"a": 1}
    result = _parse_optional_dict_argument({"metadata": source}, "metadata")

    assert result == source
    assert result is not source


def test_parse_optional_verify_status_argument_returns_none_when_missing() -> None:
    assert _parse_optional_verify_status_argument({}) is None


@pytest.mark.parametrize("raw_value", ["", "   ", 1])
def test_parse_optional_verify_status_argument_rejects_invalid_values(
    raw_value: object,
) -> None:
    result = _parse_optional_verify_status_argument({"verify_status": raw_value})

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "verify_status must be a non-empty string when provided",
                "details": {"field": "verify_status"},
            },
        }
    )


def test_parse_optional_verify_status_argument_rejects_unknown_value() -> None:
    result = _parse_optional_verify_status_argument({"verify_status": "unknown"})

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "verify_status must be a supported verification status",
                "details": {
                    "field": "verify_status",
                    "allowed_values": ["pending", "passed", "failed", "skipped"],
                },
            },
        }
    )


def test_parse_optional_verify_status_argument_returns_enum() -> None:
    assert (
        _parse_optional_verify_status_argument({"verify_status": "passed"})
        is VerifyStatus.PASSED
    )


@pytest.mark.parametrize("raw_value", [None, "", "   ", 1])
def test_parse_required_workflow_status_argument_rejects_invalid_values(
    raw_value: object,
) -> None:
    result = _parse_required_workflow_status_argument({"workflow_status": raw_value})

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "workflow_status must be a non-empty string",
                "details": {"field": "workflow_status"},
            },
        }
    )


def test_parse_required_workflow_status_argument_rejects_unknown_value() -> None:
    result = _parse_required_workflow_status_argument({"workflow_status": "weird"})

    assert result == McpToolResponse(
        payload={
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "workflow_status must be a supported workflow status",
                "details": {
                    "field": "workflow_status",
                    "allowed_values": ["running", "completed", "failed", "cancelled"],
                },
            },
        }
    )


def test_parse_required_workflow_status_argument_returns_enum() -> None:
    assert (
        _parse_required_workflow_status_argument({"workflow_status": "completed"})
        is WorkflowInstanceStatus.COMPLETED
    )
