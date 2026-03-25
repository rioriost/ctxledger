# Next Minimal Hierarchy Primitive Design

## Context

The recent `memory_get_context` groundwork has already pushed two meaningful retrieval concerns down into repository-oriented primitives:

- workspace-root inherited context selection
- constrained `supports` relation target item resolution

That has made the service layer more declarative without widening retrieval semantics.

The next step should stay equally small.

## Decision

The next minimal hierarchy primitive should be:

- `MemoryItemRepository.list_by_episode_ids(...)`

This primitive should support retrieving memory items for a set of selected episode ids in one repository call.

## Why this is the next smallest useful primitive

The remaining hierarchy-shaped orchestration in `memory_get_context` is still centered on:

1. selecting episodes
2. collecting child memory items for those episodes
3. projecting those items into summary-first, episode-direct, and grouped outputs

Of those steps, the most natural repository concern is step 2.

A multi-episode child-item retrieval primitive:

- follows the existing `list_by_episode_id(...)` contract naturally
- reduces service-layer episode fanout
- helps both summary-first and grouped-selection work
- does not force early decisions about broader relation traversal
- keeps grouping and output semantics in the service layer

## Why not relation-first

A relation-oriented next primitive is possible, but it is not the smallest hierarchy step.

Examples such as:

- `list_by_source_memory_ids(...)`
- relation-type-filtered bulk relation retrieval

would immediately raise broader design questions:

- whether the primitive is `supports`-specific or generic
- whether relation traversal should stay one-hop
- whether grouping semantics belong with relation selection
- whether relation-aware ranking is being introduced implicitly

That would broaden the slice too early.

## Why not summary-first

A summary-specific primitive is also not the best next step.

Summary construction is still closer to retrieval projection than persistence selection. Pushing summary semantics into repositories now would blur layering too early and make the repository contract carry presentation-oriented meaning.

## Proposed contract shape

Initial shape:

- `list_by_episode_ids(episode_ids: tuple[UUID, ...]) -> tuple[MemoryItemRecord, ...]`

## Contract constraints

For the first slice, keep the contract deliberately narrow:

- accept a tuple of episode ids
- return a flat tuple of `MemoryItemRecord`
- return an empty tuple for empty input
- preserve deterministic ordering
- do not introduce grouped return shapes
- do not include summary semantics
- do not introduce per-episode limits
- do not add relation semantics

## Service-layer use

The intended service refactor is small:

1. collect selected episode ids
2. retrieve all matching memory items through `list_by_episode_ids(...)`
3. regroup them by episode in service code
4. preserve existing response semantics

This keeps the change structural rather than behavioral.

## Expected benefits

This primitive should make the service contract cleaner in the same way the previous slices did:

- repository handles one more retrieval selection primitive explicitly
- service remains responsible for orchestration and grouped output assembly
- future grouped-selection cleanup becomes easier
- future summary-first cleanup gets a clearer child-item input boundary

## Non-goals for this slice

This slice should not attempt to:

- broaden relation traversal behavior
- change `memory_get_context` response semantics
- introduce summary aggregation contracts
- redesign grouped output structure
- add ranking changes

## Recommended next implementation slice

1. add `list_by_episode_ids(...)` to the memory item repository protocol
2. implement it in in-memory and Postgres repositories
3. switch episode child-item collection in `memory_get_context` to use it
4. keep all external response shapes and retrieval semantics unchanged

## Decision summary

The next minimal hierarchy primitive should be a bulk episode-child retrieval primitive, not a relation-first or summary-first abstraction.

The key design rule is:

- move retrieval input selection downward
- keep hierarchy meaning and grouped projection in the service layer