from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from ..server import CtxLedgerServer, McpResourceResponse


def parse_workspace_resume_resource_uri(uri: str) -> UUID | None:
    normalized_uri = uri.strip()
    if not normalized_uri:
        return None

    prefix = "workspace://"
    if not normalized_uri.startswith(prefix):
        return None

    remainder = normalized_uri[len(prefix) :]
    parts = remainder.split("/")
    if len(parts) != 2 or parts[1] != "resume":
        return None

    try:
        return UUID(parts[0])
    except ValueError:
        return None


def parse_workflow_detail_resource_uri(uri: str) -> tuple[UUID, UUID] | None:
    normalized_uri = uri.strip()
    if not normalized_uri:
        return None

    prefix = "workspace://"
    if not normalized_uri.startswith(prefix):
        return None

    remainder = normalized_uri[len(prefix) :]
    parts = remainder.split("/")
    if len(parts) != 3 or parts[1] != "workflow":
        return None

    try:
        return UUID(parts[0]), UUID(parts[2])
    except ValueError:
        return None


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


__all__ = [
    "build_workflow_detail_resource_handler",
    "build_workflow_detail_resource_response",
    "build_workspace_resume_resource_handler",
    "build_workspace_resume_resource_response",
    "parse_workflow_detail_resource_uri",
    "parse_workspace_resume_resource_uri",
]
