from __future__ import annotations

from typing import Any
from uuid import UUID

from ctxledger.memory.service import (
    GetContextResponse,
    RememberEpisodeResponse,
    SearchMemoryResponse,
    StubResponse,
)

from ..workflow.service import WorkflowResume
from .introspection import RuntimeIntrospection


def serialize_workflow_resume(
    resume: WorkflowResume,
    *,
    include_closed_projection_failures: bool = True,
) -> dict[str, Any]:
    payload = {
        "workspace": {
            "workspace_id": str(resume.workspace.workspace_id),
            "repo_url": resume.workspace.repo_url,
            "canonical_path": resume.workspace.canonical_path,
            "default_branch": resume.workspace.default_branch,
            "metadata": resume.workspace.metadata,
        },
        "workflow": {
            "workflow_instance_id": str(resume.workflow_instance.workflow_instance_id),
            "workspace_id": str(resume.workflow_instance.workspace_id),
            "ticket_id": resume.workflow_instance.ticket_id,
            "status": resume.workflow_instance.status.value,
            "metadata": resume.workflow_instance.metadata,
        },
        "attempt": (
            {
                "attempt_id": str(resume.attempt.attempt_id),
                "workflow_instance_id": str(resume.attempt.workflow_instance_id),
                "attempt_number": resume.attempt.attempt_number,
                "status": resume.attempt.status.value,
                "failure_reason": resume.attempt.failure_reason,
                "verify_status": (
                    resume.attempt.verify_status.value
                    if resume.attempt.verify_status is not None
                    else None
                ),
                "started_at": resume.attempt.started_at.isoformat(),
                "finished_at": (
                    resume.attempt.finished_at.isoformat()
                    if resume.attempt.finished_at is not None
                    else None
                ),
            }
            if resume.attempt is not None
            else None
        ),
        "latest_checkpoint": (
            {
                "checkpoint_id": str(resume.latest_checkpoint.checkpoint_id),
                "workflow_instance_id": str(
                    resume.latest_checkpoint.workflow_instance_id
                ),
                "attempt_id": str(resume.latest_checkpoint.attempt_id),
                "step_name": resume.latest_checkpoint.step_name,
                "summary": resume.latest_checkpoint.summary,
                "checkpoint_json": resume.latest_checkpoint.checkpoint_json,
                "created_at": resume.latest_checkpoint.created_at.isoformat(),
            }
            if resume.latest_checkpoint is not None
            else None
        ),
        "latest_verify_report": (
            {
                "verify_id": str(resume.latest_verify_report.verify_id),
                "attempt_id": str(resume.latest_verify_report.attempt_id),
                "status": resume.latest_verify_report.status.value,
                "report_json": resume.latest_verify_report.report_json,
                "created_at": resume.latest_verify_report.created_at.isoformat(),
            }
            if resume.latest_verify_report is not None
            else None
        ),
        "projections": [
            {
                "projection_type": projection.projection_type.value,
                "status": projection.status.value,
                "target_path": projection.target_path,
                "last_successful_write_at": (
                    projection.last_successful_write_at.isoformat()
                    if projection.last_successful_write_at is not None
                    else None
                ),
                "last_canonical_update_at": (
                    projection.last_canonical_update_at.isoformat()
                    if projection.last_canonical_update_at is not None
                    else None
                ),
                "open_failure_count": projection.open_failure_count,
            }
            for projection in resume.projections
        ],
        "resumable_status": resume.resumable_status.value,
        "next_hint": resume.next_hint,
        "warnings": [
            {
                "code": warning.code,
                "message": warning.message,
                "details": warning.details,
            }
            for warning in resume.warnings
        ],
    }
    if include_closed_projection_failures:
        payload["closed_projection_failures"] = [
            {
                "projection_type": failure.projection_type.value,
                "target_path": failure.target_path,
                "attempt_id": (
                    str(failure.attempt_id) if failure.attempt_id is not None else None
                ),
                "error_code": failure.error_code,
                "error_message": failure.error_message,
                "occurred_at": (
                    failure.occurred_at.isoformat()
                    if failure.occurred_at is not None
                    else None
                ),
                "resolved_at": (
                    failure.resolved_at.isoformat()
                    if failure.resolved_at is not None
                    else None
                ),
                "open_failure_count": failure.open_failure_count,
                "retry_count": failure.retry_count,
                "status": failure.status,
            }
            for failure in getattr(resume, "closed_projection_failures", ())
        ]
    return payload


def serialize_closed_projection_failures_history(
    workflow_instance_id: UUID,
    closed_projection_failures: tuple[Any, ...] | list[Any],
) -> dict[str, Any]:
    return {
        "workflow_instance_id": str(workflow_instance_id),
        "closed_projection_failures": [
            {
                "projection_type": failure.projection_type.value,
                "target_path": failure.target_path,
                "attempt_id": (
                    str(failure.attempt_id) if failure.attempt_id is not None else None
                ),
                "error_code": failure.error_code,
                "error_message": failure.error_message,
                "occurred_at": (
                    failure.occurred_at.isoformat()
                    if failure.occurred_at is not None
                    else None
                ),
                "resolved_at": (
                    failure.resolved_at.isoformat()
                    if failure.resolved_at is not None
                    else None
                ),
                "open_failure_count": failure.open_failure_count,
                "retry_count": failure.retry_count,
                "status": failure.status,
            }
            for failure in closed_projection_failures
        ],
    }


def serialize_stub_response(response: StubResponse) -> dict[str, Any]:
    return {
        "feature": response.feature.value,
        "implemented": response.implemented,
        "message": response.message,
        "status": response.status,
        "available_in_version": response.available_in_version,
        "timestamp": response.timestamp.isoformat(),
        "details": response.details,
    }


def serialize_search_memory_response(
    response: SearchMemoryResponse,
) -> dict[str, Any]:
    return {
        "feature": response.feature.value,
        "implemented": response.implemented,
        "message": response.message,
        "status": response.status,
        "available_in_version": response.available_in_version,
        "timestamp": response.timestamp.isoformat(),
        "results": [
            {
                "memory_id": str(result.memory_id),
                "workspace_id": (
                    str(result.workspace_id)
                    if result.workspace_id is not None
                    else None
                ),
                "episode_id": (
                    str(result.episode_id) if result.episode_id is not None else None
                ),
                "workflow_instance_id": (
                    str(result.workflow_instance_id)
                    if result.workflow_instance_id is not None
                    else None
                ),
                "summary": result.summary,
                "attempt_id": (
                    str(result.attempt_id) if result.attempt_id is not None else None
                ),
                "metadata": result.metadata,
                "score": result.score,
                "matched_fields": list(result.matched_fields),
                "lexical_score": result.lexical_score,
                "semantic_score": result.semantic_score,
                "ranking_details": result.ranking_details,
                "created_at": result.created_at.isoformat(),
                "updated_at": result.updated_at.isoformat(),
            }
            for result in response.results
        ],
        "details": response.details,
    }


def serialize_remember_episode_response(
    response: RememberEpisodeResponse,
) -> dict[str, Any]:
    payload = {
        "feature": response.feature.value,
        "implemented": response.implemented,
        "message": response.message,
        "status": response.status,
        "available_in_version": response.available_in_version,
        "timestamp": response.timestamp.isoformat(),
        "details": response.details,
    }
    if response.episode is not None:
        payload["episode"] = {
            "episode_id": str(response.episode.episode_id),
            "workflow_instance_id": str(response.episode.workflow_instance_id),
            "summary": response.episode.summary,
            "attempt_id": (
                str(response.episode.attempt_id)
                if response.episode.attempt_id is not None
                else None
            ),
            "metadata": response.episode.metadata,
            "status": response.episode.status,
            "created_at": response.episode.created_at.isoformat(),
            "updated_at": response.episode.updated_at.isoformat(),
        }
    return payload


def serialize_get_context_response(
    response: GetContextResponse,
) -> dict[str, Any]:
    details = dict(response.details)
    details.setdefault("memory_items", [])
    details.setdefault("memory_item_counts_by_episode", {})
    details.setdefault("summaries", [])

    return {
        "feature": response.feature.value,
        "implemented": response.implemented,
        "message": response.message,
        "status": response.status,
        "available_in_version": response.available_in_version,
        "timestamp": response.timestamp.isoformat(),
        "episodes": [
            {
                "episode_id": str(episode.episode_id),
                "workflow_instance_id": str(episode.workflow_instance_id),
                "summary": episode.summary,
                "attempt_id": (
                    str(episode.attempt_id) if episode.attempt_id is not None else None
                ),
                "metadata": episode.metadata,
                "status": episode.status,
                "created_at": episode.created_at.isoformat(),
                "updated_at": episode.updated_at.isoformat(),
            }
            for episode in response.episodes
        ],
        "details": details,
    }


def serialize_runtime_introspection(
    introspection: RuntimeIntrospection,
) -> dict[str, Any]:
    return {
        "transport": introspection.transport,
        "routes": list(introspection.routes),
        "tools": list(introspection.tools),
        "resources": list(introspection.resources),
    }


def serialize_runtime_introspection_collection(
    introspections: tuple[RuntimeIntrospection, ...],
) -> list[dict[str, Any]]:
    return [
        serialize_runtime_introspection(introspection)
        for introspection in introspections
    ]


__all__ = [
    "serialize_closed_projection_failures_history",
    "serialize_get_context_response",
    "serialize_remember_episode_response",
    "serialize_runtime_introspection",
    "serialize_runtime_introspection_collection",
    "serialize_search_memory_response",
    "serialize_stub_response",
    "serialize_workflow_resume",
]
