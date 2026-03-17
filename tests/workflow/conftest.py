from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ctxledger.db import InMemoryStore, build_in_memory_uow_factory
from ctxledger.workflow.memory_bridge import (
    EpisodeRecord,
    MemoryEmbeddingRecord,
    MemoryItemRecord,
    WorkflowMemoryBridge,
)
from ctxledger.workflow.service import (
    RegisterWorkspaceInput,
    WorkflowService,
    Workspace,
)


class RecordingEpisodeRepository:
    def __init__(self) -> None:
        self.episodes: list[EpisodeRecord] = []

    def create(self, episode: EpisodeRecord) -> EpisodeRecord:
        self.episodes.append(episode)
        return episode

    def list_by_workflow_id(
        self,
        workflow_instance_id,
        *,
        limit: int,
    ) -> tuple[EpisodeRecord, ...]:
        episodes = [
            episode
            for episode in self.episodes
            if episode.workflow_instance_id == workflow_instance_id
        ]
        episodes.sort(key=lambda episode: episode.created_at, reverse=True)
        return tuple(episodes[:limit])


class RecordingMemoryItemRepository:
    def __init__(self) -> None:
        self.memory_items: list[MemoryItemRecord] = []

    def create(self, memory_item: MemoryItemRecord) -> MemoryItemRecord:
        self.memory_items.append(memory_item)
        return memory_item


class RecordingMemoryEmbeddingRepository:
    def __init__(self) -> None:
        self.embeddings: list[MemoryEmbeddingRecord] = []

    def create(self, embedding: MemoryEmbeddingRecord) -> MemoryEmbeddingRecord:
        self.embeddings.append(embedding)
        return embedding


def make_service_and_uow(
    *,
    workflow_memory_bridge: WorkflowMemoryBridge | None = None,
) -> tuple[WorkflowService, object]:
    store = InMemoryStore.create()
    uow_factory = build_in_memory_uow_factory(store)
    service = WorkflowService(
        uow_factory,
        workflow_memory_bridge=workflow_memory_bridge,
    )
    return service, store


def register_workspace(service: WorkflowService) -> Workspace:
    return service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo.git",
            canonical_path="/tmp/repo",
            default_branch="main",
        )
    )


def build_recording_workflow_memory_bridge() -> tuple[
    WorkflowMemoryBridge,
    RecordingEpisodeRepository,
    RecordingMemoryItemRepository,
    RecordingMemoryEmbeddingRepository,
]:
    episode_repository = RecordingEpisodeRepository()
    memory_item_repository = RecordingMemoryItemRepository()
    memory_embedding_repository = RecordingMemoryEmbeddingRepository()
    bridge = WorkflowMemoryBridge(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_embedding_repository=memory_embedding_repository,
        embedding_generator=None,
    )
    return (
        bridge,
        episode_repository,
        memory_item_repository,
        memory_embedding_repository,
    )


def make_aged_episode_copy(
    episode: EpisodeRecord,
    *,
    created_at: datetime = datetime(2024, 1, 1, tzinfo=UTC),
    updated_at: datetime = datetime(2024, 1, 1, tzinfo=UTC),
) -> EpisodeRecord:
    return EpisodeRecord(
        episode_id=episode.episode_id,
        workflow_instance_id=episode.workflow_instance_id,
        summary=episode.summary,
        attempt_id=episode.attempt_id,
        metadata=dict(episode.metadata),
        status=episode.status,
        created_at=created_at,
        updated_at=updated_at,
    )


def new_uuid() -> str:
    return str(uuid4())
