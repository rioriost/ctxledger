# Minimal Hierarchy Schema and Repository Design for `0.6.0`

## Purpose

This note defines the **minimum schema and repository design** needed to
implement the currently chosen `0.6.0` hierarchy direction.

It follows these canonical design decisions:

- `docs/memory/decisions/first_age_slice_boundary_decision.md`
- `docs/memory/decisions/minimal_hierarchy_model_decision.md`
- `docs/memory/decisions/first_memory_get_context_hierarchical_improvement_decision.md`

This note answers the next implementation-preparation question:

> What is the smallest relational schema and repository surface needed to
> support canonical summaries, summary membership, and the first
> summary-first retrieval improvement?

The goal is to define a design that is:

- small
- canonical-relational first
- repository-friendly
- compatible with current in-memory and PostgreSQL patterns
- compatible with later derived AGE mirroring
- implementable without broad contract churn

---

## Status

**Decision status:** active  
**Intended phase support:** `0.6.0` Phase B and early Phase D

This note should be read as an implementation-oriented design note, not yet as a
claim that the described schema and repositories are already implemented.

---

## Design summary

The minimum implementation design is:

1. add a canonical relational `memory_summaries` table
2. add a canonical relational `memory_summary_memberships` table
3. introduce explicit summary record and membership record types
4. introduce narrow summary-oriented repository contracts
5. keep summary membership distinct from generic `memory_relations`
6. keep graph state derived and optional at this layer
7. keep first retrieval integration focused on:
   - selecting summaries
   - expanding direct member memory items

This is the smallest useful design that can support:

- canonical summary persistence
- canonical summary-to-item expansion
- summary-first selection
- direct member-item expansion
- later derived graph mirroring if justified

---

## Canonical storage boundary

The canonical storage boundary remains:

- PostgreSQL relational tables are authoritative
- summary entities are canonical relational data
- summary membership mappings are canonical relational data
- AGE graph state, if later added for this model, is derived and rebuildable

This design does **not** make summaries or membership graph-native.

This design also does **not** overload generic `memory_relations` with summary
membership semantics.

---

## Minimal relational schema

## 1. `memory_summaries`

The first new canonical table should be `memory_summaries`.

### Role

This table stores the first compressed hierarchy layer above `memory_items`.

Each row represents a canonical summary unit that may later be selected by
hierarchy-aware retrieval.

### Recommended columns

Minimum recommended shape:

- `memory_summary_id UUID PRIMARY KEY`
- `workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE`
- `episode_id UUID REFERENCES episodes(episode_id) ON DELETE CASCADE`
- `summary_text TEXT NOT NULL`
- `summary_kind TEXT NOT NULL`
- `metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

### Notes on column meaning

#### `workspace_id`
Required because summary retrieval will often need a stable workspace-scoped
ownership boundary even when episode linkage is absent or later broadened.

#### `episode_id`
Optional in the schema, but useful for the first slice because it allows a
summary to remain attached to a current episode-oriented retrieval surface
without making summaries identical to episodes.

#### `summary_text`
Stores the actual compressed textual content.

#### `summary_kind`
Allows the first implementation to distinguish narrow summary roles without
needing a generic hierarchy engine.

Recommended early values could remain conservative, such as:

- `episode_summary`
- `workspace_summary`

The exact initial enum-like set can remain implementation-local, but the design
should keep it narrow and explicit.

#### `metadata_json`
Allows lightweight extensibility without forcing early extra columns.

### Recommended constraints

At minimum:

- `CHECK (btrim(summary_text) <> '')`
- `CHECK (btrim(summary_kind) <> '')`

### Recommended indexes

Minimum recommended indexes:

- `(workspace_id, created_at DESC)`
- `(episode_id, created_at DESC)` where episode linkage is expected to matter
- optionally `(workspace_id, summary_kind, created_at DESC)`

### Updated-at handling

Use the existing shared `set_updated_at()` trigger pattern already present in the
schema.

That keeps summary rows aligned with the current repository conventions for
mutable canonical records.

---

## 2. `memory_summary_memberships`

The second new canonical table should be `memory_summary_memberships`.

### Role

This table stores the canonical mapping from a summary to its member
`memory_items`.

This is the first real hierarchy edge in the model.

### Recommended columns

Minimum recommended shape:

- `memory_summary_membership_id UUID PRIMARY KEY`
- `memory_summary_id UUID NOT NULL REFERENCES memory_summaries(memory_summary_id) ON DELETE CASCADE`
- `memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE`
- `membership_order INTEGER`
- `metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

### Notes on column meaning

#### `memory_summary_id`
Identifies the canonical parent summary.

#### `memory_id`
Identifies the canonical member memory item.

#### `membership_order`
Optional but recommended.

It gives the design a place to preserve deterministic child ordering without
forcing a second migration if ordering becomes useful immediately in retrieval or
response shaping.

The first implementation does not need sophisticated ordering semantics.
Nullable ordering is enough.

#### `metadata_json`
Useful for later small extensions without changing the table shape too early.

### Recommended constraints

Minimum recommended constraints:

- unique summary membership per summary-item pair

Recommended as:

- `UNIQUE (memory_summary_id, memory_id)`

If `membership_order` is used semantically later, additional constraints may be
added then, but they are not required for the first slice.

### Recommended indexes

Minimum recommended indexes:

- `(memory_summary_id, membership_order, created_at, memory_id)`
- `(memory_id, created_at DESC)`

These support both primary directions:

- expand member items for a summary
- find summaries associated with a memory item if needed later

---

## Why membership should not be stored only in `memory_relations`

It may be tempting to represent summary membership as another
`relation_type` in `memory_relations`.

This note recommends **not** doing that for the first hierarchy slice.

### Reasons

1. summary membership is part of the hierarchy model itself
2. membership semantics are structurally different from ad hoc semantic
   relations like `supports`
3. explicit membership tables make repository contracts clearer
4. explicit membership avoids overloading relation traversal policy too early
5. explicit membership keeps canonical hierarchy ownership understandable even if
   graph mirroring is later added

So the current design rule is:

- use `memory_relations` for semantic directional relations
- use `memory_summary_memberships` for hierarchy membership

---

## Proposed Python record types

The current type layer already contains:

- `EpisodeRecord`
- `MemoryItemRecord`
- `MemoryRelationRecord`

The minimal hierarchy implementation should add:

- `MemorySummaryRecord`
- `MemorySummaryMembershipRecord`

## 1. `MemorySummaryRecord`

Recommended conceptual shape:

- `memory_summary_id: UUID`
- `workspace_id: UUID`
- `episode_id: UUID | None = None`
- `summary_text: str`
- `summary_kind: str`
- `metadata: dict[str, Any] = field(default_factory=dict)`
- `created_at: datetime`
- `updated_at: datetime`

### Why this shape fits the current codebase

It matches current type conventions:

- dataclass-based records
- explicit IDs
- JSON metadata support
- timestamps on canonical records

It also keeps naming explicit and domain-local.

## 2. `MemorySummaryMembershipRecord`

Recommended conceptual shape:

- `memory_summary_membership_id: UUID`
- `memory_summary_id: UUID`
- `memory_id: UUID`
- `membership_order: int | None = None`
- `metadata: dict[str, Any] = field(default_factory=dict)`
- `created_at: datetime`

### Why keep membership explicit

This makes hierarchy membership a first-class durable concept and avoids forcing
the repository layer to infer hierarchy edges indirectly.

---

## Proposed repository boundaries

The repository surface should stay small and oriented around canonical
persistence and simple expansion primitives.

## 1. `MemorySummaryRepository`

Recommended minimum responsibilities:

- create a summary
- list summaries by workspace
- list summaries by episode
- list summaries by summary IDs
- optionally list summaries by memory item through membership join, if needed
  later

### Recommended minimum methods

Initial narrow contract:

- `create(summary: MemorySummaryRecord) -> MemorySummaryRecord`
- `list_by_workspace_id(workspace_id: UUID, *, limit: int) -> tuple[MemorySummaryRecord, ...]`
- `list_by_episode_id(episode_id: UUID, *, limit: int) -> tuple[MemorySummaryRecord, ...]`
- `list_by_summary_ids(summary_ids: tuple[UUID, ...]) -> tuple[MemorySummaryRecord, ...]`

### Why this is enough initially

This supports:

- summary persistence
- scope-based summary selection
- future service-level summary-first retrieval

without prematurely introducing ranking or orchestration logic.

## 2. `MemorySummaryMembershipRepository`

Recommended minimum responsibilities:

- create summary membership
- list memberships for selected summaries
- list memberships for a single summary
- optionally list memberships by memory item later

### Recommended minimum methods

Initial narrow contract:

- `create(membership: MemorySummaryMembershipRecord) -> MemorySummaryMembershipRecord`
- `list_by_summary_id(memory_summary_id: UUID, *, limit: int) -> tuple[MemorySummaryMembershipRecord, ...]`
- `list_by_summary_ids(memory_summary_ids: tuple[UUID, ...]) -> tuple[MemorySummaryMembershipRecord, ...]`

### Optional early convenience method

A very useful early convenience method would be:

- `list_member_memory_ids_by_summary_ids(memory_summary_ids: tuple[UUID, ...]) -> tuple[UUID, ...]`

This may help keep service logic smaller and deterministic.

However, it is not mandatory if service code can safely derive this from
membership records plus existing `MemoryItemRepository.list_by_memory_ids(...)`.

---

## Recommended service composition

The service layer should compose the new repositories with existing ones.

### Existing repositories likely reused

- `EpisodeRepository`
- `MemoryItemRepository`
- `MemoryRelationRepository`
- workflow and workspace lookup repositories

### New repositories

- `MemorySummaryRepository`
- `MemorySummaryMembershipRepository`

### Recommended first retrieval flow

The first summary-first retrieval slice should be able to do:

1. resolve the relevant scope
2. retrieve candidate summaries for that scope
3. choose one or more summaries
4. retrieve summary memberships
5. retrieve member memory items through existing `MemoryItemRepository`
6. assemble grouped output and additive metadata in the service layer

This keeps:

- persistence logic in repositories
- retrieval orchestration in services
- response shaping outside repository contracts

---

## Recommended in-memory implementation shape

The current codebase uses simple in-memory repositories and store dictionaries.

The minimum in-memory implementation can follow the same pattern.

## In-memory storage additions

Recommended new backing stores:

- `memory_summaries_by_id: dict[object, MemorySummaryRecord]`
- `memory_summary_memberships_by_id: dict[object, MemorySummaryMembershipRecord]`

These should be threaded through:

- in-memory repository classes
- in-memory unit of work
- in-memory store snapshot support
- in-memory factory wiring

## In-memory repository behavior

### `InMemoryMemorySummaryRepository`
Recommended behavior:

- append/store by id
- sort by `created_at DESC` for list operations
- keep deterministic ordering

### `InMemoryMemorySummaryMembershipRepository`
Recommended behavior:

- append/store by id
- support filtering by `memory_summary_id`
- support bulk filtering by summary ids
- preserve deterministic ordering by:
  - `membership_order` when present
  - then `created_at`
  - then stable id fallback if needed

This is enough for focused tests and early service integration.

---

## Recommended PostgreSQL repository implementation shape

The current PostgreSQL persistence layer already uses repository classes with
explicit row-to-record conversion and narrow query methods.

The summary implementation should follow that pattern.

## `PostgresMemorySummaryRepository`

Recommended minimum queries:

- insert summary
- select by workspace ordered by `created_at DESC, memory_summary_id DESC`
- select by episode ordered by `created_at DESC, memory_summary_id DESC`
- select by summary ids

### Row mapping
A `_row_to_memory_summary(...)` helper would likely mirror the existing style of:

- `_row_to_episode(...)`
- `_memory_item_row_to_record(...)`

## `PostgresMemorySummaryMembershipRepository`

Recommended minimum queries:

- insert membership
- select by single summary id
- select by multiple summary ids

### Ordering recommendation
For summary expansion, deterministic membership order matters.

Recommended SQL ordering:

1. `membership_order ASC NULLS LAST`
2. `created_at ASC`
3. `memory_summary_membership_id ASC`

That gives stable expansion even before sophisticated ranking exists.

---

## Unit-of-work integration

The design fits naturally into the current unit-of-work style.

### Recommended new unit-of-work attributes

Where supported, add:

- `memory_summaries`
- `memory_summary_memberships`

### Why this matches current patterns

The codebase already uses unit-of-work attributes for:

- `memory_episodes`
- `memory_items`
- `memory_embeddings`

So the hierarchy additions can remain consistent with existing layering rather
than introducing a separate persistence mechanism.

---

## Suggested SQL shape

The exact migration should follow repository conventions, but the schema intent
can be expressed like this:

```ctxledger/schemas/postgres.sql#L1-1
-- illustrative snippet only; line numbers will differ when implemented
```

Recommended logical shape:

```/dev/null/ctxledger_memory_summary_schema.sql#L1-41
CREATE TABLE IF NOT EXISTS memory_summaries (
  memory_summary_id UUID PRIMARY KEY,
  workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
  episode_id UUID REFERENCES episodes(episode_id) ON DELETE CASCADE,
  summary_text TEXT NOT NULL,
  summary_kind TEXT NOT NULL,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT memory_summaries_summary_text_not_empty
    CHECK (btrim(summary_text) <> ''),
  CONSTRAINT memory_summaries_summary_kind_not_empty
    CHECK (btrim(summary_kind) <> '')
);

CREATE INDEX IF NOT EXISTS idx_memory_summaries_workspace_created_desc
  ON memory_summaries (workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_memory_summaries_episode_created_desc
  ON memory_summaries (episode_id, created_at DESC);

DROP TRIGGER IF EXISTS trg_memory_summaries_set_updated_at ON memory_summaries;
CREATE TRIGGER trg_memory_summaries_set_updated_at
BEFORE UPDATE ON memory_summaries
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
```

And:

```/dev/null/ctxledger_memory_summary_membership_schema.sql#L1-24
CREATE TABLE IF NOT EXISTS memory_summary_memberships (
  memory_summary_membership_id UUID PRIMARY KEY,
  memory_summary_id UUID NOT NULL REFERENCES memory_summaries(memory_summary_id) ON DELETE CASCADE,
  memory_id UUID NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
  membership_order INTEGER,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT memory_summary_memberships_unique_summary_member
    UNIQUE (memory_summary_id, memory_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_summary_memberships_summary_order_created
  ON memory_summary_memberships (
    memory_summary_id,
    membership_order,
    created_at,
    memory_id
  );

CREATE INDEX IF NOT EXISTS idx_memory_summary_memberships_memory_created_desc
  ON memory_summary_memberships (memory_id, created_at DESC);
```

These snippets are illustrative design targets, not a claim of implementation.

---

## Recommended repository protocol sketch

A narrow protocol sketch could look like this:

```/dev/null/ctxledger_memory_summary_protocols.py#L1-33
class MemorySummaryRepository(Protocol):
    def create(self, summary: MemorySummaryRecord) -> MemorySummaryRecord: ...

    def list_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]: ...

    def list_by_episode_id(
        self,
        episode_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryRecord, ...]: ...

    def list_by_summary_ids(
        self,
        summary_ids: tuple[UUID, ...],
    ) -> tuple[MemorySummaryRecord, ...]: ...


class MemorySummaryMembershipRepository(Protocol):
    def create(
        self,
        membership: MemorySummaryMembershipRecord,
    ) -> MemorySummaryMembershipRecord: ...

    def list_by_summary_id(
        self,
        memory_summary_id: UUID,
        *,
        limit: int,
    ) -> tuple[MemorySummaryMembershipRecord, ...]: ...

    def list_by_summary_ids(
        self,
        memory_summary_ids: tuple[UUID, ...],
    ) -> tuple[MemorySummaryMembershipRecord, ...]: ...
```

This protocol intentionally avoids:

- retrieval route policy
- ranking semantics
- grouped output shaping
- graph-specific traversal behavior

---

## Recommended type sketch

A minimum type sketch could look like this:

```/dev/null/ctxledger_memory_summary_types.py#L1-26
@dataclass(slots=True, frozen=True)
class MemorySummaryRecord:
    memory_summary_id: UUID
    workspace_id: UUID
    episode_id: UUID | None = None
    summary_text: str = ""
    summary_kind: str = "episode_summary"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, frozen=True)
class MemorySummaryMembershipRecord:
    memory_summary_membership_id: UUID
    memory_summary_id: UUID
    memory_id: UUID
    membership_order: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

Again, this is a design sketch, not implementation.

---

## AGE compatibility boundary

This schema and repository design intentionally keeps AGE out of the canonical
ownership path.

### If later graph mirroring is added

A later derived graph mirror may represent:

- summary nodes
- memory item nodes
- summary-membership edges

But that should remain:

- derived
- rebuildable
- optional at this implementation boundary
- subordinate to relational canonical storage

### What this means operationally

The first summary-first retrieval improvement should be implementable entirely
from relational state.

Graph traversal may later optimize or extend retrieval, but it is not required to
validate the first summary hierarchy slice.

---

## Validation and testing implications

This design supports a clean testing sequence.

## 1. Type-level tests
Validate:

- summary record construction
- membership record construction
- timestamp/default behavior
- metadata preservation

## 2. In-memory repository tests
Validate:

- create/list behaviors
- deterministic ordering
- unique membership expectations at the repository or fixture layer
- bulk expansion behavior

## 3. PostgreSQL repository tests
Validate:

- inserts
- workspace/episode summary listing
- summary membership listing
- row mapping correctness
- ordering correctness

## 4. Service-layer tests
Validate later:

- summary-first selection
- member-item expansion
- grouped-primary shaping
- compatibility field continuity
- fallback behavior remaining intact elsewhere

---

## Suggested implementation order

The smallest practical implementation sequence is:

1. add `MemorySummaryRecord` and `MemorySummaryMembershipRecord`
2. add repository protocols for summaries and memberships
3. add in-memory repositories and wiring
4. add schema tables to `schemas/postgres.sql`
5. add PostgreSQL repositories and unit-of-work wiring
6. add focused repository tests
7. integrate the first summary-first retrieval path in `memory_get_context`
8. add focused service tests
9. only then consider any graph mirroring for summaries if a concrete traversal
   benefit exists

This ordering keeps the implementation semantically small and testable.

---

## Non-goals of this design note

This note does **not**:

- implement summary generation logic
- define long-term summary ranking policy
- define summary-to-summary recursion
- define graph traversal semantics
- require immediate AGE mirroring
- redesign `memory_get_context` transport contracts wholesale
- collapse summary membership into generic memory relations
- introduce a generic hierarchy platform

It only defines the minimum schema and repository design needed to implement the
already chosen minimal hierarchy direction.

---

## Working rules

Use these rules during implementation.

### Ownership rule
- `memory_summaries` and `memory_summary_memberships` are canonical relational
  state

### Separation rule
- summary membership is not just another generic memory relation

### Repository rule
- repositories persist and retrieve summaries and memberships
- services orchestrate selection, expansion, and shaping

### Scope rule
- first expansion is direct only:
  - `summary -> memory_item`

### Graph rule
- any AGE representation is derived and optional at this boundary

### Change-size rule
- keep the first implementation semantically narrow
- avoid mixing schema, retrieval redesign, and graph expansion all at once

---

## Decision summary

The minimum implementation design for the first summary hierarchy slice is:

- a canonical `memory_summaries` table
- a canonical `memory_summary_memberships` table
- explicit `MemorySummaryRecord` and `MemorySummaryMembershipRecord` types
- narrow summary and membership repository contracts
- direct summary-to-memory-item expansion
- no required summary recursion
- no graph-native truth
- no overload of generic `memory_relations`

This is the smallest schema and repository design that can support the chosen
`0.6.0` hierarchy path while staying aligned with the current Phase A, Phase B,
and first retrieval-improvement decisions.