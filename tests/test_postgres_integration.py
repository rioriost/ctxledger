from __future__ import annotations

import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import pytest

from ctxledger.config import (
    EmbeddingProvider,
    EmbeddingSettings,
    ProjectionSettings,
    load_settings,
)
from ctxledger.db.postgres import PostgresConfig, build_postgres_uow_factory
from ctxledger.memory.embeddings import (
    EmbeddingRequest,
    EmbeddingResult,
    ExternalAPIEmbeddingGenerator,
    build_embedding_generator,
    compute_content_hash,
)
from ctxledger.memory.service import (
    EmbeddingGenerator,
    GetMemoryContextRequest,
    MemoryFeature,
    MemoryService,
    RememberEpisodeRequest,
    SearchMemoryRequest,
    UnitOfWorkEpisodeRepository,
    UnitOfWorkMemoryEmbeddingRepository,
    UnitOfWorkMemoryItemRepository,
    UnitOfWorkWorkflowLookupRepository,
    UnitOfWorkWorkspaceLookupRepository,
)
from ctxledger.projection.writer import ResumeProjectionWriter
from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge
from ctxledger.workflow.service import (
    CompleteWorkflowInput,
    CreateCheckpointInput,
    MemoryEmbeddingRecord,
    MemoryItemRecord,
    ProjectionArtifactType,
    ProjectionStatus,
    RecordProjectionFailureInput,
    RecordProjectionStateInput,
    RegisterWorkspaceInput,
    ResumableStatus,
    ResumeWorkflowInput,
    StartWorkflowInput,
    VerifyStatus,
    WorkflowAttemptStatus,
    WorkflowInstanceStatus,
    WorkflowService,
)

DOCKER_COMPOSE_FILE = (
    Path(__file__).resolve().parents[1] / "docker" / "docker-compose.yml"
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger"
POSTGRES_SERVICE_NAME = "postgres"
TEST_SCHEMA_PREFIX = "ctxledger_test_"


def _docker_compose_cmd(*args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "-f",
        str(DOCKER_COMPOSE_FILE),
        *args,
    ]


def _run_command(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def _run_compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run_command(*_docker_compose_cmd(*args), check=check)


def _is_docker_available() -> bool:
    try:
        completed = _run_command("docker", "--version", check=False)
    except OSError:
        return False
    return completed.returncode == 0


def _wait_for_postgres_ready(timeout_seconds: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_result: subprocess.CompletedProcess[str] | None = None

    while time.monotonic() < deadline:
        last_result = _run_compose("ps", "--format", "json", check=False)
        if last_result.returncode == 0 and "healthy" in last_result.stdout.lower():
            return
        time.sleep(1.0)

    logs = _run_compose("logs", POSTGRES_SERVICE_NAME, check=False)
    stdout = "" if last_result is None else last_result.stdout
    stderr = "" if last_result is None else last_result.stderr
    raise AssertionError(
        "PostgreSQL container did not become healthy in time.\n"
        f"stdout:\n{stdout}\n"
        f"stderr:\n{stderr}\n"
        f"logs:\n{logs.stdout}\n{logs.stderr}"
    )


def _run_psql(sql: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "ctxledger-postgres",
            "psql",
            "-U",
            "ctxledger",
            "-d",
            "ctxledger",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        input=sql,
        capture_output=True,
        check=False,
    )


def _wait_for_database_accepting_connections(timeout_seconds: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_result: subprocess.CompletedProcess[str] | None = None

    while time.monotonic() < deadline:
        last_result = _run_psql("SELECT 1;")
        if last_result.returncode == 0:
            return
        time.sleep(1.0)

    logs = _run_compose("logs", POSTGRES_SERVICE_NAME, check=False)
    stdout = "" if last_result is None else last_result.stdout
    stderr = "" if last_result is None else last_result.stderr
    raise AssertionError(
        "PostgreSQL did not start accepting connections in time.\n"
        f"stdout:\n{stdout}\n"
        f"stderr:\n{stderr}\n"
        f"logs:\n{logs.stdout}\n{logs.stderr}"
    )


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _apply_schema(schema_name: str) -> None:
    schema_path = PROJECT_ROOT / "schemas" / "postgres.sql"
    quoted_schema_name = _quote_ident(schema_name)
    schema_sql = schema_path.read_text(encoding="utf-8")
    schema_sql = schema_sql.replace(
        "CREATE OR REPLACE FUNCTION set_updated_at()",
        f"CREATE OR REPLACE FUNCTION {quoted_schema_name}.set_updated_at()",
    )
    schema_sql = schema_sql.replace(
        "EXECUTE FUNCTION set_updated_at();",
        f"EXECUTE FUNCTION {quoted_schema_name}.set_updated_at();",
    )
    completed = _run_psql(
        f"""
        CREATE SCHEMA IF NOT EXISTS {quoted_schema_name};
        SET search_path TO {quoted_schema_name}, public;
        {schema_sql}
        """
    )
    if completed.returncode != 0:
        raise AssertionError(
            "Failed to apply PostgreSQL schema.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def _wait_for_schema_ready(schema_name: str, timeout_seconds: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    sql = f"""
    SELECT EXISTS (
      SELECT 1
      FROM information_schema.tables
      WHERE table_schema = '{schema_name}'
        AND table_name = 'workspaces'
    );
    """
    last_result: subprocess.CompletedProcess[str] | None = None

    while time.monotonic() < deadline:
        last_result = _run_psql(sql)
        if last_result.returncode == 0 and "t" in last_result.stdout.lower():
            return
        time.sleep(1.0)

    logs = _run_compose("logs", POSTGRES_SERVICE_NAME, check=False)
    stdout = "" if last_result is None else last_result.stdout
    stderr = "" if last_result is None else last_result.stderr
    raise AssertionError(
        "PostgreSQL schema did not become ready in time.\n"
        f"stdout:\n{stdout}\n"
        f"stderr:\n{stderr}\n"
        f"logs:\n{logs.stdout}\n{logs.stderr}"
    )


def _ensure_schema_ready(schema_name: str) -> None:
    _wait_for_database_accepting_connections()
    _apply_schema(schema_name)
    _wait_for_schema_ready(schema_name)


def _drop_schema(schema_name: str) -> None:
    quoted_schema_name = _quote_ident(schema_name)
    completed = _run_psql(f"DROP SCHEMA IF EXISTS {quoted_schema_name} CASCADE;")
    if completed.returncode != 0:
        raise AssertionError(
            "Failed to drop PostgreSQL test schema.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


@pytest.fixture(scope="session")
def postgres_integration_environment() -> Iterator[None]:
    if not _is_docker_available():
        pytest.skip("Docker is required for PostgreSQL integration tests")

    try:
        import psycopg  # noqa: F401
    except ImportError:
        pytest.skip("psycopg is required for PostgreSQL integration tests")

    up_result = _run_compose("up", "-d", POSTGRES_SERVICE_NAME, check=False)
    if up_result.returncode != 0:
        pytest.skip(
            "Could not start PostgreSQL container for integration tests.\n"
            f"{up_result.stdout}\n{up_result.stderr}"
        )

    _wait_for_postgres_ready()
    yield


@pytest.fixture
def postgres_test_schema(
    postgres_integration_environment: None,
) -> Iterator[str]:
    schema_name = f"{TEST_SCHEMA_PREFIX}{uuid4().hex}"
    _ensure_schema_ready(schema_name)
    try:
        yield schema_name
    finally:
        _drop_schema(schema_name)


@pytest.fixture
def postgres_database_url(postgres_integration_environment: None) -> str:
    return os.getenv("CTXLEDGER_TEST_DATABASE_URL", DEFAULT_DATABASE_URL)


@pytest.fixture
def openai_test_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY is required for real OpenAI integration tests")
    return api_key


@pytest.fixture
def openai_test_model() -> str:
    return os.getenv("OPENAI_MODEL", "text-embedding-3-small")


@pytest.fixture
def openai_test_base_url() -> str:
    return os.getenv(
        "OPENAI_BASE_URL",
        "https://api.openai.com/v1/embeddings",
    )


@pytest.fixture
def clean_postgres_database(
    postgres_test_schema: str,
) -> Iterator[str]:
    yield postgres_test_schema


@pytest.fixture
def postgres_workflow_service(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> WorkflowService:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    return WorkflowService(build_postgres_uow_factory(config))


def test_postgres_workflow_service_round_trip_happy_path(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo.git",
            canonical_path="/tmp/integration-repo",
            default_branch="main",
            metadata={"suite": "integration"},
        )
    )

    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-123",
            metadata={"priority": "high"},
        )
    )

    checkpoint_result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="edit_files",
            summary="Persisted checkpoint to PostgreSQL",
            checkpoint_json={"next_intended_action": "Run tests"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    completed = service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    terminal_resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert workspace.repo_url == "https://example.com/org/repo.git"
    assert started.workflow_instance.workspace_id == workspace.workspace_id
    assert started.attempt.attempt_number == 1

    assert checkpoint_result.checkpoint.step_name == "edit_files"
    assert checkpoint_result.verify_report is not None
    assert checkpoint_result.verify_report.status == VerifyStatus.PASSED

    assert resume.workspace.workspace_id == workspace.workspace_id
    assert resume.attempt is not None
    assert resume.latest_checkpoint is not None
    assert (
        resume.latest_checkpoint.checkpoint_id
        == checkpoint_result.checkpoint.checkpoint_id
    )
    assert resume.resumable_status == ResumableStatus.RESUMABLE
    assert resume.next_hint == "Run tests"

    assert completed.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert completed.attempt.finished_at is not None
    assert completed.verify_report is not None
    assert completed.verify_report.status == VerifyStatus.PASSED

    assert terminal_resume.resumable_status == ResumableStatus.TERMINAL


def test_postgres_memory_search_returns_memory_item_based_results(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    uow_factory = build_postgres_uow_factory(config)
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-search.git",
            canonical_path="/tmp/integration-repo-memory-search",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMSEARCH-001",
        )
    )

    first_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Investigated relevant postgres root cause",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "investigation", "component": "postgres"},
        )
    )
    second_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Documented release checklist",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "docs", "component": "release"},
        )
    )

    search = memory_service.search(
        SearchMemoryRequest(
            query="postgres",
            workspace_id=str(workspace.workspace_id),
            limit=10,
            filters={},
        )
    )

    assert first_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert second_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert search.feature == MemoryFeature.SEARCH
    assert search.implemented is True
    assert search.message == "Memory-item-based lexical search completed successfully."
    assert search.details["query"] == "postgres"
    assert search.details["normalized_query"] == "postgres"
    assert search.details["workspace_id"] == str(workspace.workspace_id)
    assert search.details["limit"] == 10
    assert search.details["filters"] == {}
    assert search.details["search_mode"] == "memory_item_lexical"
    assert search.details["memory_items_considered"] == 2
    assert search.details["semantic_candidates_considered"] == 0
    assert search.details["semantic_query_generated"] is False
    assert (
        search.details["semantic_generation_skipped_reason"]
        == "embedding_search_not_configured"
    )
    assert search.details["hybrid_scoring"] == {
        "lexical_weight": 1.0,
        "semantic_weight": 1.0,
        "semantic_only_discount": 0.75,
    }
    assert search.details["results_returned"] == 1
    assert len(search.results) == 1
    assert search.results[0].workspace_id == workspace.workspace_id
    assert search.results[0].workflow_instance_id is None
    assert search.results[0].attempt_id is None
    assert search.results[0].episode_id == first_episode.episode.episode_id
    assert search.results[0].summary == "Investigated relevant postgres root cause"
    assert search.results[0].metadata == {
        "kind": "investigation",
        "component": "postgres",
    }
    assert "content" in search.results[0].matched_fields
    assert search.results[0].lexical_score > 0
    assert search.results[0].semantic_score == 0.0
    assert search.results[0].score == search.results[0].lexical_score
    assert search.results[0].ranking_details == {
        "lexical_component": search.results[0].lexical_score,
        "semantic_component": 0.0,
        "score_mode": "lexical_only",
        "semantic_only_discount_applied": False,
    }

    with uow_factory() as uow:
        assert uow.memory_items is not None
        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )

    assert [item.content for item in workspace_items] == [
        "Documented release checklist",
        "Investigated relevant postgres root cause",
    ]


def test_postgres_memory_remember_episode_persists_local_stub_embedding(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    uow_factory = build_postgres_uow_factory(config)
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        embedding_generator=build_embedding_generator(
            EmbeddingSettings(
                provider=EmbeddingProvider.LOCAL_STUB,
                model="local-stub-v1",
                api_key=None,
                base_url=None,
                dimensions=1536,
                enabled=True,
            )
        ),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-embeddings-local-stub.git",
            canonical_path="/tmp/integration-repo-memory-embeddings-local-stub",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMEMBED-LOCAL-STUB-001",
        )
    )

    episode_response = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Persist local stub embedding for memory item",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "checkpoint", "component": "memory"},
        )
    )

    assert episode_response.episode is not None

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )

        assert len(workspace_items) == 1
        created_memory_item = workspace_items[0]
        memory_embeddings = uow.memory_embeddings.list_by_memory_id(
            created_memory_item.memory_id,
            limit=10,
        )

    assert created_memory_item.workspace_id == workspace.workspace_id
    assert created_memory_item.episode_id == episode_response.episode.episode_id
    assert created_memory_item.content == "Persist local stub embedding for memory item"
    assert created_memory_item.metadata == {
        "kind": "checkpoint",
        "component": "memory",
    }

    assert len(memory_embeddings) == 1
    assert memory_embeddings[0].memory_id == created_memory_item.memory_id
    assert memory_embeddings[0].embedding_model == "local-stub-v1"
    assert len(memory_embeddings[0].embedding) == 1536
    assert memory_embeddings[0].content_hash is not None


class FakeCustomHTTPEmbeddingGenerator(EmbeddingGenerator):
    def __init__(self) -> None:
        self.requests: list[EmbeddingRequest] = []

    def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
        self.requests.append(request)
        return EmbeddingResult(
            provider="custom_http",
            model="custom-http-test-model",
            vector=(0.125,) * 1536,
            content_hash="custom-http-content-hash",
        )


def test_postgres_memory_remember_episode_persists_custom_http_embedding(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    uow_factory = build_postgres_uow_factory(config)
    workflow_service = WorkflowService(uow_factory)
    embedding_generator = FakeCustomHTTPEmbeddingGenerator()
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        embedding_generator=embedding_generator,
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-embeddings-custom-http.git",
            canonical_path="/tmp/integration-repo-memory-embeddings-custom-http",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMEMBED-CUSTOM-HTTP-001",
        )
    )

    episode_response = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Persist custom HTTP embedding for memory item",
            attempt_id=str(started.attempt.attempt_id),
            metadata={
                "kind": "checkpoint",
                "component": "memory",
                "provider": "custom_http",
            },
        )
    )

    assert episode_response.episode is not None
    assert len(embedding_generator.requests) == 1
    assert embedding_generator.requests[0].text == (
        "Persist custom HTTP embedding for memory item"
    )
    assert embedding_generator.requests[0].metadata == {
        "kind": "checkpoint",
        "component": "memory",
        "provider": "custom_http",
    }

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )

        assert len(workspace_items) == 1
        created_memory_item = workspace_items[0]
        memory_embeddings = uow.memory_embeddings.list_by_memory_id(
            created_memory_item.memory_id,
            limit=10,
        )

    assert created_memory_item.workspace_id == workspace.workspace_id
    assert created_memory_item.episode_id == episode_response.episode.episode_id
    assert (
        created_memory_item.content == "Persist custom HTTP embedding for memory item"
    )
    assert created_memory_item.metadata == {
        "kind": "checkpoint",
        "component": "memory",
        "provider": "custom_http",
    }

    assert len(memory_embeddings) == 1
    assert memory_embeddings[0].memory_id == created_memory_item.memory_id
    assert memory_embeddings[0].embedding_model == "custom-http-test-model"
    assert memory_embeddings[0].embedding == (0.125,) * 1536
    assert memory_embeddings[0].content_hash == "custom-http-content-hash"


def test_postgres_memory_remember_episode_and_search_with_real_openai_embeddings(
    postgres_database_url: str,
    clean_postgres_database: str,
    openai_test_api_key: str,
    openai_test_model: str,
    openai_test_base_url: str,
) -> None:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    uow_factory = build_postgres_uow_factory(config)
    workflow_service = WorkflowService(uow_factory)
    embedding_generator = ExternalAPIEmbeddingGenerator(
        provider=EmbeddingProvider.OPENAI,
        model=openai_test_model,
        api_key=openai_test_api_key,
        base_url=openai_test_base_url,
    )
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        embedding_generator=embedding_generator,
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-search-openai.git",
            canonical_path="/tmp/integration-repo-memory-search-openai",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMSEARCH-OPENAI-001",
        )
    )

    relevant_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Investigated projection drift root cause in deployment workflow",
            attempt_id=str(started.attempt.attempt_id),
            metadata={
                "kind": "root-cause",
                "component": "projection",
                "scope": "deployment",
            },
        )
    )
    distractor_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Documented release checklist and handoff steps",
            attempt_id=str(started.attempt.attempt_id),
            metadata={
                "kind": "docs",
                "component": "release",
                "scope": "handoff",
            },
        )
    )

    assert relevant_episode.episode is not None
    assert distractor_episode.episode is not None

    if relevant_episode.details.get("embedding_generation_skipped_reason") is not None:
        pytest.fail(
            "Real OpenAI integration test did not persist the relevant embedding: "
            f"{relevant_episode.details['embedding_generation_skipped_reason']}"
        )
    if (
        distractor_episode.details.get("embedding_generation_skipped_reason")
        is not None
    ):
        pytest.fail(
            "Real OpenAI integration test did not persist the distractor embedding: "
            f"{distractor_episode.details['embedding_generation_skipped_reason']}"
        )

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )
        assert len(workspace_items) == 2

        embeddings_by_memory_id = {
            item.memory_id: uow.memory_embeddings.list_by_memory_id(
                item.memory_id,
                limit=10,
            )
            for item in workspace_items
        }

    assert all(len(embeddings) == 1 for embeddings in embeddings_by_memory_id.values())
    assert all(
        embeddings[0].embedding_model == openai_test_model
        for embeddings in embeddings_by_memory_id.values()
    )
    assert all(
        len(embeddings[0].embedding) > 0
        for embeddings in embeddings_by_memory_id.values()
    )
    assert all(
        embeddings[0].content_hash for embeddings in embeddings_by_memory_id.values()
    )

    search = memory_service.search(
        SearchMemoryRequest(
            query="projection drift root cause",
            workspace_id=str(workspace.workspace_id),
            limit=5,
            filters={},
        )
    )

    assert search.feature == MemoryFeature.SEARCH
    assert search.implemented is True
    assert search.details["search_mode"] == "hybrid_memory_item_search"
    assert search.details["semantic_candidates_considered"] >= 1
    assert search.details["semantic_query_generated"] is True
    assert search.details["memory_items_considered"] == 2
    assert search.details["results_returned"] >= 1
    assert len(search.results) >= 1

    top_result = search.results[0]
    assert top_result.summary == (
        "Investigated projection drift root cause in deployment workflow"
    )
    assert top_result.semantic_score > 0.0
    assert (
        "embedding_similarity" in top_result.matched_fields
        or "content" in top_result.matched_fields
    )
    assert top_result.score > 0.0
    assert top_result.ranking_details["semantic_component"] > 0.0


def test_postgres_workflow_complete_auto_records_memory_and_embedding(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    uow_factory = build_postgres_uow_factory(config)
    workflow_service = WorkflowService(
        uow_factory,
        workflow_memory_bridge=WorkflowMemoryBridge(
            episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
            memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
            memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(
                uow_factory
            ),
            embedding_generator=build_embedding_generator(
                EmbeddingSettings(
                    provider=EmbeddingProvider.LOCAL_STUB,
                    model="local-stub-v1",
                    api_key=None,
                    base_url=None,
                    dimensions=1536,
                    enabled=True,
                )
            ),
        ),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-memory.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-memory",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-COMPLETE-001",
        )
    )
    checkpoint_result = workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="validate_openai",
            summary="Broader targeted regression is green",
            checkpoint_json={"next_intended_action": "Review diff and commit"},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Validated OpenAI embedding integration end to end",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )

        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]
        assert len(auto_episodes) == 1
        auto_episode = auto_episodes[0]

        episode_memory_items = uow.memory_items.list_by_episode_id(
            auto_episode.episode_id,
            limit=10,
        )
        assert len(episode_memory_items) == 1
        auto_memory_item = episode_memory_items[0]

        memory_embeddings = uow.memory_embeddings.list_by_memory_id(
            auto_memory_item.memory_id,
            limit=10,
        )

    assert completed.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert completed.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert checkpoint_result.verify_report is not None
    assert checkpoint_result.verify_report.status == VerifyStatus.PASSED

    assert auto_episode.workflow_instance_id == (
        started.workflow_instance.workflow_instance_id
    )
    assert auto_episode.attempt_id == started.attempt.attempt_id
    assert auto_episode.metadata == {
        "auto_generated": True,
        "memory_origin": "workflow_complete_auto",
        "workflow_status": "completed",
        "attempt_status": "succeeded",
        "attempt_number": 1,
        "verify_status": "passed",
        "step_name": "validate_openai",
        "next_intended_action": "Review diff and commit",
    }
    assert "Completion summary: Validated OpenAI embedding integration end to end" in (
        auto_episode.summary
    )
    assert "Latest checkpoint summary: Broader targeted regression is green" in (
        auto_episode.summary
    )
    assert "Last planned next action: Review diff and commit" in auto_episode.summary
    assert "Verify status: passed" in auto_episode.summary

    assert auto_memory_item.workspace_id == workspace.workspace_id
    assert auto_memory_item.episode_id == auto_episode.episode_id
    assert auto_memory_item.type == "workflow_completion_note"
    assert auto_memory_item.provenance == "workflow_complete_auto"
    assert auto_memory_item.content == auto_episode.summary
    assert auto_memory_item.metadata == auto_episode.metadata

    assert len(memory_embeddings) == 1
    assert memory_embeddings[0].memory_id == auto_memory_item.memory_id
    assert memory_embeddings[0].embedding_model == "local-stub-v1"
    assert len(memory_embeddings[0].embedding) == 1536
    assert memory_embeddings[0].content_hash is not None


def test_postgres_workflow_complete_auto_memory_is_searchable(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    uow_factory = build_postgres_uow_factory(config)
    workflow_service = WorkflowService(
        uow_factory,
        workflow_memory_bridge=WorkflowMemoryBridge(
            episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
            memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
            memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(
                uow_factory
            ),
            embedding_generator=build_embedding_generator(
                EmbeddingSettings(
                    provider=EmbeddingProvider.LOCAL_STUB,
                    model="local-stub-v1",
                    api_key=None,
                    base_url=None,
                    dimensions=1536,
                    enabled=True,
                )
            ),
        ),
    )
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        embedding_generator=build_embedding_generator(
            EmbeddingSettings(
                provider=EmbeddingProvider.LOCAL_STUB,
                model="local-stub-v1",
                api_key=None,
                base_url=None,
                dimensions=1536,
                enabled=True,
            )
        ),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-workflow-complete-auto-search.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-search",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-SEARCH-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="investigate_projection_drift",
            summary="Investigated projection drift root cause in deployment workflow",
            checkpoint_json={
                "next_intended_action": "Write fix and validate semantic retrieval"
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Validated projection drift fix and semantic retrieval",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    search = memory_service.search(
        SearchMemoryRequest(
            query="projection drift root cause",
            workspace_id=str(workspace.workspace_id),
            limit=5,
            filters={},
        )
    )

    assert completed.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert completed.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert completed.auto_memory_details is not None
    assert completed.auto_memory_details["auto_memory_recorded"] is True
    assert completed.auto_memory_details["embedding_persistence_status"] == "stored"
    assert completed.warnings == ()

    assert search.feature == MemoryFeature.SEARCH
    assert search.implemented is True
    assert search.details["search_mode"] == "hybrid_memory_item_search"
    assert search.details["semantic_candidates_considered"] >= 1
    assert search.details["semantic_query_generated"] is True
    assert search.details["memory_items_considered"] >= 1
    assert search.details["results_returned"] >= 1
    assert len(search.results) >= 1

    top_result = search.results[0]
    assert (
        top_result.summary == "Workflow completed with status `completed`.\n"
        "Completion summary: Validated projection drift fix and semantic retrieval\n"
        "Latest checkpoint summary: Investigated projection drift root cause in deployment workflow\n"
        "Last planned next action: Write fix and validate semantic retrieval\n"
        "Verify status: passed"
    )
    assert top_result.semantic_score > 0.0
    assert top_result.score > 0.0
    assert top_result.ranking_details["semantic_component"] > 0.0
    assert top_result.metadata == {
        "auto_generated": True,
        "memory_origin": "workflow_complete_auto",
        "workflow_status": "completed",
        "attempt_status": "succeeded",
        "attempt_number": 1,
        "verify_status": "passed",
        "step_name": "investigate_projection_drift",
        "next_intended_action": "Write fix and validate semantic retrieval",
    }
    assert (
        "embedding_similarity" in top_result.matched_fields
        or "content" in top_result.matched_fields
    )


def test_postgres_memory_search_hybrid_results_include_ranking_details(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    uow_factory = build_postgres_uow_factory(config)
    workflow_service = WorkflowService(uow_factory)

    class FixedHybridEmbeddingGenerator(EmbeddingGenerator):
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            if request.text == "projection drift root cause":
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v1",
                    vector=(1.0,) + (0.0,) * 1535,
                    content_hash="query-hash",
                )

            if (
                request.text
                == "Projection drift root cause identified in deployment workflow"
            ):
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v1",
                    vector=(0.8,) + (0.0,) * 1535,
                    content_hash="lexical-memory-hash",
                )

            if request.text == "Background note with no lexical overlap":
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v1",
                    vector=(1.0,) + (0.0,) * 1535,
                    content_hash="semantic-only-memory-hash",
                )

            raise AssertionError(f"unexpected embedding request: {request.text}")

    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        embedding_generator=FixedHybridEmbeddingGenerator(),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-search-hybrid.git",
            canonical_path="/tmp/integration-repo-memory-search-hybrid",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMSEARCH-HYBRID-001",
        )
    )

    lexical_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Projection drift root cause identified in deployment workflow",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "root-cause"},
        )
    )
    semantic_only_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Background note with no lexical overlap",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "background"},
        )
    )

    assert lexical_episode.episode is not None
    assert semantic_only_episode.episode is not None

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )
        memory_items_by_content = {item.content: item for item in workspace_items}

        assert (
            "Projection drift root cause identified in deployment workflow"
            in memory_items_by_content
        )
        assert "Background note with no lexical overlap" in memory_items_by_content

        uow.commit()

    search = memory_service.search(
        SearchMemoryRequest(
            query="projection drift root cause",
            workspace_id=str(workspace.workspace_id),
            limit=5,
            filters={},
        )
    )

    assert search.feature == MemoryFeature.SEARCH
    assert search.implemented is True
    assert search.details["search_mode"] == "hybrid_memory_item_search"
    assert search.details["semantic_candidates_considered"] == 2
    assert search.details["semantic_query_generated"] is True
    assert search.details["result_mode_counts"] == {
        "hybrid": 0,
        "lexical_only": 1,
        "semantic_only_discounted": 1,
    }
    assert search.details["result_composition"] == {
        "with_lexical_signal": 1,
        "with_semantic_signal": 1,
        "with_both_signals": 0,
    }
    assert search.details["results_returned"] == 2
    assert [result.summary for result in search.results] == [
        "Projection drift root cause identified in deployment workflow",
        "Background note with no lexical overlap",
    ]

    lexical_result = search.results[0]
    semantic_only_result = search.results[1]

    assert lexical_result.lexical_score > 0.0
    assert lexical_result.semantic_score == 0.0
    assert lexical_result.ranking_details == {
        "lexical_component": lexical_result.lexical_score,
        "semantic_component": 0.0,
        "score_mode": "lexical_only",
        "semantic_only_discount_applied": False,
    }

    assert semantic_only_result.lexical_score == 0.0
    assert semantic_only_result.semantic_score == 1.0
    assert semantic_only_result.ranking_details == {
        "lexical_component": 0.0,
        "semantic_component": semantic_only_result.semantic_score,
        "score_mode": "semantic_only_discounted",
        "semantic_only_discount_applied": True,
    }
    assert lexical_result.score > semantic_only_result.score


def test_postgres_memory_search_result_mode_counts_cover_hybrid_lexical_and_semantic_only(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    uow_factory = build_postgres_uow_factory(config)
    workflow_service = WorkflowService(uow_factory)

    class FixedThreeModeEmbeddingGenerator(EmbeddingGenerator):
        def generate(self, request: EmbeddingRequest) -> EmbeddingResult:
            if request.text == "projection drift root cause":
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v2",
                    vector=(1.0,) + (0.0,) * 1535,
                    content_hash="query-hash",
                )

            if request.text == "Projection drift root cause with semantic support":
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v2",
                    vector=(0.95,) + (0.0,) * 1535,
                    content_hash="hybrid-memory-hash",
                )

            if (
                request.text
                == "Projection drift root cause documented without semantic alignment"
            ):
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v2",
                    vector=(0.0, 1.0) + (0.0,) * 1534,
                    content_hash="lexical-only-memory-hash",
                )

            if request.text == "Background note with unrelated wording":
                return EmbeddingResult(
                    provider="test",
                    model="test-hybrid-v2",
                    vector=(0.5,) + (0.0,) * 1535,
                    content_hash="semantic-only-memory-hash",
                )

            raise AssertionError(f"unexpected embedding request: {request.text}")

    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        embedding_generator=FixedThreeModeEmbeddingGenerator(),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-search-three-modes.git",
            canonical_path="/tmp/integration-repo-memory-search-three-modes",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMSEARCH-HYBRID-THREE-MODES-001",
        )
    )

    hybrid_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Projection drift root cause with semantic support",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "hybrid"},
        )
    )
    lexical_only_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Projection drift root cause documented without semantic alignment",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "lexical-only"},
        )
    )
    semantic_only_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Background note with unrelated wording",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "semantic-only"},
        )
    )

    assert hybrid_episode.episode is not None
    assert lexical_only_episode.episode is not None
    assert semantic_only_episode.episode is not None

    search = memory_service.search(
        SearchMemoryRequest(
            query="projection drift root cause",
            workspace_id=str(workspace.workspace_id),
            limit=5,
            filters={},
        )
    )

    assert search.feature == MemoryFeature.SEARCH
    assert search.implemented is True
    assert search.details["search_mode"] == "hybrid_memory_item_search"
    assert search.details["semantic_candidates_considered"] == 3
    assert search.details["semantic_query_generated"] is True
    assert search.details["result_mode_counts"] == {
        "hybrid": 1,
        "lexical_only": 1,
        "semantic_only_discounted": 1,
    }
    assert search.details["result_composition"] == {
        "with_lexical_signal": 2,
        "with_semantic_signal": 2,
        "with_both_signals": 1,
    }
    assert search.details["results_returned"] == 3
    assert [result.summary for result in search.results] == [
        "Projection drift root cause with semantic support",
        "Projection drift root cause documented without semantic alignment",
        "Background note with unrelated wording",
    ]

    hybrid_result = search.results[0]
    lexical_only_result = search.results[1]
    semantic_only_result = search.results[2]

    assert hybrid_result.lexical_score > 0.0
    assert hybrid_result.semantic_score > 0.0
    assert hybrid_result.ranking_details == {
        "lexical_component": hybrid_result.lexical_score,
        "semantic_component": hybrid_result.semantic_score,
        "score_mode": "hybrid",
        "semantic_only_discount_applied": False,
    }

    assert lexical_only_result.lexical_score > 0.0
    assert lexical_only_result.semantic_score == 0.0
    assert lexical_only_result.ranking_details == {
        "lexical_component": lexical_only_result.lexical_score,
        "semantic_component": 0.0,
        "score_mode": "lexical_only",
        "semantic_only_discount_applied": False,
    }

    assert semantic_only_result.lexical_score == 0.0
    assert semantic_only_result.semantic_score > 0.0
    assert semantic_only_result.ranking_details == {
        "lexical_component": 0.0,
        "semantic_component": semantic_only_result.semantic_score,
        "score_mode": "semantic_only_discounted",
        "semantic_only_discount_applied": True,
    }

    assert hybrid_result.score > lexical_only_result.score
    assert lexical_only_result.score > semantic_only_result.score


def test_postgres_memory_embedding_repository_find_similar_returns_nearest_matches(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    uow_factory = build_postgres_uow_factory(config)
    workflow_service = WorkflowService(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-embedding-similarity.git",
            canonical_path="/tmp/integration-repo-memory-embedding-similarity",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMEMBED-SIMILARITY-001",
        )
    )

    episode = (
        MemoryService(
            episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
            workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        )
        .remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id=str(
                    started.workflow_instance.workflow_instance_id
                ),
                summary="Episode backing similarity query test",
                attempt_id=str(started.attempt.attempt_id),
                metadata={"kind": "integration"},
            )
        )
        .episode
    )
    assert episode is not None

    nearest_memory_id = uuid4()
    middle_memory_id = uuid4()
    farthest_memory_id = uuid4()

    nearest_item = MemoryItemRecord(
        memory_id=nearest_memory_id,
        workspace_id=workspace.workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Nearest semantic memory item",
        metadata={"kind": "similarity", "rank": "nearest"},
        created_at=datetime(2024, 2, 10, tzinfo=UTC),
        updated_at=datetime(2024, 2, 10, tzinfo=UTC),
    )
    middle_item = MemoryItemRecord(
        memory_id=middle_memory_id,
        workspace_id=workspace.workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Middle semantic memory item",
        metadata={"kind": "similarity", "rank": "middle"},
        created_at=datetime(2024, 2, 11, tzinfo=UTC),
        updated_at=datetime(2024, 2, 11, tzinfo=UTC),
    )
    farthest_item = MemoryItemRecord(
        memory_id=farthest_memory_id,
        workspace_id=workspace.workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Farthest semantic memory item",
        metadata={"kind": "similarity", "rank": "farthest"},
        created_at=datetime(2024, 2, 12, tzinfo=UTC),
        updated_at=datetime(2024, 2, 12, tzinfo=UTC),
    )

    nearest_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=nearest_memory_id,
        embedding_model="test-embedding-model",
        embedding=(0.0,) * 1535 + (0.0,),
        content_hash=compute_content_hash(
            nearest_item.content,
            nearest_item.metadata,
        ),
        created_at=datetime(2024, 2, 13, tzinfo=UTC),
    )
    middle_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=middle_memory_id,
        embedding_model="test-embedding-model",
        embedding=(0.0,) * 1534 + (0.25, 0.0),
        content_hash=compute_content_hash(
            middle_item.content,
            middle_item.metadata,
        ),
        created_at=datetime(2024, 2, 14, tzinfo=UTC),
    )
    farthest_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=farthest_memory_id,
        embedding_model="test-embedding-model",
        embedding=(0.0,) * 1534 + (1.0, 1.0),
        content_hash=compute_content_hash(
            farthest_item.content,
            farthest_item.metadata,
        ),
        created_at=datetime(2024, 2, 15, tzinfo=UTC),
    )

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        uow.memory_items.create(nearest_item)
        uow.memory_items.create(middle_item)
        uow.memory_items.create(farthest_item)
        uow.memory_embeddings.create(nearest_embedding)
        uow.memory_embeddings.create(middle_embedding)
        uow.memory_embeddings.create(farthest_embedding)
        uow.commit()

    query_embedding = (0.0,) * 1536

    with uow_factory() as uow:
        assert uow.memory_embeddings is not None

        scoped_matches = uow.memory_embeddings.find_similar(
            query_embedding,
            limit=3,
            workspace_id=workspace.workspace_id,
        )
        unscoped_matches = uow.memory_embeddings.find_similar(
            query_embedding,
            limit=2,
        )

    assert [embedding.memory_id for embedding in scoped_matches] == [
        nearest_memory_id,
        middle_memory_id,
        farthest_memory_id,
    ]
    assert [embedding.memory_id for embedding in unscoped_matches] == [
        nearest_memory_id,
        middle_memory_id,
    ]
    assert all(
        embedding.embedding_model == "test-embedding-model"
        for embedding in scoped_matches
    )


def test_postgres_memory_get_context_returns_multiple_workflow_episodes(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    workflow_service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
                schema_name=clean_postgres_database,
            )
        )
    )
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(
            build_postgres_uow_factory(
                PostgresConfig(
                    database_url=postgres_database_url,
                    connect_timeout_seconds=5,
                    statement_timeout_ms=5000,
                    schema_name=clean_postgres_database,
                )
            )
        ),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(
            build_postgres_uow_factory(
                PostgresConfig(
                    database_url=postgres_database_url,
                    connect_timeout_seconds=5,
                    statement_timeout_ms=5000,
                    schema_name=clean_postgres_database,
                )
            )
        ),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context.git",
            canonical_path="/tmp/integration-repo-memory-context",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-001",
        )
    )

    first_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Investigated root cause",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "investigation"},
        )
    )
    second_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Applied durable fix",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "implementation"},
        )
    )

    context = memory_service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert first_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert second_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert context.feature == MemoryFeature.GET_CONTEXT
    assert context.implemented is True
    assert len(context.episodes) == 2
    assert [episode.summary for episode in context.episodes] == [
        "Applied durable fix",
        "Investigated root cause",
    ]
    assert context.details["query"] is None
    assert context.details["normalized_query"] is None
    assert context.details["lookup_scope"] == "workflow_instance"
    assert context.details["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert context.details["resolved_workflow_ids"] == [
        str(started.workflow_instance.workflow_instance_id)
    ]
    assert context.details["resolved_workflow_count"] == 1
    assert context.details["query_filter_applied"] is False
    assert context.details["episodes_before_query_filter"] == 2
    assert context.details["matched_episode_count"] == 2
    assert context.details["episodes_returned"] == 2


def test_postgres_memory_get_context_returns_workspace_episodes(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    workflow_service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
                schema_name=clean_postgres_database,
            )
        )
    )
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(
            build_postgres_uow_factory(
                PostgresConfig(
                    database_url=postgres_database_url,
                    connect_timeout_seconds=5,
                    statement_timeout_ms=5000,
                    schema_name=clean_postgres_database,
                )
            )
        ),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(
            build_postgres_uow_factory(
                PostgresConfig(
                    database_url=postgres_database_url,
                    connect_timeout_seconds=5,
                    statement_timeout_ms=5000,
                    schema_name=clean_postgres_database,
                )
            )
        ),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context-workspace.git",
            canonical_path="/tmp/integration-repo-memory-context-workspace",
            default_branch="main",
        )
    )
    first_started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-WS-001",
        )
    )
    workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=first_started.workflow_instance.workflow_instance_id,
            attempt_id=first_started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )
    second_started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-WS-002",
        )
    )

    older_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(
                first_started.workflow_instance.workflow_instance_id
            ),
            summary="Workspace episode from older workflow",
            attempt_id=str(first_started.attempt.attempt_id),
            metadata={"kind": "investigation"},
        )
    )
    newer_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(
                second_started.workflow_instance.workflow_instance_id
            ),
            summary="Workspace episode from newer workflow",
            attempt_id=str(second_started.attempt.attempt_id),
            metadata={"kind": "implementation"},
        )
    )

    context = memory_service.get_context(
        GetMemoryContextRequest(
            workspace_id=str(workspace.workspace_id),
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert older_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert newer_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert context.feature == MemoryFeature.GET_CONTEXT
    assert context.implemented is True
    assert [episode.summary for episode in context.episodes] == [
        "Workspace episode from newer workflow",
        "Workspace episode from older workflow",
    ]
    assert context.details["query"] is None
    assert context.details["normalized_query"] is None
    assert context.details["lookup_scope"] == "workspace"
    assert context.details["workspace_id"] == str(workspace.workspace_id)
    assert context.details["workflow_instance_id"] is None
    assert context.details["ticket_id"] is None
    assert sorted(context.details["resolved_workflow_ids"]) == sorted(
        [
            str(first_started.workflow_instance.workflow_instance_id),
            str(second_started.workflow_instance.workflow_instance_id),
        ]
    )
    assert context.details["resolved_workflow_count"] == 2
    assert context.details["query_filter_applied"] is False
    assert context.details["episodes_before_query_filter"] == 2
    assert context.details["matched_episode_count"] == 2
    assert context.details["episodes_returned"] == 2


def test_postgres_memory_get_context_returns_ticket_episodes(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    workflow_service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
                schema_name=clean_postgres_database,
            )
        )
    )
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(
            build_postgres_uow_factory(
                PostgresConfig(
                    database_url=postgres_database_url,
                    connect_timeout_seconds=5,
                    statement_timeout_ms=5000,
                    schema_name=clean_postgres_database,
                )
            )
        ),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(
            build_postgres_uow_factory(
                PostgresConfig(
                    database_url=postgres_database_url,
                    connect_timeout_seconds=5,
                    statement_timeout_ms=5000,
                    schema_name=clean_postgres_database,
                )
            )
        ),
    )

    first_workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context-ticket-a.git",
            canonical_path="/tmp/integration-repo-memory-context-ticket-a",
            default_branch="main",
        )
    )
    second_workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context-ticket-b.git",
            canonical_path="/tmp/integration-repo-memory-context-ticket-b",
            default_branch="main",
        )
    )

    first_started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=first_workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-TICKET-001",
        )
    )
    second_started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=second_workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-TICKET-001",
        )
    )

    older_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(
                first_started.workflow_instance.workflow_instance_id
            ),
            summary="Ticket episode from first workspace",
            attempt_id=str(first_started.attempt.attempt_id),
            metadata={"kind": "investigation"},
        )
    )
    newer_episode = memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(
                second_started.workflow_instance.workflow_instance_id
            ),
            summary="Ticket episode from second workspace",
            attempt_id=str(second_started.attempt.attempt_id),
            metadata={"kind": "implementation"},
        )
    )

    context = memory_service.get_context(
        GetMemoryContextRequest(
            ticket_id="INTEG-MEMCTX-TICKET-001",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert older_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert newer_episode.feature == MemoryFeature.REMEMBER_EPISODE
    assert context.feature == MemoryFeature.GET_CONTEXT
    assert context.implemented is True
    assert [episode.summary for episode in context.episodes] == [
        "Ticket episode from second workspace",
        "Ticket episode from first workspace",
    ]
    assert context.details["query"] is None
    assert context.details["normalized_query"] is None
    assert context.details["lookup_scope"] == "ticket"
    assert context.details["workspace_id"] is None
    assert context.details["workflow_instance_id"] is None
    assert context.details["ticket_id"] == "INTEG-MEMCTX-TICKET-001"
    assert sorted(context.details["resolved_workflow_ids"]) == sorted(
        [
            str(first_started.workflow_instance.workflow_instance_id),
            str(second_started.workflow_instance.workflow_instance_id),
        ]
    )
    assert context.details["resolved_workflow_count"] == 2
    assert context.details["query_filter_applied"] is False
    assert context.details["episodes_before_query_filter"] == 2
    assert context.details["matched_episode_count"] == 2
    assert context.details["episodes_returned"] == 2


def test_postgres_memory_get_context_applies_initial_query_filtering(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    workflow_service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
                schema_name=clean_postgres_database,
            )
        )
    )
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(
            build_postgres_uow_factory(
                PostgresConfig(
                    database_url=postgres_database_url,
                    connect_timeout_seconds=5,
                    statement_timeout_ms=5000,
                    schema_name=clean_postgres_database,
                )
            )
        ),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(
            build_postgres_uow_factory(
                PostgresConfig(
                    database_url=postgres_database_url,
                    connect_timeout_seconds=5,
                    statement_timeout_ms=5000,
                    schema_name=clean_postgres_database,
                )
            )
        ),
    )

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-context-query.git",
            canonical_path="/tmp/integration-repo-memory-context-query",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMCTX-QUERY-001",
        )
    )

    memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Fix flaky postgres startup ordering",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "stabilization", "component": "postgres"},
        )
    )
    memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Document release checklist",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "docs", "component": "release"},
        )
    )
    memory_service.remember_episode(
        RememberEpisodeRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            summary="Track filtering semantics decision",
            attempt_id=str(started.attempt.attempt_id),
            metadata={"kind": "analysis", "component": "metadata-filter"},
        )
    )

    context = memory_service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            query="postgres",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert context.feature == MemoryFeature.GET_CONTEXT
    assert context.implemented is True
    assert [episode.summary for episode in context.episodes] == [
        "Fix flaky postgres startup ordering",
    ]
    assert context.details["query"] == "postgres"
    assert context.details["normalized_query"] == "postgres"
    assert context.details["lookup_scope"] == "workflow_instance"
    assert context.details["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert context.details["resolved_workflow_ids"] == [
        str(started.workflow_instance.workflow_instance_id)
    ]
    assert context.details["resolved_workflow_count"] == 1
    assert context.details["query_filter_applied"] is True
    assert context.details["episodes_before_query_filter"] == 3
    assert context.details["matched_episode_count"] == 1
    assert context.details["episodes_returned"] == 1

    metadata_context = memory_service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(started.workflow_instance.workflow_instance_id),
            query="metadata-filter",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert metadata_context.feature == MemoryFeature.GET_CONTEXT
    assert metadata_context.implemented is True
    assert [episode.summary for episode in metadata_context.episodes] == [
        "Track filtering semantics decision",
    ]
    assert metadata_context.details["query"] == "metadata-filter"
    assert metadata_context.details["normalized_query"] == "metadata-filter"
    assert metadata_context.details["lookup_scope"] == "workflow_instance"
    assert metadata_context.details["workflow_instance_id"] == str(
        started.workflow_instance.workflow_instance_id
    )
    assert metadata_context.details["resolved_workflow_ids"] == [
        str(started.workflow_instance.workflow_instance_id)
    ]
    assert metadata_context.details["resolved_workflow_count"] == 1
    assert metadata_context.details["query_filter_applied"] is True
    assert metadata_context.details["episodes_before_query_filter"] == 3
    assert metadata_context.details["matched_episode_count"] == 1
    assert metadata_context.details["episodes_returned"] == 1


def test_postgres_memory_item_and_embedding_repositories_round_trip(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    uow_factory = build_postgres_uow_factory(config)
    workflow_service = WorkflowService(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-items.git",
            canonical_path="/tmp/integration-repo-memory-items",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMITEM-001",
        )
    )

    episode = (
        MemoryService(
            episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
            workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        )
        .remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id=str(
                    started.workflow_instance.workflow_instance_id
                ),
                summary="Episode backing semantic memory items",
                attempt_id=str(started.attempt.attempt_id),
                metadata={"kind": "integration"},
            )
        )
        .episode
    )
    assert episode is not None

    memory_id = uuid4()
    episode_id = episode.episode_id
    older_memory_item = MemoryItemRecord(
        memory_id=memory_id,
        workspace_id=workspace.workspace_id,
        episode_id=episode_id,
        type="episode_note",
        provenance="episode",
        content="Older semantic memory item",
        metadata={"kind": "investigation"},
        created_at=datetime(2024, 2, 1, tzinfo=UTC),
        updated_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    newer_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace.workspace_id,
        episode_id=episode_id,
        type="episode_note",
        provenance="episode",
        content="Newer semantic memory item",
        metadata={"kind": "implementation"},
        created_at=datetime(2024, 2, 2, tzinfo=UTC),
        updated_at=datetime(2024, 2, 2, tzinfo=UTC),
    )

    older_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_id,
        embedding_model="test-embedding-model",
        embedding=(0.1,) * 1536,
        content_hash="older-content-hash",
        created_at=datetime(2024, 2, 3, tzinfo=UTC),
    )
    newer_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_id,
        embedding_model="test-embedding-model-v2",
        embedding=(0.4,) * 1536,
        content_hash="newer-content-hash",
        created_at=datetime(2024, 2, 4, tzinfo=UTC),
    )

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        created_older_item = uow.memory_items.create(older_memory_item)
        created_newer_item = uow.memory_items.create(newer_memory_item)
        created_older_embedding = uow.memory_embeddings.create(older_embedding)
        created_newer_embedding = uow.memory_embeddings.create(newer_embedding)
        uow.commit()

    assert created_older_item == older_memory_item
    assert created_newer_item == newer_memory_item
    assert created_older_embedding == older_embedding
    assert created_newer_embedding == newer_embedding

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )
        episode_items = uow.memory_items.list_by_episode_id(
            episode_id,
            limit=10,
        )
        memory_embeddings = uow.memory_embeddings.list_by_memory_id(
            memory_id,
            limit=10,
        )

    assert [item.content for item in workspace_items] == [
        "Newer semantic memory item",
        "Older semantic memory item",
    ]
    assert [item.content for item in episode_items] == [
        "Newer semantic memory item",
        "Older semantic memory item",
    ]
    assert [embedding.embedding_model for embedding in memory_embeddings] == [
        "test-embedding-model-v2",
        "test-embedding-model",
    ]
    assert memory_embeddings[0].embedding == (0.4,) * 1536
    assert memory_embeddings[1].embedding == (0.1,) * 1536
    assert started.workflow_instance.workflow_instance_id is not None


def test_postgres_terminal_resume_is_for_inspection_not_continuation(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-terminal.git",
            canonical_path="/tmp/integration-repo-terminal",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-TERMINAL-001",
        )
    )
    checkpoint_result = service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="finalize",
            checkpoint_json={"next_intended_action": "No further execution"},
        )
    )
    service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
        )
    )

    terminal_resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert terminal_resume.resumable_status == ResumableStatus.TERMINAL
    assert terminal_resume.attempt is not None
    assert terminal_resume.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert terminal_resume.latest_checkpoint is not None
    assert (
        terminal_resume.latest_checkpoint.checkpoint_id
        == checkpoint_result.checkpoint.checkpoint_id
    )
    assert (
        terminal_resume.next_hint
        == "Workflow is terminal. Inspect the final state instead of resuming execution."
    )


def test_postgres_workflow_service_resume_without_projection_state_is_still_resumable(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-2.git",
            canonical_path="/tmp/integration-repo-2",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-456",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Resume implementation"},
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.resumable_status == ResumableStatus.RESUMABLE
    assert resume.projections == ()
    assert all(warning.code != "stale_projection" for warning in resume.warnings)


def test_postgres_workflow_service_records_projection_failures(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection.git",
            canonical_path="/tmp/integration-repo-projection",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Retry projection write"},
        )
    )

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )

    first_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="disk full",
            error_code="io_error",
        )
    )
    second_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            target_path=".agent/resume.md",
            error_message="permission denied",
            error_code="permission_error",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert first_failure.attempt_id == started.attempt.attempt_id
    assert first_failure.open_failure_count == 1
    assert second_failure.attempt_id == started.attempt.attempt_id
    assert second_failure.open_failure_count == 1
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FAILED
    assert resume.projections[0].open_failure_count == 1
    assert any(warning.code == "open_projection_failure" for warning in resume.warnings)

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1

    open_failure_warning = open_failure_warnings[0]
    assert open_failure_warning.details["projection_type"] == "resume_json"
    assert open_failure_warning.details["open_failure_count"] == 1
    assert open_failure_warning.details["target_path"] == ".agent/resume.json"
    assert len(open_failure_warning.details["failures"]) == 1
    assert (
        open_failure_warning.details["failures"][0]["projection_type"] == "resume_json"
    )
    assert open_failure_warning.details["failures"][0]["error_code"] == "io_error"
    assert open_failure_warning.details["failures"][0]["occurred_at"] is not None
    assert open_failure_warning.details["failures"][0]["resolved_at"] is None


def test_postgres_workflow_service_resolves_projection_failures_after_successful_projection_write(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-resolve.git",
            canonical_path="/tmp/integration-repo-projection-resolve",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-RESOLVE-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Rewrite projection successfully"},
        )
    )

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="disk full",
            error_code="io_error",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            target_path=".agent/resume.md",
            error_message="permission denied",
            error_code="permission_error",
        )
    )

    resolved_count = service.resolve_resume_projection_failures(
        workspace_id=workspace.workspace_id,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
    )
    recorded = service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FRESH,
            target_path=".agent/resume.json",
        )
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resolved_count == 2
    assert recorded.status == ProjectionStatus.FRESH
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].open_failure_count == 0
    assert all(warning.code != "open_projection_failure" for warning in resume.warnings)


def test_postgres_workflow_service_reconcile_resolves_only_successful_projection_failures(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-partial.git",
            canonical_path="/tmp/integration-repo-projection-partial",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-PARTIAL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Rewrite only JSON projection successfully"
            },
        )
    )

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )
    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.md",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="json disk full",
            error_code="io_error",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_MD,
            target_path=".agent/resume.md",
            error_message="markdown permission denied",
            error_code="permission_error",
        )
    )

    reconciled = service.reconcile_resume_projection(
        success_updates=(
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
            ),
        ),
        failure_updates=(),
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(reconciled) == 1
    assert reconciled[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert reconciled[0].status == ProjectionStatus.FRESH

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }
    assert set(projections_by_type) == {
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
    }

    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FRESH
    )
    assert (
        projections_by_type[ProjectionArtifactType.RESUME_JSON].open_failure_count == 0
    )

    assert projections_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FAILED
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].open_failure_count == 1

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_md"
    assert open_failure_warnings[0].details["open_failure_count"] == 1
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.md"


def test_postgres_workflow_service_reconcile_records_partial_json_failure_and_markdown_success(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-writer-json-fail.git",
            canonical_path="/tmp/integration-repo-projection-writer-json-fail",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-WRITER-JSON-FAIL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Persist markdown while json remains failed"
            },
        )
    )

    reconciled = service.reconcile_resume_projection(
        success_updates=(
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FAILED,
                target_path=".agent/resume.json",
            ),
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_MD,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.md",
            ),
        ),
        failure_updates=(
            RecordProjectionFailureInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                target_path=".agent/resume.json",
                error_message="json write failed",
                error_code="io_error",
            ),
        ),
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(reconciled) == 2

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }
    assert set(projections_by_type) == {
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
    }

    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FAILED
    )
    assert (
        projections_by_type[ProjectionArtifactType.RESUME_JSON].open_failure_count == 1
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].target_path == (
        ".agent/resume.json"
    )

    assert projections_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FRESH
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].open_failure_count == 0
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].target_path == (
        ".agent/resume.md"
    )

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_json"
    assert open_failure_warnings[0].details["open_failure_count"] == 1
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.json"
    assert len(open_failure_warnings[0].details["failures"]) == 1
    assert (
        open_failure_warnings[0].details["failures"][0]["projection_type"]
        == "resume_json"
    )
    assert open_failure_warnings[0].details["failures"][0]["target_path"] == (
        ".agent/resume.json"
    )
    assert open_failure_warnings[0].details["failures"][0]["error_code"] == "io_error"
    assert open_failure_warnings[0].details["failures"][0]["error_message"] == (
        "json write failed"
    )
    assert open_failure_warnings[0].details["failures"][0]["open_failure_count"] == 1


def test_postgres_workflow_service_reconcile_records_partial_markdown_failure_and_json_success(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-writer-md-fail.git",
            canonical_path="/tmp/integration-repo-projection-writer-md-fail",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-WRITER-MD-FAIL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Persist json while markdown remains failed"
            },
        )
    )

    reconciled = service.reconcile_resume_projection(
        success_updates=(
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
            ),
            RecordProjectionStateInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                projection_type=ProjectionArtifactType.RESUME_MD,
                status=ProjectionStatus.FAILED,
                target_path=".agent/resume.md",
            ),
        ),
        failure_updates=(
            RecordProjectionFailureInput(
                workspace_id=workspace.workspace_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                projection_type=ProjectionArtifactType.RESUME_MD,
                target_path=".agent/resume.md",
                error_message="markdown write failed",
                error_code="permission_error",
            ),
        ),
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert len(reconciled) == 2

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }
    assert set(projections_by_type) == {
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
    }

    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FRESH
    )
    assert (
        projections_by_type[ProjectionArtifactType.RESUME_JSON].open_failure_count == 0
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].target_path == (
        ".agent/resume.json"
    )

    assert projections_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FAILED
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].open_failure_count == 1
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].target_path == (
        ".agent/resume.md"
    )

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_md"
    assert open_failure_warnings[0].details["open_failure_count"] == 1
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.md"
    assert len(open_failure_warnings[0].details["failures"]) == 1
    assert (
        open_failure_warnings[0].details["failures"][0]["projection_type"]
        == "resume_md"
    )
    assert open_failure_warnings[0].details["failures"][0]["target_path"] == (
        ".agent/resume.md"
    )
    assert (
        open_failure_warnings[0].details["failures"][0]["error_code"]
        == "permission_error"
    )
    assert open_failure_warnings[0].details["failures"][0]["error_message"] == (
        "markdown write failed"
    )
    assert open_failure_warnings[0].details["failures"][0]["open_failure_count"] == 1


def test_postgres_workflow_service_reports_multiple_failures_for_same_projection(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-multi-failure.git",
            canonical_path="/tmp/integration-repo-projection-multi-failure",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-MULTI-FAIL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Inspect repeated JSON projection failures"
            },
        )
    )

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )
    first_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="first json failure",
            error_code="io_error",
        )
    )
    second_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="second json failure",
            error_code="permission_error",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert first_failure.open_failure_count == 1
    assert second_failure.open_failure_count == 2

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FAILED
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].open_failure_count == 2

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_json"
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.json"
    assert open_failure_warnings[0].details["open_failure_count"] == 2
    assert len(open_failure_warnings[0].details["failures"]) == 2
    assert (
        open_failure_warnings[0].details["failures"][0]["projection_type"]
        == "resume_json"
    )
    assert open_failure_warnings[0].details["failures"][0]["target_path"] == (
        ".agent/resume.json"
    )
    assert open_failure_warnings[0].details["failures"][0]["error_code"] == "io_error"
    assert open_failure_warnings[0].details["failures"][0]["error_message"] == (
        "first json failure"
    )
    assert open_failure_warnings[0].details["failures"][0]["open_failure_count"] == 1
    assert (
        open_failure_warnings[0].details["failures"][1]["projection_type"]
        == "resume_json"
    )
    assert open_failure_warnings[0].details["failures"][1]["target_path"] == (
        ".agent/resume.json"
    )
    assert (
        open_failure_warnings[0].details["failures"][1]["error_code"]
        == "permission_error"
    )
    assert open_failure_warnings[0].details["failures"][1]["error_message"] == (
        "second json failure"
    )
    assert open_failure_warnings[0].details["failures"][1]["open_failure_count"] == 2


def test_postgres_workflow_service_resolve_clears_repeated_failures_for_same_projection(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-multi-failure-resolve.git",
            canonical_path="/tmp/integration-repo-projection-multi-failure-resolve",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-MULTI-RESOLVE-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Resolve repeated JSON projection failures"
            },
        )
    )

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )
    first_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="first json failure",
            error_code="io_error",
        )
    )
    second_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="second json failure",
            error_code="permission_error",
        )
    )

    resolved_count = service.resolve_resume_projection_failures(
        workspace_id=workspace.workspace_id,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
    )
    recorded = service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FRESH,
            target_path=".agent/resume.json",
        )
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert first_failure.open_failure_count == 1
    assert second_failure.open_failure_count == 2
    assert resolved_count == 2
    assert recorded.status == ProjectionStatus.FRESH

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].open_failure_count == 0
    assert all(warning.code != "open_projection_failure" for warning in resume.warnings)


def test_postgres_workflow_service_repeated_failures_increment_retry_count(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-retry-count.git",
            canonical_path="/tmp/integration-repo-projection-retry-count",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-RETRY-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Inspect retry_count for repeated JSON projection failures"
            },
        )
    )

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )
    first_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="first json failure",
            error_code="io_error",
        )
    )
    second_failure = service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="second json failure",
            error_code="permission_error",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert first_failure.attempt_id == started.attempt.attempt_id
    assert first_failure.open_failure_count == 1
    assert first_failure.retry_count == 0
    assert first_failure.status == "open"
    assert first_failure.occurred_at is not None
    assert first_failure.resolved_at is None
    assert second_failure.attempt_id == started.attempt.attempt_id
    assert second_failure.open_failure_count == 2
    assert second_failure.retry_count == 1
    assert second_failure.status == "open"
    assert second_failure.occurred_at is not None
    assert second_failure.resolved_at is None

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_json"
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.json"
    assert open_failure_warnings[0].details["open_failure_count"] == 2
    assert len(open_failure_warnings[0].details["failures"]) == 2
    assert open_failure_warnings[0].details["failures"][0]["retry_count"] == 0
    assert open_failure_warnings[0].details["failures"][0]["status"] == "open"
    assert open_failure_warnings[0].details["failures"][0]["occurred_at"] is not None
    assert open_failure_warnings[0].details["failures"][0]["resolved_at"] is None
    assert open_failure_warnings[0].details["failures"][1]["retry_count"] == 1
    assert open_failure_warnings[0].details["failures"][1]["status"] == "open"
    assert open_failure_warnings[0].details["failures"][1]["occurred_at"] is not None
    assert open_failure_warnings[0].details["failures"][1]["resolved_at"] is None


def test_postgres_workflow_service_ignore_clears_open_projection_failure_warning(
    postgres_workflow_service: WorkflowService,
) -> None:
    service = postgres_workflow_service

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-projection-ignore.git",
            canonical_path="/tmp/integration-repo-projection-ignore",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-IGNORE-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={
                "next_intended_action": "Ignore repeated JSON projection failures"
            },
        )
    )

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FAILED,
            target_path=".agent/resume.json",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="first json failure",
            error_code="io_error",
        )
    )
    service.record_resume_projection_failure(
        RecordProjectionFailureInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            target_path=".agent/resume.json",
            error_message="second json failure",
            error_code="permission_error",
        )
    )

    ignored_count = service.ignore_resume_projection_failures(
        workspace_id=workspace.workspace_id,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        projection_type=ProjectionArtifactType.RESUME_JSON,
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert ignored_count == 2
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FAILED
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].open_failure_count == 0
    assert all(warning.code != "open_projection_failure" for warning in resume.warnings)
    ignored_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "ignored_projection_failure"
    ]
    assert len(ignored_failure_warnings) == 1
    assert ignored_failure_warnings[0].details["projection_type"] == "resume_json"
    assert ignored_failure_warnings[0].details["target_path"] == ".agent/resume.json"
    assert ignored_failure_warnings[0].details["open_failure_count"] == 0
    assert len(ignored_failure_warnings[0].details["failures"]) == 2
    assert ignored_failure_warnings[0].details["failures"][0]["attempt_id"] == str(
        started.attempt.attempt_id
    )
    assert ignored_failure_warnings[0].details["failures"][0]["status"] == "ignored"
    assert ignored_failure_warnings[0].details["failures"][0]["resolved_at"] is not None
    assert ignored_failure_warnings[0].details["failures"][1]["attempt_id"] == str(
        started.attempt.attempt_id
    )
    assert ignored_failure_warnings[0].details["failures"][1]["status"] == "ignored"
    assert ignored_failure_warnings[0].details["failures"][1]["resolved_at"] is not None


def test_postgres_writer_and_reconcile_end_to_end_json_only(
    postgres_database_url: str,
    clean_postgres_database: str,
    tmp_path: Path,
) -> None:
    service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
                schema_name=clean_postgres_database,
            )
        )
    )

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-e2e-json-only.git",
            canonical_path=str(tmp_path),
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-E2E-JSON-ONLY-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Write JSON projection"},
        )
    )

    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=False,
            write_json=True,
        ),
    )

    result = writer.write_and_reconcile_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert result.json_path == (tmp_path / ".agent" / "resume.json").resolve()
    assert result.markdown_path is None
    assert result.failure_updates == ()
    assert (tmp_path / ".agent" / "resume.json").exists()
    assert not (tmp_path / ".agent" / "resume.md").exists()

    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].open_failure_count == 0
    assert all(warning.code != "open_projection_failure" for warning in resume.warnings)


def test_postgres_writer_and_reconcile_end_to_end_markdown_failure(
    postgres_database_url: str,
    clean_postgres_database: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
                schema_name=clean_postgres_database,
            )
        )
    )

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-e2e-md-failure.git",
            canonical_path=str(tmp_path),
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-E2E-MD-FAIL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Write projections"},
        )
    )

    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    real_write_text = Path.write_text

    def flaky_write_text(
        self: Path, data: str, *, encoding: str | None = None, **kwargs: object
    ) -> int:
        if self.name == "resume.md":
            raise OSError("markdown write failed")
        return real_write_text(self, data, encoding=encoding, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write_text)

    result = writer.write_and_reconcile_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert result.json_path == (tmp_path / ".agent" / "resume.json").resolve()
    assert result.markdown_path == (tmp_path / ".agent" / "resume.md").resolve()
    assert (tmp_path / ".agent" / "resume.json").exists()
    assert not (tmp_path / ".agent" / "resume.md").exists()
    assert len(result.failure_updates) == 1
    assert result.failure_updates[0].projection_type == ProjectionArtifactType.RESUME_MD
    assert result.failure_updates[0].target_path == ".agent/resume.md"
    assert result.failure_updates[0].error_message == "markdown write failed"

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }
    assert set(projections_by_type) == {
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
    }
    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FRESH
    )
    assert (
        projections_by_type[ProjectionArtifactType.RESUME_JSON].open_failure_count == 0
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FAILED
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].open_failure_count == 1

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_md"
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.md"
    assert open_failure_warnings[0].details["open_failure_count"] == 1
    assert len(open_failure_warnings[0].details["failures"]) == 1
    assert (
        open_failure_warnings[0].details["failures"][0]["projection_type"]
        == "resume_md"
    )
    assert open_failure_warnings[0].details["failures"][0]["target_path"] == (
        ".agent/resume.md"
    )
    assert open_failure_warnings[0].details["failures"][0]["error_code"] is None
    assert open_failure_warnings[0].details["failures"][0]["error_message"] == (
        "markdown write failed"
    )
    assert open_failure_warnings[0].details["failures"][0]["open_failure_count"] == 1


def test_postgres_writer_and_reconcile_end_to_end_json_failure(
    postgres_database_url: str,
    clean_postgres_database: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
                schema_name=clean_postgres_database,
            )
        )
    )

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-e2e-json-failure.git",
            canonical_path=str(tmp_path),
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJ-E2E-JSON-FAIL-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Write projections"},
        )
    )

    writer = ResumeProjectionWriter(
        workflow_service=service,
        projection_settings=ProjectionSettings(
            enabled=True,
            directory_name=".agent",
            write_markdown=True,
            write_json=True,
        ),
    )

    real_write_text = Path.write_text

    def flaky_write_text(
        self: Path, data: str, *, encoding: str | None = None, **kwargs: object
    ) -> int:
        if self.name == "resume.json":
            raise OSError("json write failed")
        return real_write_text(self, data, encoding=encoding, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write_text)

    result = writer.write_and_reconcile_resume_projection(
        workspace_root=tmp_path,
        workflow_instance_id=started.workflow_instance.workflow_instance_id,
        workspace_id=workspace.workspace_id,
    )
    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert result.json_path == (tmp_path / ".agent" / "resume.json").resolve()
    assert result.markdown_path == (tmp_path / ".agent" / "resume.md").resolve()
    assert not (tmp_path / ".agent" / "resume.json").exists()
    assert (tmp_path / ".agent" / "resume.md").exists()
    assert len(result.failure_updates) == 1
    assert (
        result.failure_updates[0].projection_type == ProjectionArtifactType.RESUME_JSON
    )
    assert result.failure_updates[0].target_path == ".agent/resume.json"
    assert result.failure_updates[0].error_message == "json write failed"

    projections_by_type = {
        projection.projection_type: projection for projection in resume.projections
    }
    assert set(projections_by_type) == {
        ProjectionArtifactType.RESUME_JSON,
        ProjectionArtifactType.RESUME_MD,
    }
    assert projections_by_type[ProjectionArtifactType.RESUME_JSON].status == (
        ProjectionStatus.FAILED
    )
    assert (
        projections_by_type[ProjectionArtifactType.RESUME_JSON].open_failure_count == 1
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].status == (
        ProjectionStatus.FRESH
    )
    assert projections_by_type[ProjectionArtifactType.RESUME_MD].open_failure_count == 0

    open_failure_warnings = [
        warning
        for warning in resume.warnings
        if warning.code == "open_projection_failure"
    ]
    assert len(open_failure_warnings) == 1
    assert open_failure_warnings[0].details["projection_type"] == "resume_json"
    assert open_failure_warnings[0].details["target_path"] == ".agent/resume.json"
    assert open_failure_warnings[0].details["open_failure_count"] == 1
    assert len(open_failure_warnings[0].details["failures"]) == 1
    assert (
        open_failure_warnings[0].details["failures"][0]["projection_type"]
        == "resume_json"
    )
    assert open_failure_warnings[0].details["failures"][0]["target_path"] == (
        ".agent/resume.json"
    )
    assert open_failure_warnings[0].details["failures"][0]["error_code"] is None
    assert open_failure_warnings[0].details["failures"][0]["error_message"] == (
        "json write failed"
    )
    assert open_failure_warnings[0].details["failures"][0]["open_failure_count"] == 1


def test_postgres_settings_can_build_uow_factory_from_loaded_settings(
    postgres_database_url: str,
    clean_postgres_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "CTXLEDGER_DATABASE_URL": postgres_database_url,
        "CTXLEDGER_TRANSPORT": "http",
        "CTXLEDGER_ENABLE_HTTP": "true",
        "CTXLEDGER_HOST": "127.0.0.1",
        "CTXLEDGER_PORT": "8080",
        "CTXLEDGER_HTTP_PATH": "/mcp",
        "CTXLEDGER_PROJECTION_ENABLED": "true",
        "CTXLEDGER_PROJECTION_DIRECTORY": ".agent",
        "CTXLEDGER_PROJECTION_WRITE_JSON": "true",
        "CTXLEDGER_PROJECTION_WRITE_MARKDOWN": "true",
        "CTXLEDGER_LOG_LEVEL": "info",
        "CTXLEDGER_LOG_STRUCTURED": "true",
        "CTXLEDGER_DB_CONNECT_TIMEOUT_SECONDS": "5",
        "CTXLEDGER_DB_STATEMENT_TIMEOUT_MS": "5000",
    }

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    settings = load_settings()
    config = PostgresConfig.from_settings(settings)
    config = PostgresConfig(
        database_url=config.database_url,
        connect_timeout_seconds=config.connect_timeout_seconds,
        statement_timeout_ms=config.statement_timeout_ms,
        schema_name=clean_postgres_database,
    )
    service = WorkflowService(build_postgres_uow_factory(config))

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-3.git",
            canonical_path="/tmp/integration-repo-3",
            default_branch="main",
        )
    )

    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-789",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert config.database_url == postgres_database_url
    assert config.connect_timeout_seconds == 5
    assert config.statement_timeout_ms == 5000
    assert resume.resumable_status == ResumableStatus.BLOCKED


def test_postgres_projection_state_can_be_observed_after_projection_write(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> None:
    service = WorkflowService(
        build_postgres_uow_factory(
            PostgresConfig(
                database_url=postgres_database_url,
                connect_timeout_seconds=5,
                statement_timeout_ms=5000,
                schema_name=clean_postgres_database,
            )
        )
    )

    workspace = service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/projection.git",
            canonical_path="/tmp/integration-projection-repo",
            default_branch="main",
        )
    )
    started = service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-PROJECTION-1",
        )
    )
    service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="checkpointed",
            checkpoint_json={"next_intended_action": "Resume implementation"},
        )
    )

    service.record_resume_projection(
        RecordProjectionStateInput(
            workspace_id=workspace.workspace_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            projection_type=ProjectionArtifactType.RESUME_JSON,
            status=ProjectionStatus.FRESH,
            target_path=".agent/resume.json",
        )
    )

    resume = service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )

    assert resume.resumable_status == ResumableStatus.RESUMABLE
    assert len(resume.projections) == 1
    assert resume.projections[0].projection_type == ProjectionArtifactType.RESUME_JSON
    assert resume.projections[0].status == ProjectionStatus.FRESH
    assert resume.projections[0].target_path == ".agent/resume.json"
    assert resume.projections[0].last_successful_write_at is not None
    assert resume.projections[0].last_canonical_update_at is not None
    assert resume.projections[0].open_failure_count == 0
    assert all(
        warning.code not in {"stale_projection", "missing_projection"}
        for warning in resume.warnings
    )
