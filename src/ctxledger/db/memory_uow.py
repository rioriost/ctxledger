from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any
from uuid import UUID

from ctxledger.workflow.service import (
    ProjectionInfo,
    ProjectionStateRepository,
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
    def __init__(self, store: dict[UUID, Workspace]) -> None:
        self._store = store

    def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        workspace = self._store.get(workspace_id)
        return replace(workspace) if workspace is not None else None

    def get_by_canonical_path(self, canonical_path: str) -> Workspace | None:
        for workspace in self._store.values():
            if workspace.canonical_path == canonical_path:
                return replace(workspace)
        return None

    def get_by_repo_url(self, repo_url: str) -> list[Workspace]:
        return [
            replace(workspace)
            for workspace in self._store.values()
            if workspace.repo_url == repo_url
        ]

    def create(self, workspace: Workspace) -> Workspace:
        self._store[workspace.workspace_id] = replace(workspace)
        return replace(workspace)

    def update(self, workspace: Workspace) -> Workspace:
        self._store[workspace.workspace_id] = replace(workspace)
        return replace(workspace)


class InMemoryWorkflowInstanceRepository(WorkflowInstanceRepository):
    def __init__(self, store: dict[UUID, WorkflowInstance]) -> None:
        self._store = store

    def get_by_id(self, workflow_instance_id: UUID) -> WorkflowInstance | None:
        workflow = self._store.get(workflow_instance_id)
        return replace(workflow) if workflow is not None else None

    def get_running_by_workspace_id(
        self,
        workspace_id: UUID,
    ) -> WorkflowInstance | None:
        running = [
            workflow
            for workflow in self._store.values()
            if workflow.workspace_id == workspace_id
            and workflow.status.value == "running"
        ]
        if not running:
            return None
        running.sort(key=lambda item: (item.updated_at, item.created_at), reverse=True)
        return replace(running[0])

    def get_latest_by_workspace_id(self, workspace_id: UUID) -> WorkflowInstance | None:
        workflows = [
            workflow
            for workflow in self._store.values()
            if workflow.workspace_id == workspace_id
        ]
        if not workflows:
            return None
        workflows.sort(
            key=lambda item: (item.updated_at, item.created_at), reverse=True
        )
        return replace(workflows[0])

    def create(self, workflow: WorkflowInstance) -> WorkflowInstance:
        self._store[workflow.workflow_instance_id] = replace(workflow)
        return replace(workflow)

    def update(self, workflow: WorkflowInstance) -> WorkflowInstance:
        self._store[workflow.workflow_instance_id] = replace(workflow)
        return replace(workflow)


class InMemoryWorkflowAttemptRepository(WorkflowAttemptRepository):
    def __init__(self, store: dict[UUID, WorkflowAttempt]) -> None:
        self._store = store

    def get_by_id(self, attempt_id: UUID) -> WorkflowAttempt | None:
        attempt = self._store.get(attempt_id)
        return replace(attempt) if attempt is not None else None

    def get_running_by_workflow_id(
        self,
        workflow_instance_id: UUID,
    ) -> WorkflowAttempt | None:
        running = [
            attempt
            for attempt in self._store.values()
            if (
                attempt.workflow_instance_id == workflow_instance_id
                and attempt.status.value == "running"
            )
        ]
        if not running:
            return None
        running.sort(
            key=lambda item: (item.attempt_number, item.updated_at, item.created_at),
            reverse=True,
        )
        return replace(running[0])

    def get_latest_by_workflow_id(
        self,
        workflow_instance_id: UUID,
    ) -> WorkflowAttempt | None:
        attempts = [
            attempt
            for attempt in self._store.values()
            if attempt.workflow_instance_id == workflow_instance_id
        ]
        if not attempts:
            return None
        attempts.sort(
            key=lambda item: (item.attempt_number, item.updated_at, item.created_at),
            reverse=True,
        )
        return replace(attempts[0])

    def get_next_attempt_number(self, workflow_instance_id: UUID) -> int:
        attempts = [
            attempt.attempt_number
            for attempt in self._store.values()
            if attempt.workflow_instance_id == workflow_instance_id
        ]
        return (max(attempts) + 1) if attempts else 1

    def create(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        self._store[attempt.attempt_id] = replace(attempt)
        return replace(attempt)

    def update(self, attempt: WorkflowAttempt) -> WorkflowAttempt:
        self._store[attempt.attempt_id] = replace(attempt)
        return replace(attempt)


class InMemoryWorkflowCheckpointRepository(WorkflowCheckpointRepository):
    def __init__(self, store: dict[UUID, WorkflowCheckpoint]) -> None:
        self._store = store

    def get_latest_by_workflow_id(
        self,
        workflow_instance_id: UUID,
    ) -> WorkflowCheckpoint | None:
        checkpoints = [
            checkpoint
            for checkpoint in self._store.values()
            if checkpoint.workflow_instance_id == workflow_instance_id
        ]
        if not checkpoints:
            return None
        checkpoints.sort(key=lambda item: item.created_at, reverse=True)
        return replace(checkpoints[0])

    def get_latest_by_attempt_id(self, attempt_id: UUID) -> WorkflowCheckpoint | None:
        checkpoints = [
            checkpoint
            for checkpoint in self._store.values()
            if checkpoint.attempt_id == attempt_id
        ]
        if not checkpoints:
            return None
        checkpoints.sort(key=lambda item: item.created_at, reverse=True)
        return replace(checkpoints[0])

    def create(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        self._store[checkpoint.checkpoint_id] = replace(checkpoint)
        return replace(checkpoint)


class InMemoryVerifyReportRepository(VerifyReportRepository):
    def __init__(self, store: dict[UUID, VerifyReport]) -> None:
        self._store = store

    def get_latest_by_attempt_id(self, attempt_id: UUID) -> VerifyReport | None:
        reports = [
            report for report in self._store.values() if report.attempt_id == attempt_id
        ]
        if not reports:
            return None
        reports.sort(key=lambda item: item.created_at, reverse=True)
        return replace(reports[0])

    def create(self, verify_report: VerifyReport) -> VerifyReport:
        self._store[verify_report.verify_id] = replace(verify_report)
        return replace(verify_report)


class InMemoryProjectionStateRepository(ProjectionStateRepository):
    def __init__(self, store: dict[tuple[UUID, UUID], ProjectionInfo]) -> None:
        self._store = store

    def get_resume_projection(
        self,
        workspace_id: UUID,
        workflow_instance_id: UUID,
    ) -> ProjectionInfo | None:
        projection = self._store.get((workspace_id, workflow_instance_id))
        return replace(projection) if projection is not None else None


class InMemoryUnitOfWork:
    def __init__(
        self,
        *,
        workspaces_store: dict[UUID, Workspace] | None = None,
        workflow_instances_store: dict[UUID, WorkflowInstance] | None = None,
        workflow_attempts_store: dict[UUID, WorkflowAttempt] | None = None,
        workflow_checkpoints_store: dict[UUID, WorkflowCheckpoint] | None = None,
        verify_reports_store: dict[UUID, VerifyReport] | None = None,
        projection_states_store: dict[tuple[UUID, UUID], ProjectionInfo] | None = None,
    ) -> None:
        self._workspaces_store = (
            workspaces_store if workspaces_store is not None else {}
        )
        self._workflow_instances_store = (
            workflow_instances_store if workflow_instances_store is not None else {}
        )
        self._workflow_attempts_store = (
            workflow_attempts_store if workflow_attempts_store is not None else {}
        )
        self._workflow_checkpoints_store = (
            workflow_checkpoints_store if workflow_checkpoints_store is not None else {}
        )
        self._verify_reports_store = (
            verify_reports_store if verify_reports_store is not None else {}
        )
        self._projection_states_store = (
            projection_states_store if projection_states_store is not None else {}
        )

        self._committed = False
        self._rolled_back = False

        self.workspaces = InMemoryWorkspaceRepository(self._workspaces_store)
        self.workflow_instances = InMemoryWorkflowInstanceRepository(
            self._workflow_instances_store
        )
        self.workflow_attempts = InMemoryWorkflowAttemptRepository(
            self._workflow_attempts_store
        )
        self.workflow_checkpoints = InMemoryWorkflowCheckpointRepository(
            self._workflow_checkpoints_store
        )
        self.verify_reports = InMemoryVerifyReportRepository(self._verify_reports_store)
        self.projection_states = InMemoryProjectionStateRepository(
            self._projection_states_store
        )

    def __enter__(self) -> InMemoryUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        if exc is not None and not self._committed:
            self.rollback()

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        self._rolled_back = True

    @property
    def committed(self) -> bool:
        return self._committed

    @property
    def rolled_back(self) -> bool:
        return self._rolled_back


def make_in_memory_uow_factory(
    *,
    workspaces_store: dict[UUID, Workspace] | None = None,
    workflow_instances_store: dict[UUID, WorkflowInstance] | None = None,
    workflow_attempts_store: dict[UUID, WorkflowAttempt] | None = None,
    workflow_checkpoints_store: dict[UUID, WorkflowCheckpoint] | None = None,
    verify_reports_store: dict[UUID, VerifyReport] | None = None,
    projection_states_store: dict[tuple[UUID, UUID], ProjectionInfo] | None = None,
) -> Callable[[], InMemoryUnitOfWork]:
    shared_workspaces_store = workspaces_store if workspaces_store is not None else {}
    shared_workflow_instances_store = (
        workflow_instances_store if workflow_instances_store is not None else {}
    )
    shared_workflow_attempts_store = (
        workflow_attempts_store if workflow_attempts_store is not None else {}
    )
    shared_workflow_checkpoints_store = (
        workflow_checkpoints_store if workflow_checkpoints_store is not None else {}
    )
    shared_verify_reports_store = (
        verify_reports_store if verify_reports_store is not None else {}
    )
    shared_projection_states_store = (
        projection_states_store if projection_states_store is not None else {}
    )

    def factory() -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(
            workspaces_store=shared_workspaces_store,
            workflow_instances_store=shared_workflow_instances_store,
            workflow_attempts_store=shared_workflow_attempts_store,
            workflow_checkpoints_store=shared_workflow_checkpoints_store,
            verify_reports_store=shared_verify_reports_store,
            projection_states_store=shared_projection_states_store,
        )

    return factory
