from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ctxledger.workflow.service import (
    VerifyStatus,
    WorkflowInstanceStatus,
)


@dataclass(slots=True, frozen=True)
class McpToolSchema:
    type: str
    properties: dict[str, Any]
    required: tuple[str, ...] = ()
    additional_properties: bool = False


DEFAULT_EMPTY_MCP_TOOL_SCHEMA = McpToolSchema(
    type="object",
    properties={},
)


def serialize_mcp_tool_schema(schema: McpToolSchema) -> dict[str, Any]:
    serialized: dict[str, Any] = {
        "type": schema.type,
        "properties": dict(schema.properties),
        "additionalProperties": schema.additional_properties,
    }
    if schema.required:
        serialized["required"] = list(schema.required)
    return serialized


WORKSPACE_REGISTER_TOOL_SCHEMA = McpToolSchema(
    type="object",
    properties={
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
    required=("repo_url", "canonical_path", "default_branch"),
)

WORKFLOW_RESUME_TOOL_SCHEMA = McpToolSchema(
    type="object",
    properties={
        "workflow_instance_id": {
            "type": "string",
            "format": "uuid",
            "description": "Workflow instance to resume.",
        }
    },
    required=("workflow_instance_id",),
)

WORKFLOW_START_TOOL_SCHEMA = McpToolSchema(
    type="object",
    properties={
        "workspace_id": {
            "type": "string",
            "format": "uuid",
            "description": "Workspace identity for the workflow.",
        },
        "ticket_id": {
            "type": "string",
            "minLength": 1,
            "description": "External ticket or work item identifier.",
        },
        "metadata": {
            "type": "object",
            "description": "Optional workflow metadata.",
            "additionalProperties": True,
        },
    },
    required=("workspace_id", "ticket_id"),
)

WORKFLOW_CHECKPOINT_TOOL_SCHEMA = McpToolSchema(
    type="object",
    properties={
        "workflow_instance_id": {
            "type": "string",
            "format": "uuid",
            "description": "Workflow instance identity.",
        },
        "attempt_id": {
            "type": "string",
            "format": "uuid",
            "description": "Workflow attempt identity.",
        },
        "step_name": {
            "type": "string",
            "minLength": 1,
            "description": "Logical step name for the checkpoint.",
        },
        "summary": {
            "type": "string",
            "description": "Optional human-readable checkpoint summary.",
        },
        "current_objective": {
            "type": "string",
            "description": "Optional current objective for the checkpoint.",
        },
        "next_intended_action": {
            "type": "string",
            "description": "Optional next intended action for the checkpoint.",
        },
        "verify_target": {
            "type": "string",
            "description": "Optional explicit verification target for the checkpoint.",
        },
        "resume_hint": {
            "type": "string",
            "description": "Optional resume hint for the next continuation step.",
        },
        "blocker_or_risk": {
            "type": "string",
            "description": "Optional blocker or risk recorded with the checkpoint.",
        },
        "failure_guard": {
            "type": "string",
            "description": "Optional failure guard to preserve while continuing work.",
        },
        "root_cause": {
            "type": "string",
            "description": "Optional root cause recorded with the checkpoint.",
        },
        "recovery_pattern": {
            "type": "string",
            "description": "Optional recovery pattern recorded with the checkpoint.",
        },
        "what_remains": {
            "type": "string",
            "description": "Optional remaining work recorded with the checkpoint.",
        },
        "checkpoint_json": {
            "type": "object",
            "description": (
                "Optional structured checkpoint payload. Preferred structured "
                "fields include `current_objective`, `next_intended_action`, "
                "`verify_target`, `resume_hint`, `blocker_or_risk`, "
                "`failure_guard`, `root_cause`, `recovery_pattern`, and "
                "`what_remains`. Top-level structured checkpoint fields are "
                "normalized into this payload for compatibility."
            ),
            "additionalProperties": True,
        },
        "verify_status": {
            "type": "string",
            "enum": [status.value for status in VerifyStatus],
            "description": "Optional verification status recorded with the checkpoint.",
        },
        "verify_report": {
            "type": "object",
            "description": "Optional structured verification report.",
            "additionalProperties": True,
        },
    },
    required=("workflow_instance_id", "attempt_id", "step_name"),
)

WORKFLOW_COMPLETE_TOOL_SCHEMA = McpToolSchema(
    type="object",
    properties={
        "workflow_instance_id": {
            "type": "string",
            "format": "uuid",
            "description": "Workflow instance identity.",
        },
        "attempt_id": {
            "type": "string",
            "format": "uuid",
            "description": "Workflow attempt identity.",
        },
        "workflow_status": {
            "type": "string",
            "enum": [status.value for status in WorkflowInstanceStatus],
            "description": "Terminal workflow status.",
        },
        "summary": {
            "type": "string",
            "description": "Optional final summary.",
        },
        "verify_status": {
            "type": "string",
            "enum": [status.value for status in VerifyStatus],
            "description": "Optional final verification status.",
        },
        "verify_report": {
            "type": "object",
            "description": "Optional structured final verification report.",
            "additionalProperties": True,
        },
        "failure_reason": {
            "type": "string",
            "description": "Optional failure reason for unsuccessful completion.",
        },
    },
    required=("workflow_instance_id", "attempt_id", "workflow_status"),
)


MEMORY_REMEMBER_EPISODE_TOOL_SCHEMA = McpToolSchema(
    type="object",
    properties={
        "workflow_instance_id": {
            "type": "string",
            "minLength": 1,
            "description": "Workflow instance identifier associated with the episode.",
        },
        "summary": {
            "type": "string",
            "minLength": 1,
            "description": "Episode summary text.",
        },
        "attempt_id": {
            "type": "string",
            "description": "Optional workflow attempt identifier.",
        },
        "metadata": {
            "type": "object",
            "description": "Optional episode metadata.",
            "additionalProperties": True,
        },
    },
    required=("workflow_instance_id", "summary"),
)

MEMORY_SEARCH_TOOL_SCHEMA = McpToolSchema(
    type="object",
    properties={
        "query": {
            "type": "string",
            "minLength": 1,
            "description": "Search query text.",
        },
        "workspace_id": {
            "type": "string",
            "description": "Optional workspace identifier to constrain results.",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "description": "Maximum number of results to return.",
        },
        "filters": {
            "type": "object",
            "description": "Optional structured filters.",
            "additionalProperties": True,
        },
    },
    required=("query",),
)

MEMORY_GET_CONTEXT_TOOL_SCHEMA = McpToolSchema(
    type="object",
    properties={
        "query": {
            "type": "string",
            "description": "Optional context query text.",
        },
        "workspace_id": {
            "type": "string",
            "description": "Optional workspace identifier.",
        },
        "workflow_instance_id": {
            "type": "string",
            "description": "Optional workflow instance identifier.",
        },
        "ticket_id": {
            "type": "string",
            "description": "Optional ticket identifier.",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "description": "Maximum number of context items to return.",
        },
        "include_episodes": {
            "type": "boolean",
            "description": "Whether to include episodes in the response.",
        },
        "include_memory_items": {
            "type": "boolean",
            "description": "Whether to include memory items in the response.",
        },
        "include_summaries": {
            "type": "boolean",
            "description": "Whether to include summaries in the response.",
        },
        "primary_only": {
            "type": "boolean",
            "description": "Whether to return only the primary grouped \
            surface and omit compatibility-oriented fields.",
        },
    },
)

FILE_WORK_RECORD_TOOL_SCHEMA = McpToolSchema(
    type="object",
    properties={
        "workflow_instance_id": {
            "type": "string",
            "format": "uuid",
            "description": "Workflow instance identifier associated with the file work.",
        },
        "summary": {
            "type": "string",
            "minLength": 1,
            "description": "Short durable summary of the file work being recorded.",
        },
        "attempt_id": {
            "type": "string",
            "format": "uuid",
            "description": "Optional workflow attempt identifier.",
        },
        "file_path": {
            "type": "string",
            "minLength": 1,
            "description": "Repository-relative or canonical file \
            path for the primary file touched.",
        },
        "file_name": {
            "type": "string",
            "description": "Optional file name when it should be recorded explicitly.",
        },
        "file_operation": {
            "type": "string",
            "minLength": 1,
            "description": "Bounded file operation label such as create, \
            modify, move, copy, delete, save, or restore.",
        },
        "purpose": {
            "type": "string",
            "description": "Optional purpose of the file work.",
        },
        "metadata": {
            "type": "object",
            "description": "Optional additional bounded file-work metadata.",
            "additionalProperties": True,
        },
    },
    required=("workflow_instance_id", "summary", "file_path", "file_operation"),
)
