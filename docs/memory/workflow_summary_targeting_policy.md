# Workflow-Scoped Summary Automation Targeting Policy for `0.6.0`

## Purpose

This note defines the **workflow-scoped targeting policy** for a future narrow
summary-automation slice in `0.6.0`.

It follows the currently established summary hierarchy work, including:

- canonical relational summary ownership
- explicit episode-scoped summary building
- replace-or-rebuild behavior for matching summary kinds
- summary-first retrieval through `memory_get_context`
- transport-surface coverage
- PostgreSQL-backed builder-to-retrieval integration
- the current workflow-oriented automation direction

This note answers the next implementation-policy question:

> If workflow completion is allowed to invoke summary building automatically,
> which episode should it target, under what conditions, and what should the
> result semantics be?

The goal is to define a policy that is:

- explicit
- narrow
- implementation-ready
- compatible with current workflow-completion memory behavior
- safe relative to canonical write boundaries
- small enough for `0.6.0`

---

## Status

**Decision status:** implementation-ready policy  
**Intended phase support:** narrow workflow-oriented automation follow-up in
`0.6.0`

This note defines the policy for a future implementation slice.
It does **not** claim that the described automation is already enabled.

---

## Current context

The repository already has a valid first summary loop:

- canonical `memory_summaries`
- canonical `memory_summary_memberships`
- explicit summary building through:
  - `MemoryService.build_episode_summary(...)`
  - `ctxledger build-episode-summary`
- replace-or-rebuild support
- summary-first retrieval
- PostgreSQL-backed builder-to-retrieval validation

The current workflow-completion path already has its own established behavior:

- closeout auto-memory capture
- duplicate suppression
- embedding persistence
- additive warning/details reporting

That means any automation added here should be treated as:

- a **follow-up orchestration layer**
- not a replacement for the current explicit builder
- not a redefinition of existing workflow completion truth

---

## Core decision

The first workflow-scoped summary automation slice should target:

- **only the newly created workflow-completion auto-memory episode**

It should run only when all of the following are true:

1. workflow completion auto-memory was successfully recorded
2. the current completion path explicitly opted in to summary building
3. the targeted episode has canonical child memory items
4. the summary kind is:
   - `episode_summary`
5. replacement remains enabled for the matching summary kind

This is the narrowest useful targeting rule because it avoids immediately having
to answer harder questions about:

- older workflow episodes
- all episodes in a workflow
- workspace-wide summary regeneration
- recursive summary building
- mixed summary-kind targeting

---

## Canonical target episode

## Rule

The canonical target episode for the first workflow-oriented automation slice is:

- the episode produced by the workflow-completion auto-memory path itself

In practice, this means:

- the workflow completes
- auto-memory creates one closeout episode and one closeout memory item
- if automation is enabled and gated-in, summary building targets that exact
  newly created episode

## Why this target is preferred

This target is preferred because it is:

- local
- deterministic
- already canonical
- directly tied to a workflow-completion event
- easy to explain in logs and result metadata
- easy to validate in focused tests

## What is intentionally not targeted

The first workflow-scoped targeting slice should **not** target:

- all episodes in the workflow
- the latest non-auto-memory episode
- all workflow episodes with memory items
- workspace episodes
- ticket-wide episode sets
- summaries across multiple workflows

Those can be evaluated later if there is a stronger product need.

---

## Eligibility rules

The first automation slice should use this rule set.

### Rule 1 — workflow completion must already have succeeded

Summary automation is a follow-up to successful workflow completion.
It must not run before completion succeeds.

### Rule 2 — auto-memory must already have been recorded

If workflow completion did not produce the canonical auto-memory episode and
memory item, summary automation should not run.

This means summary automation is skipped when:

- closeout auto-memory gating skipped recording
- duplicate suppression skipped recording
- near-duplicate suppression skipped recording
- auto-memory write failed before canonical episode creation
- no closeout summary source existed

### Rule 3 — explicit trigger is required

The first automation slice should not run for every successful workflow
completion by default.

It should require an explicit signal in the current workflow-completion context.

Recommended first trigger:

- `latest_checkpoint.checkpoint_json["build_episode_summary"] = true`

This keeps the first automation slice:

- explicit
- reviewable
- operator-understandable
- low-risk

### Rule 4 — target only one summary kind

The first automation slice should build only:

- `episode_summary`

Other summary kinds should remain explicit/manual unless a later slice proves
they need automation too.

### Rule 5 — replacement stays enabled

The automated call should use:

- replacement enabled for the matching summary kind

This keeps repeated completion-driven builds deterministic and avoids stale
matching summary accumulation.

### Rule 6 — the target episode must have meaningful child memory items

If the targeted episode has no child memory items, summary automation should
skip explicitly rather than creating an empty summary.

### Rule 7 — automation remains non-fatal

If summary automation fails:

- workflow completion remains successful
- auto-memory remains canonical if it already succeeded
- summary automation failure is surfaced through additive details and/or warnings

---

## Trigger model

## Current recommended trigger

The first implementation should trigger automation only when:

- workflow completion auto-memory succeeds
- and the latest checkpoint payload explicitly opts in

### Example trigger payload

A checkpoint payload shape like this is sufficient for the first slice:

- `build_episode_summary = true`

Example conceptual payload:

- `{"build_episode_summary": true}`

Optional additional fields may be considered later, but are not required for the
first slice.

## Why checkpoint payload is a good first trigger

It is:

- explicit
- workflow-local
- already part of current operational context
- easy to inspect later
- easy to keep narrow

## What the first slice should avoid

The first automation slice should avoid:

- global default-on behavior
- hidden configuration-only activation
- summary build on every completion regardless of intent
- implicit summary generation from generic completion success

---

## Invocation contract

The automated orchestration should conceptually call the explicit builder using a
shape equivalent to:

- `episode_id = {new auto-memory episode id}`
- `summary_kind = "episode_summary"`
- `replace_existing = true`

Recommended additive metadata for the automated build call:

- `source = "workflow_completion_auto_memory"`
- `workflow_instance_id = {workflow_instance_id}`
- `auto_memory_episode_id = {episode_id}`

This preserves provenance and makes later diagnosis easier.

---

## Result semantics

The first automation slice should return or expose additive details that make the
decision and result easy to understand.

### Minimum useful fields

Recommended fields include:

- `summary_build_attempted`
- `summary_build_succeeded`
- `summary_build_status`
- `summary_build_skipped_reason`
- `summary_build_replaced_existing_summary`
- `built_memory_summary_id`
- `built_summary_kind`
- `built_summary_membership_count`

### Current skip/failure reading

If automation does not actually run because policy or boundary conditions are not
satisfied, the result should be explicit rather than silent.

Example skip reasons:

- `workflow_summary_build_not_requested`
- `auto_memory_not_recorded`
- `no_episode_memory_items`
- `workflow_scoped_builder_integration_deferred`

### Warning behavior

If the automation path runs and fails unexpectedly:

- keep workflow completion successful
- attach warning(s)
- keep the error details additive rather than turning workflow completion into a
  failure

---

## Replacement behavior under repeated completion scenarios

The first automation slice must preserve deterministic behavior when completion
is retried or replayed.

## Rule

If the targeted auto-memory episode is summarized more than once for the same
`summary_kind`, the automation path should still use replace-or-rebuild
semantics.

## Why this matters

Without this rule, repeated automation could create:

- multiple matching summaries for the same closeout episode
- unclear retrieval precedence
- harder operational debugging

The current explicit builder already knows how to replace matching summary kinds.
Automation must reuse that behavior rather than inventing a second policy.

---

## Failure handling

If the automated summary build fails:

- workflow completion should remain successful
- the closeout episode and memory item should remain canonical if they were
  already written
- the system should surface the failure through:
  - result details
  - warning(s)
  - logs

## Why this is the right failure posture

Summary automation is still a follow-up hierarchy behavior, not the primary
operational truth of workflow completion.

That means:

- workflow completion should not be rolled back solely because summary building
  failed
- canonical closeout memory should remain intact if it was already committed

---

## Observability requirements

The first automation slice should be easy to reason about after the fact.

### Logs should make clear

- whether automation was eligible
- whether it was triggered
- which episode was targeted
- which summary kind was requested
- whether replacement occurred
- whether the build succeeded, skipped, or failed

### Result details should make clear

- why a build did or did not happen
- whether the current completion created summary state
- what summary was built when successful

### Operator-facing interpretation rule

An operator should be able to answer, from one completion result and one quick
inspection path:

- did summary automation run?
- if not, why not?
- if yes, what summary did it build?

---

## Current implementation decision

For the current repository state, this targeting policy should be treated as:

- the **next implementation-ready policy**
- not yet a broad always-on behavior
- still intentionally narrow
- still intentionally bound to workflow completion auto-memory

That means:

- the policy is ready
- implementation can be added in a bounded slice
- no foundational design uncertainty remains about the initial target episode

---

## Non-goals

The first workflow-scoped targeting slice should **not** attempt to solve:

- multi-episode workflow summarization
- workspace-wide summary automation
- ticket-wide automation
- summary-to-summary recursion
- graph-dependent summary generation
- final long-term summary policy for every workflow event
- broad configuration matrices for every possible workflow status

Those are later concerns.

---

## Recommended next implementation slice

If this policy is implemented, the next narrow slice should:

1. read the latest checkpoint payload
2. detect whether `build_episode_summary = true`
3. verify that workflow completion auto-memory was recorded
4. target the newly created auto-memory episode only
5. call the explicit builder with:
   - `summary_kind = "episode_summary"`
   - replacement enabled
6. record additive success/skip/failure details
7. keep workflow completion successful even if the build fails

### Focused test scenarios

The first implementation should include focused tests for:

- trigger present -> summary build invoked
- trigger absent -> summary build skipped
- auto-memory skipped -> summary build skipped
- no child memory items -> summary build skipped
- builder failure -> workflow completion still succeeds with warning/details
- repeated run -> replacement remains deterministic

---

## Summary

The implementation-ready workflow-scoped targeting policy for the first
automation slice is:

- trigger only after workflow completion auto-memory succeeds
- require an explicit checkpoint/workflow signal
- target only the newly created workflow-completion auto-memory episode
- build only `episode_summary`
- keep replacement enabled
- keep failure non-fatal to workflow completion
- keep all outcomes explicit and observable

This is the smallest safe policy that can move the system from explicit manual
summary building toward workflow-oriented automation without prematurely
overbuilding the hierarchy system.