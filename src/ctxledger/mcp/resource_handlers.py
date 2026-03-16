from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

_RESOURCE_URI_PREFIX = "workspace://"
_WORKSPACE_RESUME_RESOURCE_PARTS = 2
_WORKFLOW_DETAIL_RESOURCE_PARTS = 3

if TYPE_CHECKING:
    from ..server import CtxLedgerServer, McpResourceResponse


def parse_workspace_resume_resource_uri(uri: str) -> UUID | None:
    parts = _parse_workspace_resource_uri(uri)
    if parts is None:
        return None
    if len(parts) != _WORKSPACE_RESUME_RESOURCE_PARTS or parts[1] != "resume":
        return None

    return _parse_uuid(parts[0])


def parse_workflow_detail_resource_uri(uri: str) -> tuple[UUID, UUID] | None:
    parts = _parse_workspace_resource_uri(uri)
    if parts is None:
        return None
    if len(parts) != _WORKFLOW_DETAIL_RESOURCE_PARTS or parts[1] != "workflow":
        return None

    workspace_id = _parse_uuid(parts[0])
    workflow_instance_id = _parse_uuid(parts[2])
    if workspace_id is None or workflow_instance_id is None:
        return None

    return workspace_id, workflow_instance_id


def build_workspace_resume_resource_response(
    server: CtxLedgerServer,
    workspace_id: UUID,
) -> McpResourceResponse:
    return server.build_workspace_resume_resource_response(workspace_id)


def build_workflow_detail_resource_response(
    server: CtxLedgerServer,
    *,
    workspace_id: UUID,
    workflow_instance_id: UUID,
) -> McpResourceResponse:
    return server.build_workflow_detail_resource_response(
        workspace_id,
        workflow_instance_id,
    )


def build_workspace_resume_resource_handler(
    server: CtxLedgerServer,
):
    def _handler(uri: str) -> McpResourceResponse:
        workspace_id = parse_workspace_resume_resource_uri(uri)
        if workspace_id is None:
            return _build_not_found_response(
                server,
                message=(
                    "workspace resume resource requires "
                    "workspace://{workspace_id}/resume"
                ),
            )

        return build_workspace_resume_resource_response(server, workspace_id)

    return _handler


def build_workflow_detail_resource_handler(
    server: CtxLedgerServer,
):
    def _handler(uri: str) -> McpResourceResponse:
        parsed = parse_workflow_detail_resource_uri(uri)
        if parsed is None:
            return _build_not_found_response(
                server,
                message=(
                    "workflow detail resource requires "
                    "workspace://{workspace_id}/workflow/{workflow_instance_id}"
                ),
            )

        workspace_id, workflow_instance_id = parsed
        return build_workflow_detail_resource_response(
            server,
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
        )

    return _handler


def _build_not_found_response(
    server: CtxLedgerServer,
    *,
    message: str,
) -> McpResourceResponse:
    response_type = _lookup_server_symbol(server, "McpResourceResponse")
    return response_type(
        status_code=404,
        payload={
            "error": {
                "code": "not_found",
                "message": message,
            }
        },
        headers={"content-type": "application/json"},
    )


def _lookup_server_symbol(server: CtxLedgerServer, name: str) -> Any:
    module = __import__(server.__class__.__module__, fromlist=[name])
    return getattr(module, name)


def _parse_workspace_resource_uri(uri: str) -> list[str] | None:
    normalized_uri = uri.strip()
    if not normalized_uri:
        return None
    if not normalized_uri.startswith(_RESOURCE_URI_PREFIX):
        return None

    remainder = normalized_uri[len(_RESOURCE_URI_PREFIX) :]
    return remainder.split("/")


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


__all__ = [
    "build_workflow_detail_resource_handler",
    "build_workflow_detail_resource_response",
    "build_workspace_resume_resource_handler",
    "build_workspace_resume_resource_response",
    "parse_workflow_detail_resource_uri",
    "parse_workspace_resume_resource_uri",
]
