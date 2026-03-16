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
    load_settings,
)
from ctxledger.db.postgres import (
    PostgresConfig,
    build_connection_pool,
    build_postgres_uow_factory,
)
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
from ctxledger.workflow.memory_bridge import WorkflowMemoryBridge
from ctxledger.workflow.service import (
    CompleteWorkflowInput,
    CreateCheckpointInput,
    MemoryEmbeddingRecord,
    MemoryItemRecord,
    RegisterWorkspaceInput,
    ResumableStatus,
    ResumeWorkflowInput,
    StartWorkflowInput,
    VerifyReport,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
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
def postgres_pooled_uow_factory(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> Iterator:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    connection_pool = build_connection_pool(config)
    try:
        yield build_postgres_uow_factory(config, connection_pool)
    finally:
        connection_pool.close()


@pytest.fixture
def postgres_workflow_service(
    postgres_pooled_uow_factory,
) -> WorkflowService:
    return WorkflowService(postgres_pooled_uow_factory)


def test_postgres_memory_search_returns_memory_item_based_results(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    embedding_generator = FakeCustomHTTPEmbeddingGenerator()
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
        memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
        embedding_generator=embedding_generator,
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
    postgres_pooled_uow_factory,
    openai_test_api_key: str,
    openai_test_model: str,
    openai_test_base_url: str,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
        embedding_generator=embedding_generator,
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
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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


def test_postgres_workflow_complete_auto_memory_skips_low_signal_closeout(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
            repo_url="https://example.com/org/repo-workflow-complete-auto-low-signal.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-low-signal",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-LOW-SIGNAL-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="minor_note",
            summary="Tiny progress note",
            checkpoint_json={},
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed a low-signal pass",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        assert uow.memory_items is not None

        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]
        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )

    assert completed.workflow_instance.status == WorkflowInstanceStatus.COMPLETED
    assert completed.attempt.status == WorkflowAttemptStatus.SUCCEEDED
    assert completed.auto_memory_details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "low_signal_checkpoint_closeout",
    }
    assert completed.warnings == ()
    assert auto_episodes == []
    assert workspace_items == ()


def test_postgres_workflow_complete_auto_memory_suppresses_duplicate_closeout(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
            repo_url="https://example.com/org/repo-workflow-complete-auto-duplicate.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-duplicate",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-DUPE-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Checkpoint summary for duplicate suppression",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path"
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed heuristic planning pass",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    reopened_attempt = workflow_service.resume_workflow(
        ResumeWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id
        )
    )
    assert reopened_attempt.resumable_status == ResumableStatus.TERMINAL

    duplicate_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=first_completed.attempt,
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Checkpoint summary for duplicate suppression",
                checkpoint_json={
                    "next_intended_action": "Implement the minimum heuristic path"
                },
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.PASSED,
                report_json={"checks": ["pytest"], "status": "passed"},
            ),
            summary="Completed heuristic planning pass",
            failure_reason=None,
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "stored",
        "embedding_generation_skipped_reason": None,
        "embedding_provider": "local_stub",
        "embedding_model": "local-stub-v1",
        "embedding_vector_dimensions": 1536,
        "embedding_content_hash": first_completed.auto_memory_details[
            "embedding_content_hash"
        ],
    }
    assert duplicate_result is not None
    assert duplicate_result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "duplicate_closeout_auto_memory",
    }
    assert len(auto_episodes) == 1


def test_postgres_workflow_complete_auto_memory_suppresses_near_duplicate_closeout(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
            repo_url="https://example.com/org/repo-workflow-complete-auto-near-duplicate.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-near-duplicate",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-NEAR-DUPE-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="First checkpoint summary",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path"
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="First completion summary",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    near_duplicate_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=first_completed.attempt,
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Second checkpoint summary",
                checkpoint_json={
                    "next_intended_action": "Implement the minimum heuristic path"
                },
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.PASSED,
                report_json={"checks": ["pytest"], "status": "passed"},
            ),
            summary="Second completion summary",
            failure_reason=None,
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert near_duplicate_result is not None
    assert near_duplicate_result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "near_duplicate_checkpoint_closeout",
    }
    assert len(auto_episodes) == 1


def test_postgres_workflow_complete_auto_memory_skips_near_duplicate_with_high_summary_similarity(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
            repo_url="https://example.com/org/repo-workflow-complete-auto-summary-similar.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-summary-similar",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-SUMMARY-SIMILAR-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior",
            checkpoint_json={
                "next_intended_action": "Implement summary similarity gating"
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Implemented summary similarity gating for duplicate suppression",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    near_duplicate_result = workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
        workflow=first_completed.workflow_instance,
        attempt=first_completed.attempt,
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior again",
            checkpoint_json={
                "next_intended_action": "Implement summary similarity gating"
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=started.attempt.attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["pytest"], "status": "passed"},
        ),
        summary="Implemented gating for summary similarity in duplicate suppression",
        failure_reason=None,
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert near_duplicate_result is not None
    assert near_duplicate_result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "near_duplicate_checkpoint_closeout",
    }
    assert len(auto_episodes) == 1


def test_postgres_workflow_complete_auto_memory_skips_near_duplicate_when_similarity_is_only_boilerplate_driven(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
            repo_url="https://example.com/org/repo-workflow-complete-auto-summary-boilerplate.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-summary-boilerplate",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-SUMMARY-BOILERPLATE-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior",
            checkpoint_json={
                "next_intended_action": "Implement summary similarity gating"
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Implemented summary similarity gating for duplicate suppression",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    near_duplicate_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=first_completed.attempt,
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Investigated duplicate suppression behavior for another path",
                checkpoint_json={
                    "next_intended_action": "Implement summary similarity gating"
                },
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.PASSED,
                report_json={"checks": ["pytest"], "status": "passed"},
            ),
            summary="Implemented summary similarity gating for duplicate suppression",
            failure_reason=None,
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert near_duplicate_result is not None
    assert near_duplicate_result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "near_duplicate_checkpoint_closeout",
    }
    assert len(auto_episodes) == 1


def test_postgres_workflow_complete_auto_memory_does_not_treat_old_closeout_as_near_duplicate(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
            repo_url="https://example.com/org/repo-workflow-complete-auto-old-near-duplicate.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-old-near-duplicate",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-OLD-NEAR-DUPE-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="First checkpoint summary",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path"
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="First completion summary",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        existing_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in existing_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]
        assert len(auto_episodes) == 1

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        existing_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in existing_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]
        assert len(auto_episodes) == 1

        aged_episode = auto_episodes[0]
        assert hasattr(uow, "_conn")
        with uow._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE episodes
                SET created_at = %s, updated_at = %s
                WHERE episode_id = %s
                """,
                (
                    datetime(2024, 1, 1, tzinfo=UTC),
                    datetime(2024, 1, 1, tzinfo=UTC),
                    str(aged_episode.episode_id),
                ),
            )
        uow.commit()

    later_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=first_completed.attempt,
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Second checkpoint summary",
                checkpoint_json={
                    "next_intended_action": "Implement the minimum heuristic path"
                },
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.PASSED,
                report_json={"checks": ["pytest"], "status": "passed"},
            ),
            summary="Second completion summary",
            failure_reason=None,
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        refreshed_auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert later_result is not None
    assert later_result.details["auto_memory_recorded"] is True
    assert later_result.details["embedding_persistence_status"] == "stored"
    assert later_result.details["embedding_generation_skipped_reason"] is None
    assert later_result.details["embedding_provider"] == "local_stub"
    assert later_result.details["embedding_model"] == "local-stub-v1"
    assert later_result.details["embedding_vector_dimensions"] == 1536
    assert later_result.details["embedding_content_hash"] is not None
    assert len(refreshed_auto_episodes) == 2


def test_postgres_workflow_complete_auto_memory_records_when_summary_similarity_is_below_threshold(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
            repo_url="https://example.com/org/repo-workflow-complete-auto-summary-dissimilar.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-summary-dissimilar",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-SUMMARY-DISSIMILAR-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Investigated duplicate suppression behavior",
            checkpoint_json={
                "next_intended_action": "Implement summary similarity gating"
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Implemented summary similarity gating for duplicate suppression",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    different_result = workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
        workflow=first_completed.workflow_instance,
        attempt=first_completed.attempt,
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Documented operator-facing rollout guidance for the refined suppression logic",
            checkpoint_json={
                "next_intended_action": "Publish operator-facing duplicate suppression notes"
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=started.attempt.attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["pytest"], "status": "passed"},
        ),
        summary="Documented rollout notes for operators after validation",
        failure_reason=None,
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert different_result is not None
    assert different_result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "stored",
        "embedding_generation_skipped_reason": None,
        "embedding_provider": "local_stub",
        "embedding_model": "local-stub-v1",
        "embedding_vector_dimensions": 1536,
        "embedding_content_hash": different_result.details["embedding_content_hash"],
    }
    assert len(auto_episodes) == 2


def test_postgres_workflow_complete_auto_memory_uses_extracted_and_metadata_fields_for_near_duplicate_matching(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
            repo_url="https://example.com/org/repo-workflow-complete-auto-metadata-aware.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-metadata-aware",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-METADATA-AWARE-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Compared extracted closeout fields",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching"
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Refined metadata-aware closeout duplicate detection",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    near_duplicate_result = workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
        workflow=first_completed.workflow_instance,
        attempt=first_completed.attempt,
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Compared extracted closeout fields again",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching"
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=started.attempt.attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["pytest"], "status": "passed"},
        ),
        summary="Refined duplicate detection with metadata-aware closeout matching",
        failure_reason=None,
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert near_duplicate_result is not None
    assert near_duplicate_result.details == {
        "auto_memory_recorded": False,
        "auto_memory_skipped_reason": "near_duplicate_checkpoint_closeout",
    }
    assert len(auto_episodes) == 1


def test_postgres_workflow_complete_auto_memory_does_not_treat_different_attempt_status_as_near_duplicate(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
            repo_url="https://example.com/org/repo-workflow-complete-auto-attempt-status-diff.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-attempt-status-diff",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-ATTEMPT-STATUS-DIFF-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Compared weighted closeout fields",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching"
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="Completed weighted duplicate matching refinement",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    attempt_different_result = workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
        workflow=first_completed.workflow_instance,
        attempt=WorkflowAttempt(
            attempt_id=started.attempt.attempt_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.FAILED,
            verify_status=VerifyStatus.PASSED,
            started_at=started.attempt.started_at,
            finished_at=datetime.now(UTC),
            created_at=started.attempt.created_at,
            updated_at=datetime.now(UTC),
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Compared weighted closeout fields again",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching"
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=started.attempt.attempt_id,
            status=VerifyStatus.PASSED,
            report_json={"checks": ["pytest"], "status": "passed"},
        ),
        summary="Completed weighted closeout duplicate matching refinement",
        failure_reason=None,
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert attempt_different_result is not None
    assert attempt_different_result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "stored",
        "embedding_generation_skipped_reason": None,
        "embedding_provider": "local_stub",
        "embedding_model": "local-stub-v1",
        "embedding_vector_dimensions": 1536,
        "embedding_content_hash": attempt_different_result.details[
            "embedding_content_hash"
        ],
    }
    assert len(auto_episodes) == 2
    assert any(
        episode.metadata.get("attempt_status") == "failed" for episode in auto_episodes
    )


def test_postgres_workflow_complete_auto_memory_does_not_treat_different_failure_reason_as_near_duplicate(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
            repo_url="https://example.com/org/repo-workflow-complete-auto-failure-reason-diff.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-failure-reason-diff",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-FAILURE-REASON-DIFF-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Compared weighted closeout fields",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching"
            },
            verify_status=VerifyStatus.FAILED,
            verify_report={"checks": ["pytest"], "status": "failed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.FAILED,
            summary="Failed while refining metadata-aware duplicate matching",
            verify_status=VerifyStatus.FAILED,
            verify_report={"checks": ["pytest"], "status": "failed"},
            failure_reason="first failure path",
        )
    )

    failure_reason_different_result = workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
        workflow=first_completed.workflow_instance,
        attempt=WorkflowAttempt(
            attempt_id=started.attempt.attempt_id,
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_number=2,
            status=WorkflowAttemptStatus.FAILED,
            verify_status=VerifyStatus.FAILED,
            failure_reason="second failure path",
            started_at=started.attempt.started_at,
            finished_at=datetime.now(UTC),
            created_at=started.attempt.created_at,
            updated_at=datetime.now(UTC),
        ),
        latest_checkpoint=WorkflowCheckpoint(
            checkpoint_id=uuid4(),
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="Compared weighted closeout fields again",
            checkpoint_json={
                "next_intended_action": "Implement metadata-aware duplicate matching"
            },
        ),
        verify_report=VerifyReport(
            verify_id=uuid4(),
            attempt_id=started.attempt.attempt_id,
            status=VerifyStatus.FAILED,
            report_json={"checks": ["pytest"], "status": "failed"},
        ),
        summary="Failed while refining duplicate matching with metadata-aware fields",
        failure_reason="second failure path",
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert failure_reason_different_result is not None
    assert failure_reason_different_result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "stored",
        "embedding_generation_skipped_reason": None,
        "embedding_provider": "local_stub",
        "embedding_model": "local-stub-v1",
        "embedding_vector_dimensions": 1536,
        "embedding_content_hash": failure_reason_different_result.details[
            "embedding_content_hash"
        ],
    }
    assert len(auto_episodes) == 2
    assert any(
        episode.metadata.get("failure_reason") == "second failure path"
        for episode in auto_episodes
    )


def test_postgres_workflow_complete_auto_memory_does_not_treat_different_verify_status_as_near_duplicate(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
            repo_url="https://example.com/org/repo-workflow-complete-auto-verify-diff.git",
            canonical_path="/tmp/integration-repo-workflow-complete-auto-verify-diff",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-AUTO-MEM-VERIFY-DIFF-001",
        )
    )
    workflow_service.create_checkpoint(
        CreateCheckpointInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            step_name="design_phase2",
            summary="First checkpoint summary",
            checkpoint_json={
                "next_intended_action": "Implement the minimum heuristic path"
            },
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    first_completed = workflow_service.complete_workflow(
        CompleteWorkflowInput(
            workflow_instance_id=started.workflow_instance.workflow_instance_id,
            attempt_id=started.attempt.attempt_id,
            workflow_status=WorkflowInstanceStatus.COMPLETED,
            summary="First completion summary",
            verify_status=VerifyStatus.PASSED,
            verify_report={"checks": ["pytest"], "status": "passed"},
        )
    )

    verify_different_result = (
        workflow_service._workflow_memory_bridge.record_workflow_completion_memory(
            workflow=first_completed.workflow_instance,
            attempt=WorkflowAttempt(
                attempt_id=started.attempt.attempt_id,
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_number=started.attempt.attempt_number,
                status=WorkflowAttemptStatus.SUCCEEDED,
                verify_status=VerifyStatus.FAILED,
                started_at=started.attempt.started_at,
                finished_at=datetime.now(UTC),
                created_at=started.attempt.created_at,
                updated_at=datetime.now(UTC),
            ),
            latest_checkpoint=WorkflowCheckpoint(
                checkpoint_id=uuid4(),
                workflow_instance_id=started.workflow_instance.workflow_instance_id,
                attempt_id=started.attempt.attempt_id,
                step_name="design_phase2",
                summary="Second checkpoint summary",
                checkpoint_json={
                    "next_intended_action": "Implement the minimum heuristic path"
                },
            ),
            verify_report=VerifyReport(
                verify_id=uuid4(),
                attempt_id=started.attempt.attempt_id,
                status=VerifyStatus.FAILED,
                report_json={"checks": ["pytest"], "status": "failed"},
            ),
            summary="Second completion summary",
            failure_reason=None,
        )
    )

    with uow_factory() as uow:
        assert uow.memory_episodes is not None
        workflow_episodes = uow.memory_episodes.list_by_workflow_id(
            started.workflow_instance.workflow_instance_id,
            limit=10,
        )
        auto_episodes = [
            episode
            for episode in workflow_episodes
            if episode.metadata.get("memory_origin") == "workflow_complete_auto"
        ]

    assert first_completed.auto_memory_details is not None
    assert first_completed.auto_memory_details["auto_memory_recorded"] is True
    assert verify_different_result is not None
    assert verify_different_result.details == {
        "auto_memory_recorded": True,
        "embedding_persistence_status": "stored",
        "embedding_generation_skipped_reason": None,
        "embedding_provider": "local_stub",
        "embedding_model": "local-stub-v1",
        "embedding_vector_dimensions": 1536,
        "embedding_content_hash": verify_different_result.details[
            "embedding_content_hash"
        ],
    }
    assert len(auto_episodes) == 2
    assert any(
        episode.metadata.get("verify_status") == "failed" for episode in auto_episodes
    )


def test_postgres_memory_search_hybrid_results_include_ranking_details(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
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
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
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
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
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
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)
    memory_service = MemoryService(
        episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
        workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
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
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
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


def test_postgres_settings_can_build_uow_factory_from_loaded_settings(
    postgres_pooled_uow_factory,
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
    connection_pool = build_connection_pool(config)
    try:
        service = WorkflowService(build_postgres_uow_factory(config, connection_pool))

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
    finally:
        connection_pool.close()
