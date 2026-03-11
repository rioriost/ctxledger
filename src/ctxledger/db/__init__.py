from __future__ import annotations

from dataclasses import replace
from typing import Callable

from ctxledger.workflow.service import (
    ProjectionInfo,
    ProjectionStateRepository,
    UnitOfWork,
    VerifyReport,
    VerifyReportRepository,
    WorkflowAttempt,
    WorkflowAttemptRepository,
    WorkflowCheckpoint,
    WorkflowCheckpointRepository,
    WorkflowInstance,
    WorkflowInstanceRepository,
    Workspace,
    WorkspaceRepository,
)


class InMemoryWorkspaceRepository(WorkspaceRepository):
    def __init__(
        self,
        workspaces_by_id: dict[object, Workspace],
        workspaces_by_canonical_path: dict[str, object],
    ) -> None:
        self._workspaces_by_id = workspaces_by_id
        self._workspaces_by_canonical_path = workspaces_by_canonical_path

    def get_by_id(self, workspace_id: object) -> Workspace | None:
        return self._workspaces_by_id.get(workspace_id)

    def get_by_canonical_path(self, canonical_path: str) -> Workspace | None:
        workspace_id = self._workspaces_by_canonical_path.get(canonical_path)
        if workspace_id is None:
            return None
        return self._workspaces_by_id.get(workspace_id)

    def get_by_repo_url(self, repo_url: str) -> list[Workspace]:
        return [
            workspace
            for workspace in self._workspaces_by_id.values()
            if workspace.repo_url == repo_url
        ]

    def create(self, workspace: Workspace) -> Workspace:
        self._workspaces_by_id[workspace.workspace_id] = workspace
        self._workspaces_by_canonical_path[workspace.canonical_path] = (
            workspace.workspace_id
        )
        return workspace

    def update(self, workspace: Workspace) -> Workspace:
        existing = self._workspaces_by_id.get(workspace.workspace_id)
        if existing is not None and existing.canonical_path != workspace.canonical_path:
            self._workspaces_by_canonical_path.pop(existing.canonical_path, None)

        self._workspaces_by_id[workspace.workspace_id] = workspace
        self._workspaces_by_canonical_path[workspace.canonical_path] = (
            workspace.workspace_id
        )
        return workspace


class InMemoryWorkflowInstanceRepository(WorkflowInstanceRepository):
    def __init__(self, workflows_by_id: dict[object, WorkflowInstance]) -> None:
        self._workflows_by_id = workflows_by_id

    def get_by_id(self, workflow_instance_id: object) -> WorkflowInstance | None:
        return self._workflows_by_id.get(workflow_instance_id)

    def get_running_by_workspace_id(
        self, workspace_id: object
    ) -> WorkflowInstance | None:
        workflows = [
            workflow
            for workflow in self._workflows_by_id.values()
            if workflow.workspace_id == workspace_id
            and workflow.status.value == "running"
        ]
        workflows.sort(key=lambda workflow: workflow.created_at, reverse=True)
        return workflows[0] if workflows else None

    def get_latest_by_workspace_id(
        self, workspace_id: object
    ) -> WorkflowInstance | None:
        workflows = [
            workflow
            for workflow in self._workflows_by_id.values()
            if workflow.workspace_id == workspace_id
        ]
        workflows.sort(key=lambda workflow: workflow.updated_at, reverse=True)
        return workflows[0] if workflows else None

    def create(self, workflow: WorkflowInstance) -> WorkflowInstance:
        self._workflows_by_id[workflow.workflow_instance_id] = workflow
        return workflow

    def update(self, workflow: WorkflowInstance) -> WorkflowInstance:
        self._workflows_by_id[workflow.workflow_instance_id] = workflow
        return workflow


class InMemoryWorkflowAttemptRepository(WorkflowAttemptRepository):
    def __init__(self, attempts_by_id: dict[object, WorkflowAttempt]) -> None:
        self._attempts_by_id = attempts_by_id

    def get_by_id(self, attempt_id: object) -> WorkflowAttempt | None:
        return self._attempts_by_id.get(attempt_id)

    def get_running_by_workflow_id(
        self, workflow_instance_id: object
    ) -> WorkflowAttempt | None:
        attempts = [
            attempt
            for attempt in self._attempts_by_id.values()
            if (
                attempt.workflow_instance_id == workflow_instance_id
                and attempt.status.value == "running"
            )
        ]
        attempts.sort(key=lambda attempt: attempt.started_at, reverse=True)
        return attempts[0] if attempts else None

    def get_latest_by_workflow_id(
        self, workflow_instance_id: object
    ) -> WorkflowAttempt | None:
        attempts = [
            attempt
            for attempt in self._attempts_by_id.values()
            if attempt.workflow_instance_id == workflow_instance_id
        ]
        attempts.sort(
            key=lambda attempt: (attempt.attempt_number, attempt.started_at),
            reverse=True,
        )
        return attempts[0] if attempts else None

    def get_next_attempt_number(self, workflow_instance_id: object) -> int:
        attempts = [
            attempt.attempt_number
            for attempt in self._attempts_by_id.values()
            if attempt.workflow_instance_id == workflow_instance_id
        ]
        return (max(attempts) + 1) if attempts else 1

    def create(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        self._attempts_by_id[attempt.attempt_id] = attempt
        return attempt

    def update(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        self._attempts_by_id[attempt.attempt_id] = attempt
        return attempt


class InMemoryWorkflowCheckpointRepository(WorkflowCheckpointRepository):
    def __init__(self, checkpoints_by_id: dict[object, WorkflowCheckpoint]) -> None:
        self._checkpoints_by_id = checkpoints_by_id

    def get_latest_by_workflow_id(
        self, workflow_instance_id: object
    ) -> WorkflowCheckpoint | None:
        checkpoints = [
            checkpoint
            for checkpoint in self._checkpoints_by_id.values()
            if checkpoint.workflow_instance_id == workflow_instance_id
        ]
        checkpoints.sort(key=lambda checkpoint: checkpoint.created_at, reverse=True)
        return checkpoints[0] if checkpoints else None

    def get_latest_by_attempt_id(self, attempt_id: object) -> WorkflowCheckpoint | None:
        checkpoints = [
            checkpoint
            for checkpoint in self._checkpoints_by_id.values()
            if checkpoint.attempt_id == attempt_id
        ]
        checkpoints.sort(key=lambda checkpoint: checkpoint.created_at, reverse=True)
        return checkpoints[0] if checkpoints else None

    def create(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        self._checkpoints_by_id[checkpoint.checkpoint_id] = checkpoint
        return checkpoint


class InMemoryVerifyReportRepository(VerifyReportRepository):
    def __init__(self, verify_reports_by_id: dict[object, VerifyReport]) -> None:
        self._verify_reports_by_id = verify_reports_by_id

    def get_latest_by_attempt_id(self, attempt_id: object) -> VerifyReport | None:
        verify_reports = [
            verify_report
            for verify_report in self._verify_reports_by_id.values()
            if verify_report.attempt_id == attempt_id
        ]
        verify_reports.sort(key=lambda report: report.created_at, reverse=True)
        return verify_reports[0] if verify_reports else None

    def create(self, verify_report: VerifyReport) -> VerifyReport:
        self._verify_reports_by_id[verify_report.verify_id] = verify_report
        return verify_report


class InMemoryProjectionStateRepository(ProjectionStateRepository):
    def __init__(
        self,
        projection_states_by_key: dict[tuple[object, object], ProjectionInfo],
    ) -> None:
        self._projection_states_by_key = projection_states_by_key

    def get_resume_projection(
        self,
        workspace_id: object,
        workflow_instance_id: object,
    ) -> ProjectionInfo | None:
        return self._projection_states_by_key.get((workspace_id, workflow_instance_id))

    def set_resume_projection(
        self,
        workspace_id: object,
        workflow_instance_id: object,
        projection: ProjectionInfo,
    ) -> None:
        self._projection_states_by_key[(workspace_id, workflow_instance_id)] = (
            projection
        )


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(
        self,
        *,
        workspaces_by_id: dict[object, Workspace] | None = None,
        workspaces_by_canonical_path: dict[str, object] | None = None,
        workflows_by_id: dict[object, WorkflowInstance] | None = None,
        attempts_by_id: dict[object, WorkflowAttempt] | None = None,
        checkpoints_by_id: dict[object, WorkflowCheckpoint] | None = None,
        verify_reports_by_id: dict[object, VerifyReport] | None = None,
        projection_states_by_key: dict[tuple[object, object], ProjectionInfo]
        | None = None,
    ) -> None:
        self._workspaces_by_id = workspaces_by_id or {}
        self._workspaces_by_canonical_path = workspaces_by_canonical_path or {}
        self._workflows_by_id = workflows_by_id or {}
        self._attempts_by_id = attempts_by_id or {}
        self._checkpoints_by_id = checkpoints_by_id or {}
        self._verify_reports_by_id = verify_reports_by_id or {}
        self._projection_states_by_key = projection_states_by_key or {}

        self._committed = False
        self._rolled_back = False

        self.workspaces = InMemoryWorkspaceRepository(
            self._workspaces_by_id,
            self._workspaces_by_canonical_path,
        )
        self.workflow_instances = InMemoryWorkflowInstanceRepository(
            self._workflows_by_id
        )
        self.workflow_attempts = InMemoryWorkflowAttemptRepository(self._attempts_by_id)
        self.workflow_checkpoints = InMemoryWorkflowCheckpointRepository(
            self._checkpoints_by_id
        )
        self.verify_reports = InMemoryVerifyReportRepository(self._verify_reports_by_id)
        self.projection_states = InMemoryProjectionStateRepository(
            self._projection_states_by_key
        )

    def __enter__(self) -> InMemoryUnitOfWork:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is not None and not self._committed:
            self.rollback()

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        self._rolled_back = True


@dataclass(slots=True)
class InMemoryStore:
    workspaces_by_id: dict[object, Workspace]
    workspaces_by_canonical_path: dict[str, object]
    workflows_by_id: dict[object, WorkflowInstance]
    attempts_by_id: dict[object, WorkflowAttempt]
    checkpoints_by_id: dict[object, WorkflowCheckpoint]
    verify_reports_by_id: dict[object, VerifyReport]
    projection_states_by_key: dict[tuple[object, object], ProjectionInfo]

    @classmethod
    def create(cls) -> InMemoryStore:
        return cls(
            workspaces_by_id={},
            workspaces_by_canonical_path={},
            workflows_by_id={},
            attempts_by_id={},
            checkpoints_by_id={},
            verify_reports_by_id={},
            projection_states_by_key={},
        )

    def snapshot(self) -> InMemoryStore:
        return InMemoryStore(
            workspaces_by_id=dict(self.workspaces_by_id),
            workspaces_by_canonical_path=dict(self.workspaces_by_canonical_path),
            workflows_by_id=dict(self.workflows_by_id),
            attempts_by_id=dict(self.attempts_by_id),
            checkpoints_by_id=dict(self.checkpoints_by_id),
            verify_reports_by_id=dict(self.verify_reports_by_id),
            projection_states_by_key=dict(self.projection_states_by_key),
        )


def build_in_memory_uow_factory(
    store: InMemoryStore | None = None,
) -> Callable[[], InMemoryUnitOfWork]:
    backing_store = store or InMemoryStore.create()

    def _factory() -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(
            workspaces_by_id=backing_store.workspaces_by_id,
            workspaces_by_canonical_path=backing_store.workspaces_by_canonical_path,
            workflows_by_id=backing_store.workflows_by_id,
            attempts_by_id=backing_store.attempts_by_id,
            checkpoints_by_id=backing_store.checkpoints_by_id,
            verify_reports_by_id=backing_store.verify_reports_by_id,
            projection_states_by_key=backing_store.projection_states_by_key,
        )

    return _factory


__all__ = [
    "InMemoryProjectionStateRepository",
    "InMemoryStore",
    "InMemoryUnitOfWork",
    "InMemoryVerifyReportRepository",
    "InMemoryWorkflowAttemptRepository",
    "InMemoryWorkflowCheckpointRepository",
    "InMemoryWorkflowInstanceRepository",
    "InMemoryWorkspaceRepository",
    "build_in_memory_uow_factory",
]
