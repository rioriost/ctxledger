from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ctxledger.config import ProjectionSettings
from ctxledger.workflow.service import (
    ProjectionArtifactType,
    ProjectionStatus,
    RecordProjectionFailureInput,
    RecordProjectionStateInput,
    ResumableStatus,
    ResumeWorkflowInput,
    WorkflowResume,
    WorkflowService,
)


class ProjectionWriteError(RuntimeError):
    """Raised when a projection cannot be written safely."""


@dataclass(frozen=True, slots=True)
class ResumeProjectionResult:
    json_path: Path | None
    markdown_path: Path | None
    state_updates: tuple[RecordProjectionStateInput, ...]
    failure_updates: tuple[RecordProjectionFailureInput, ...] = ()


@dataclass(frozen=True, slots=True)
class ResumeProjectionWriter:
    workflow_service: WorkflowService
    projection_settings: ProjectionSettings

    def write_resume_projection(
        self,
        *,
        workspace_root: str | Path,
        workflow_instance_id: Any,
        workspace_id: Any,
    ) -> ResumeProjectionResult:
        workspace_root_path = Path(workspace_root).expanduser().resolve()
        projection_root = self._projection_root(workspace_root_path)

        resume = self.workflow_service.resume_workflow(
            ResumeWorkflowInput(workflow_instance_id=workflow_instance_id)
        )

        json_path: Path | None = None
        markdown_path: Path | None = None
        state_updates: list[RecordProjectionStateInput] = []
        failure_updates: list[RecordProjectionFailureInput] = []

        projection_root.mkdir(parents=True, exist_ok=True)

        if self.projection_settings.write_json:
            json_path = self._safe_projection_path(
                workspace_root_path,
                projection_root / "resume.json",
            )
            try:
                json_path.write_text(
                    self._build_resume_json(resume),
                    encoding="utf-8",
                )
                state_updates.append(
                    self._build_state_update(
                        workspace_id=workspace_id,
                        workflow_instance_id=workflow_instance_id,
                        projection_type=ProjectionArtifactType.RESUME_JSON,
                        target_path=self._relative_target_path(
                            workspace_root_path, json_path
                        ),
                    )
                )
            except Exception as exc:
                failure_updates.append(
                    self._build_failure_update(
                        workspace_id=workspace_id,
                        workflow_instance_id=workflow_instance_id,
                        attempt_id=(
                            resume.attempt.attempt_id
                            if resume.attempt is not None
                            else None
                        ),
                        projection_type=ProjectionArtifactType.RESUME_JSON,
                        target_path=self._relative_target_path(
                            workspace_root_path, json_path
                        ),
                        exc=exc,
                    )
                )
                state_updates.append(
                    self._build_failed_state_update(
                        workspace_id=workspace_id,
                        workflow_instance_id=workflow_instance_id,
                        projection_type=ProjectionArtifactType.RESUME_JSON,
                        target_path=self._relative_target_path(
                            workspace_root_path, json_path
                        ),
                    )
                )

        if self.projection_settings.write_markdown:
            markdown_path = self._safe_projection_path(
                workspace_root_path,
                projection_root / "resume.md",
            )
            try:
                markdown_path.write_text(
                    self._build_resume_markdown(resume),
                    encoding="utf-8",
                )
                state_updates.append(
                    self._build_state_update(
                        workspace_id=workspace_id,
                        workflow_instance_id=workflow_instance_id,
                        projection_type=ProjectionArtifactType.RESUME_MD,
                        target_path=self._relative_target_path(
                            workspace_root_path,
                            markdown_path,
                        ),
                    )
                )
            except Exception as exc:
                failure_updates.append(
                    self._build_failure_update(
                        workspace_id=workspace_id,
                        workflow_instance_id=workflow_instance_id,
                        attempt_id=(
                            resume.attempt.attempt_id
                            if resume.attempt is not None
                            else None
                        ),
                        projection_type=ProjectionArtifactType.RESUME_MD,
                        target_path=self._relative_target_path(
                            workspace_root_path,
                            markdown_path,
                        ),
                        exc=exc,
                    )
                )
                state_updates.append(
                    self._build_failed_state_update(
                        workspace_id=workspace_id,
                        workflow_instance_id=workflow_instance_id,
                        projection_type=ProjectionArtifactType.RESUME_MD,
                        target_path=self._relative_target_path(
                            workspace_root_path,
                            markdown_path,
                        ),
                    )
                )

        return ResumeProjectionResult(
            json_path=json_path,
            markdown_path=markdown_path,
            state_updates=tuple(state_updates),
            failure_updates=tuple(failure_updates),
        )

    def write_and_reconcile_resume_projection(
        self,
        *,
        workspace_root: str | Path,
        workflow_instance_id: Any,
        workspace_id: Any,
    ) -> ResumeProjectionResult:
        result = self.write_resume_projection(
            workspace_root=workspace_root,
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
        )
        self.workflow_service.reconcile_resume_projection(
            success_updates=result.state_updates,
            failure_updates=result.failure_updates,
        )
        return result

    def _projection_root(self, workspace_root: Path) -> Path:
        directory_name = self.projection_settings.directory_name.strip()
        if not directory_name:
            raise ProjectionWriteError("Projection directory name must not be empty")

        candidate = workspace_root / directory_name
        return self._safe_projection_path(workspace_root, candidate)

    def _safe_projection_path(self, workspace_root: Path, candidate: Path) -> Path:
        resolved_root = workspace_root.resolve()
        resolved_candidate = candidate.resolve()

        try:
            resolved_candidate.relative_to(resolved_root)
        except ValueError as exc:
            raise ProjectionWriteError(
                "Projection path must stay within the workspace root"
            ) from exc

        return resolved_candidate

    def _relative_target_path(self, workspace_root: Path, target_path: Path) -> str:
        return target_path.relative_to(workspace_root).as_posix()

    def _build_state_update(
        self,
        *,
        workspace_id: Any,
        workflow_instance_id: Any,
        projection_type: ProjectionArtifactType,
        target_path: str,
    ) -> RecordProjectionStateInput:
        return RecordProjectionStateInput(
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=projection_type,
            status=ProjectionStatus.FRESH,
            target_path=target_path,
        )

    def _build_failed_state_update(
        self,
        *,
        workspace_id: Any,
        workflow_instance_id: Any,
        projection_type: ProjectionArtifactType,
        target_path: str,
    ) -> RecordProjectionStateInput:
        return RecordProjectionStateInput(
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            projection_type=projection_type,
            status=ProjectionStatus.FAILED,
            target_path=target_path,
        )

    def _build_failure_update(
        self,
        *,
        workspace_id: Any,
        workflow_instance_id: Any,
        attempt_id: Any,
        projection_type: ProjectionArtifactType,
        target_path: str,
        exc: Exception,
    ) -> RecordProjectionFailureInput:
        error_code = getattr(exc, "code", None)
        return RecordProjectionFailureInput(
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            attempt_id=attempt_id,
            projection_type=projection_type,
            target_path=target_path,
            error_message=str(exc),
            error_code=error_code if isinstance(error_code, str) else None,
        )

    def _build_resume_json(self, resume: WorkflowResume) -> str:
        payload = {
            "workspace": {
                "workspace_id": str(resume.workspace.workspace_id),
                "repo_url": resume.workspace.repo_url,
                "canonical_path": resume.workspace.canonical_path,
                "default_branch": resume.workspace.default_branch,
                "metadata": resume.workspace.metadata,
            },
            "workflow": {
                "workflow_instance_id": str(
                    resume.workflow_instance.workflow_instance_id
                ),
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
        return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    def _build_resume_markdown(self, resume: WorkflowResume) -> str:
        lines: list[str] = []

        lines.append("# Resume")
        lines.append("")
        lines.append(f"- Workflow: `{resume.workflow_instance.workflow_instance_id}`")
        lines.append(f"- Ticket: `{resume.workflow_instance.ticket_id}`")
        lines.append(f"- Status: `{resume.workflow_instance.status.value}`")
        lines.append(f"- Resumable: `{resume.resumable_status.value}`")
        lines.append("")

        lines.append("## Workspace")
        lines.append("")
        lines.append(f"- Repo URL: `{resume.workspace.repo_url}`")
        lines.append(f"- Canonical path: `{resume.workspace.canonical_path}`")
        lines.append(f"- Default branch: `{resume.workspace.default_branch}`")
        lines.append("")

        lines.append("## Attempt")
        lines.append("")
        if resume.attempt is None:
            lines.append("- No attempt available")
        else:
            lines.append(f"- Attempt id: `{resume.attempt.attempt_id}`")
            lines.append(f"- Attempt number: `{resume.attempt.attempt_number}`")
            lines.append(f"- Attempt status: `{resume.attempt.status.value}`")
            if resume.attempt.verify_status is not None:
                lines.append(f"- Verify status: `{resume.attempt.verify_status.value}`")
        lines.append("")

        lines.append("## Latest checkpoint")
        lines.append("")
        if resume.latest_checkpoint is None:
            lines.append("- No checkpoint available")
        else:
            lines.append(f"- Step: `{resume.latest_checkpoint.step_name}`")
            if resume.latest_checkpoint.summary:
                lines.append(f"- Summary: {resume.latest_checkpoint.summary}")
            next_action = resume.latest_checkpoint.checkpoint_json.get(
                "next_intended_action"
            )
            if isinstance(next_action, str) and next_action.strip():
                lines.append(f"- Next intended action: {next_action.strip()}")
        lines.append("")

        lines.append("## Projections")
        lines.append("")
        if not resume.projections:
            lines.append("- No projection metadata available")
        else:
            for projection in resume.projections:
                lines.append(f"- Projection type: `{projection.projection_type.value}`")
                lines.append(f"  - Projection status: `{projection.status.value}`")
                if projection.target_path:
                    lines.append(f"  - Target path: `{projection.target_path}`")
                lines.append(
                    f"  - Open failure count: `{projection.open_failure_count}`"
                )
        lines.append("")

        lines.append("## Warnings")
        lines.append("")
        if not resume.warnings:
            lines.append("- None")
        else:
            for warning in resume.warnings:
                lines.append(f"- `{warning.code}`: {warning.message}")
        lines.append("")

        lines.append("## Next hint")
        lines.append("")
        lines.append(resume.next_hint or "No next hint available.")
        lines.append("")

        lines.append("## Resume status summary")
        lines.append("")
        lines.append(self._status_summary(resume.resumable_status))
        lines.append("")

        return "\n".join(lines)

    def _status_summary(self, status: ResumableStatus) -> str:
        if status == ResumableStatus.RESUMABLE:
            return "Workflow can be resumed from the latest checkpoint."
        if status == ResumableStatus.TERMINAL:
            return "Workflow is terminal and should be inspected, not resumed."
        if status == ResumableStatus.BLOCKED:
            return "Workflow is blocked and requires additional canonical progress."
        return "Workflow state is inconsistent and requires investigation."
