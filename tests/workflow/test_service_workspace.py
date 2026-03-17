from __future__ import annotations

from uuid import uuid4

from ctxledger.workflow.service import (
    RegisterWorkspaceInput,
    WorkspaceNotFoundError,
    WorkspaceRegistrationConflictError,
)

from .conftest import make_service_and_uow, register_workspace


def test_register_workspace_creates_workspace() -> None:
    service, uow = make_service_and_uow()

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo.git",
            canonical_path="/tmp/repo",
            default_branch="main",
            metadata={"language": "python"},
        )
    )

    assert workspace.workspace_id in uow.workspaces_by_id
    assert workspace.repo_url == "https://example.com/org/repo.git"
    assert workspace.canonical_path == "/tmp/repo"
    assert workspace.default_branch == "main"
    assert workspace.metadata == {"language": "python"}


def test_register_workspace_rejects_canonical_path_conflict_without_workspace_id() -> (
    None
):
    service, _ = make_service_and_uow()
    register_workspace(service)

    try:
        service.register_workspace(
            RegisterWorkspaceInput(
                repo_url="https://example.com/org/other.git",
                canonical_path="/tmp/repo",
                default_branch="main",
            )
        )
    except WorkspaceRegistrationConflictError as exc:
        assert exc.code == "workspace_registration_conflict"
        assert "canonical_path" in str(exc)
    else:
        raise AssertionError("Expected WorkspaceRegistrationConflictError")


def test_register_workspace_updates_existing_workspace_with_explicit_workspace_id() -> (
    None
):
    service, _ = make_service_and_uow()
    workspace = register_workspace(service)

    updated = service.register_workspace(
        RegisterWorkspaceInput(
            workspace_id=workspace.workspace_id,
            repo_url=workspace.repo_url,
            canonical_path=workspace.canonical_path,
            default_branch="develop",
            metadata={"team": "platform"},
        )
    )

    assert updated.workspace_id == workspace.workspace_id
    assert updated.repo_url == workspace.repo_url
    assert updated.canonical_path == workspace.canonical_path
    assert updated.default_branch == "develop"
    assert updated.metadata == {"team": "platform"}
    assert updated.created_at == workspace.created_at
    assert updated.updated_at >= workspace.updated_at


def test_register_workspace_rejects_repo_url_conflict_without_workspace_id() -> None:
    service, _ = make_service_and_uow()
    register_workspace(service)

    try:
        service.register_workspace(
            RegisterWorkspaceInput(
                repo_url="https://example.com/org/repo.git",
                canonical_path="/tmp/another-repo",
                default_branch="main",
            )
        )
    except WorkspaceRegistrationConflictError as exc:
        assert exc.code == "workspace_registration_conflict"
        assert "repo_url" in str(exc)
    else:
        raise AssertionError("Expected WorkspaceRegistrationConflictError")


def test_register_workspace_raises_when_explicit_workspace_id_is_unknown() -> None:
    service, _ = make_service_and_uow()

    try:
        service.register_workspace(
            RegisterWorkspaceInput(
                workspace_id=uuid4(),
                repo_url="https://example.com/org/repo.git",
                canonical_path="/tmp/repo",
                default_branch="main",
            )
        )
    except WorkspaceNotFoundError as exc:
        assert exc.code == "workspace_not_found"
    else:
        raise AssertionError("Expected WorkspaceNotFoundError")


def test_register_workspace_rejects_canonical_path_belonging_to_another_workspace() -> (
    None
):
    service, _ = make_service_and_uow()
    first = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-a.git",
            canonical_path="/tmp/repo-a",
            default_branch="main",
        )
    )
    second = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-b.git",
            canonical_path="/tmp/repo-b",
            default_branch="main",
        )
    )

    try:
        service.register_workspace(
            RegisterWorkspaceInput(
                workspace_id=second.workspace_id,
                repo_url=second.repo_url,
                canonical_path=first.canonical_path,
                default_branch=second.default_branch,
            )
        )
    except WorkspaceRegistrationConflictError as exc:
        assert exc.code == "workspace_registration_conflict"
        assert "canonical_path belongs to another workspace" in str(exc)
    else:
        raise AssertionError("Expected WorkspaceRegistrationConflictError")


def test_register_workspace_rejects_repo_url_belonging_to_another_workspace() -> None:
    service, _ = make_service_and_uow()
    first = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-a.git",
            canonical_path="/tmp/repo-a",
            default_branch="main",
        )
    )
    second = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-b.git",
            canonical_path="/tmp/repo-b",
            default_branch="main",
        )
    )

    try:
        service.register_workspace(
            RegisterWorkspaceInput(
                workspace_id=second.workspace_id,
                repo_url=first.repo_url,
                canonical_path=second.canonical_path,
                default_branch=second.default_branch,
            )
        )
    except WorkspaceRegistrationConflictError as exc:
        assert exc.code == "workspace_registration_conflict"
        assert "repo_url belongs to another workspace" in str(exc)
    else:
        raise AssertionError("Expected WorkspaceRegistrationConflictError")
