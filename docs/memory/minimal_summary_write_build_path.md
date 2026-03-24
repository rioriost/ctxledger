# Minimal Summary Write/Build Path for `0.6.0`

## Purpose

This note defines the **minimum summary write/build path** for the current
`0.6.0` hierarchical-memory implementation.

It follows the currently established design decisions:

- `docs/memory/first_age_slice_boundary_decision.md`
- `docs/memory/minimal_hierarchy_model_decision.md`
- `docs/memory/first_memory_get_context_hierarchical_improvement_decision.md`
- `docs/memory/minimal_hierarchy_schema_repository_design.md`

This note answers the next implementation question:

> Now that canonical summaries can be stored and read, what is the smallest
> supported path for creating them in a way that stays behavior-preserving,
> relationally canonical, and operationally understandable?

The goal is to define a path that is:

- minimal
- explicit
- canonical-relational first
- easy to test
- easy to defer or disable
- compatible with later graph mirroring
- compatible with later richer summary-generation logic

---

## Status

**Decision status:** proposed current direction  
**Intended phase support:** follow-up to the first hierarchy slice in `0.6.0`

This note is a design-direction note for the next small write-side slice.
It does **not** claim that the described summary build path is already
implemented.

---

## Design summary

The minimum supported summary write/build path should be:

1. **explicit**
2. **rebuildable**
3. **scope-local**
4. **relationally canonical**
5. **separate from ordinary read-path execution**

More concretely:

- the first write/build path should create canonical summaries from already
  canonical memory items
- the first build target should be **one episode at a time**
- the first builder should create **one episode summary** over that episode's
  member memory items
- the first build path should write:
  - one `memory_summaries` row
  - one or more `memory_summary_memberships` rows
- the build path should be triggered explicitly by a dedicated application path
  or tightly scoped service call, not implicitly by ordinary retrieval
- repeated runs should behave predictably and avoid uncontrolled duplicate
  accumulation

This is the smallest useful write/build path because it closes the loop for the
new summary model without forcing global summarization policy or background
maintenance machinery too early.

---

## Why this is the right next step

The repository now already has:

- canonical summary types
- canonical summary persistence
- canonical summary membership persistence
- summary-first retrieval support
- summary-first service, serializer, MCP, and HTTP validation
- full-suite validation for the current first slice

What is still missing is a minimal canonical path for **producing** summaries.

Without a write/build path, summaries remain structurally supported but
operationally under-produced.

However, the next step should still stay small.

The repository should not jump immediately to:

- global auto-summarization
- recursive summary generation
- graph-driven summary construction
- background reconciliation workers
- summary write side effects during normal reads

Instead, it should first add one narrow, explicit, testable path that proves the
summary model can be built from canonical memory items.

---

## Core decision

The first supported summary write/build path should be:

- **episode-scoped**
- **explicitly invoked**
- **single-layer**
- **idempotent enough for safe reruns**
- **based on existing canonical memory items**

The first build target should therefore be:

- `episode -> memory_items -> one canonical episode summary`

This means the initial builder should:

1. resolve one canonical episode
2. resolve its direct canonical memory items
3. derive one summary text from those items
4. persist one canonical `memory_summary`
5. persist canonical summary memberships pointing to the selected memory items

This is intentionally narrower than a full summary system.

---

## Recommended first scope

## Build one summary per episode

The initial supported scope should be:

- one episode at a time

The initial summary kind should be:

- `episode_summary`

This is preferable to broader scopes because it:

- aligns with the existing episode-oriented retrieval model
- uses already-understood ownership boundaries
- avoids immediately needing workspace-wide ranking or clustering policy
- remains easy to explain and validate
- fits naturally with the first `summary -> memory_item` hierarchy shape

---

## What the first build path should consume

The builder should consume canonical relational inputs only.

### Required canonical inputs

At minimum:

- one `EpisodeRecord`
- direct `MemoryItemRecord` rows attached to that episode

### Optional future inputs, but not required now

Deferred:

- relation-derived supporting items
- workspace-root inherited items
- neighboring summaries
- summary-of-summary inputs
- graph traversal results
- embedding-driven clustering

The first build path should use the simplest direct canonical child set.

---

## What the first build path should produce

For one selected episode, the builder should produce:

### 1. One `memory_summaries` row

Minimum fields:

- `memory_summary_id`
- `workspace_id`
- `episode_id`
- `summary_text`
- `summary_kind = "episode_summary"`
- `metadata`
- timestamps

### 2. One or more `memory_summary_memberships` rows

For each included child memory item:

- `memory_summary_membership_id`
- `memory_summary_id`
- `memory_id`
- `membership_order`
- `metadata`
- timestamp

The result is one durable canonical summary plus explicit canonical membership.

---

## Summary text generation rule

The first builder should keep summary text generation simple and deterministic.

### Preferred initial generation rule

The initial summary text may be produced by a conservative builder such as:

- concatenating or compressing selected memory item contents
- optionally using a deterministic formatting rule
- optionally preferring the most recent or most representative items
- optionally bounded by a length limit

The key rule is:

- **the first build path should prefer determinism and explainability over
  sophistication**

This means the first implementation should avoid immediate dependence on:

- opaque LLM generation
- unstable ranking heuristics
- graph traversal
- multi-pass compression pipelines

### Why deterministic first is valuable

A deterministic first builder makes it easier to test:

- duplicate handling
- rerun behavior
- summary membership correctness
- retrieval behavior after build
- mismatch diagnosis between source items and generated summary

It also preserves a clean foundation for later optional AI-assisted summary
generation.

---

## Membership selection rule

The initial builder should include:

- the direct canonical memory items for the selected episode

### Ordering

The builder should assign `membership_order` deterministically.

Recommended first ordering:

- returned memory-item order from the canonical episode item query

That means the builder can preserve the existing item ordering basis rather than
inventing a new ranking system immediately.

### Why this is enough

The first goal is not to discover the globally best abstraction.

The first goal is to make the hierarchy durable, explicit, and testable.

---

## Invocation model

The first summary build path should be **explicitly invoked**.

### Preferred invocation shapes

Any of these can be valid first-step shapes:

- a dedicated CLI command
- a dedicated service method
- a narrowly scoped operator/developer-facing command
- a manual rebuild helper for a chosen episode

### What should not happen yet

The builder should **not** initially run:

- implicitly during `memory_get_context`
- automatically during every episode write
- automatically during ordinary startup
- automatically as part of graph bootstrap
- silently during unrelated workflow operations

The initial build path should be clear, explicit, and easy to reason about.

---

## Why not auto-build on every episode write yet

A tempting design is:

- remember episode
- immediately create summary
- immediately create memberships

This should be deferred at first.

### Reasons

1. It couples write-side memory ingestion to a new hierarchy feature too early.
2. It raises immediate policy questions:
   - when to rebuild
   - when to replace
   - whether to summarize partial episodes
   - whether every episode deserves a summary
3. It makes ordinary memory writes more operationally complex.
4. It blurs the distinction between:
   - canonical raw memory capture
   - canonical summary construction

The first summary build path should therefore remain separate from basic
episode-recording behavior.

---

## Why not build summaries during `workflow_complete` yet

A second tempting design is to attach summary generation to workflow completion
auto-memory.

That should also be deferred for the first write/build slice.

### Reasons

- workflow completion memory already has its own closeout logic
- summary production is a hierarchy concern, not just a workflow-closeout concern
- completion-bound generation would skip non-completion use cases
- it would complicate the current auto-memory path before the hierarchy builder
  is stable on its own

The initial summary builder should therefore remain its own explicit path.

---

## Duplicate and rebuild behavior

The first summary build path must be safe enough to rerun.

### Recommended current rule

For a given target episode and summary kind:

- treat rebuild as replacing the current builder-owned summary for that episode
  and kind

A practical first interpretation is:

1. find existing builder-owned summaries for:
   - `episode_id`
   - `summary_kind = "episode_summary"`
2. remove or supersede the old builder-owned summary rows and their memberships
3. insert the newly built summary
4. insert the new memberships

This gives a **replace-or-rebuild** model instead of uncontrolled accumulation.

### Why this is better than append-only duplication

It keeps the first build path:

- understandable
- testable
- predictable
- easier to reason about during retrieval

### Builder ownership metadata

To support this, the builder should stamp metadata that makes ownership explicit.

Recommended metadata examples:

- `"builder": "minimal_episode_summary_builder"`
- `"build_scope": "episode"`
- `"source": "explicit_build_path"`

This metadata makes future replacement and diagnostics easier.

---

## Failure handling

The first summary build path should fail explicitly and locally.

### If summary build fails

The system should:

- leave canonical source memory items untouched
- avoid partial silent mutation where possible
- return a clear failure to the caller
- avoid redefining existing memory retrieval as broken

### If input episode has no child memory items

The builder should choose one explicit behavior and document it.

Recommended first behavior:

- do **not** create a summary
- return an explicit no-op / skipped result such as:
  - `summary_built = false`
  - `skipped_reason = "no_episode_memory_items"`

This is preferable to generating low-value empty summaries.

---

## Repository boundary recommendation

The builder should rely on existing and new repositories, not bypass them.

### Likely repository inputs

- `EpisodeRepository`
- `MemoryItemRepository`
- `MemorySummaryRepository`
- `MemorySummaryMembershipRepository`

### Possible builder-local orchestration

The builder should orchestrate:

1. fetch episode
2. fetch child memory items
3. generate summary text
4. replace existing builder-owned summary for that episode/kind if needed
5. create summary
6. create memberships

This keeps persistence narrow and keeps build orchestration outside raw storage
methods.

---

## Recommended service boundary

The cleanest first shape is likely a dedicated service-oriented entry point,
such as a new summary-build helper/service rather than forcing the logic into
`MemoryService.get_context`.

Conceptually, something like:

- `build_episode_summary(episode_id: UUID) -> BuildSummaryResult`

or

- `rebuild_episode_summary(episode_id: UUID) -> BuildSummaryResult`

would be appropriate.

### Why this is a good first boundary

It is:

- explicit
- testable
- narrowly scoped
- easy to expose later via CLI or operator tooling
- easy to keep separate from ordinary reads

---

## Result shape recommendation

The first build path should return an explicit result object or payload.

Minimum useful fields:

- `summary_built: bool`
- `skipped_reason: str | None`
- `memory_summary_id: UUID | None`
- `episode_id: UUID`
- `summary_kind: str | None`
- `member_memory_count: int`
- `replaced_existing_summary: bool`
- `details: dict[str, Any]`

This makes the first builder easy to test and easy to observe.

---

## Metadata recommendation

The first built summary should carry enough metadata to explain:

- how it was built
- why it exists
- whether it is builder-owned
- what scope it summarizes

Recommended metadata examples:

- `"builder": "minimal_episode_summary_builder"`
- `"build_scope": "episode"`
- `"source_episode_id": "{episode_id}"`
- `"source_memory_item_count": {N}`
- `"build_version": "0.6.0-first-slice"`

These are additive and operationally useful.

---

## Interaction with retrieval

The initial retrieval path should not change dramatically just because the write
path now exists.

### Intended effect

Once the builder has created canonical summaries:

- `memory_get_context` can encounter them
- `memory_get_context` can prefer them through the existing summary-first slice
- direct member expansion can work from durable canonical memberships

### What should remain unchanged

The first write/build path should **not** by itself require:

- grouped response redesign
- graph traversal
- recursive hierarchy
- new retrieval route families
- broad compatibility-field removal

This keeps the write slice semantically narrow.

---

## Interaction with AGE

The write/build path should remain relationally canonical.

### Current rule

The builder writes:

- relational summary rows
- relational summary membership rows

It does **not** initially need to write graph state.

### Later possibility

A later follow-up may mirror:

- summary nodes
- membership edges

into AGE as derived state.

But the first build path should not require that.

This preserves:

- explicit ownership boundary
- rebuildability
- failure isolation
- behavior-preserving deployment expectations

---

## Validation strategy

The first summary build path should be validated incrementally.

### 1. Builder-local tests

Test:

- episode with one item
- episode with multiple items
- episode with no items
- rerun / replacement behavior
- membership ordering
- metadata stamping

### 2. Repository-integration tests

Test:

- summary row creation
- membership row creation
- replacement or rebuild behavior
- retrieval after build

### 3. Service retrieval follow-up tests

Test:

- builder-created summaries are preferred by `memory_get_context`
- summary memberships expand correctly
- fallback behavior still works when no built summary exists

### 4. Broader validation

After the slice is stable:

- run relevant focused suites
- run full pytest suite

---

## Suggested implementation order

A semantically small implementation order would be:

1. add a design-appropriate summary build result type
2. add a minimal dedicated builder/service entry point
3. implement deterministic episode-scoped summary text construction
4. implement create-or-replace summary persistence
5. implement membership persistence
6. add focused builder tests
7. add one integration test proving retrieval sees built summaries
8. only later consider automatic build triggers

---

## Non-goals

This first summary write/build path should **not** attempt to solve:

- summary-to-summary construction
- workspace-wide summarization
- graph-native build flows
- AI-heavy generation orchestration
- background reconciliation daemons
- auto-build on every memory write
- auto-build during every workflow completion
- final global summary policy
- final replacement/supersession lifecycle semantics across all future summary kinds

It only defines the minimum explicit write/build path for the first hierarchy
slice.

---

## Working rules

Use these rules for the first implementation.

### Ownership rule
- summaries and memberships remain canonical relational state

### Invocation rule
- summary build is explicit, not implicit

### Scope rule
- first build scope is one episode at a time

### Generation rule
- prefer deterministic, explainable summary text construction first

### Replacement rule
- reruns should replace or rebuild builder-owned summaries, not accumulate
  duplicates silently

### Retrieval rule
- the build path should feed the existing summary-first retrieval slice
  without forcing broad contract redesign

### Graph rule
- graph mirroring, if added later, remains derived and optional

---

## Decision summary

The minimum summary write/build path for `0.6.0` should be:

- an **explicit**
- **episode-scoped**
- **relationally canonical**
- **replace-or-rebuild**
- **single-layer**

builder that:

1. reads one episode's canonical memory items
2. generates one deterministic `episode_summary`
3. writes one canonical `memory_summaries` row
4. writes canonical `memory_summary_memberships` rows
5. avoids uncontrolled duplicate accumulation
6. stays separate from ordinary reads and ordinary memory writes

This is the smallest useful write-side slice that completes the first summary
hierarchy loop while remaining consistent with the current `0.6.0` boundaries.