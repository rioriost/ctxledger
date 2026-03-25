# Workflow-Oriented Summary Automation Direction for `0.6.0`

## Purpose

This note defines the current direction for connecting the explicit summary
builder to workflow-oriented automation.

It follows the currently established hierarchy work for `0.6.0`, including:

- relational canonical summary ownership
- explicit summary-first retrieval
- the minimal explicit episode summary builder
- replace-or-rebuild behavior for matching episode summaries
- behavior-preserving boundaries around existing memory and retrieval paths

This note answers the next design question:

> How should the new episode summary builder relate to workflow-oriented
> automation without prematurely turning summary generation into an opaque or
> overly broad side effect?

The goal is to define a path that is:

- explicit about ownership and triggering
- incremental
- operationally understandable
- safe relative to current workflow-completion memory behavior
- compatible with future richer automation
- still small enough for `0.6.0`

---

## Status

**Decision status:** implementation-ready direction  
**Intended phase support:** post-first summary build loop follow-up in `0.6.0`

This note is now intended to be concrete enough to guide a narrow follow-up
implementation slice.

At the current stage, workflow-completion-triggered summary building should be
read as:

- **considered**
- **design-framed**
- **implementation-ready at the policy level**
- still deferred in code until the follow-up slice is intentionally enabled

---

## Context

The repository now already has a meaningful first summary loop:

- canonical `memory_summaries`
- canonical `memory_summary_memberships`
- summary-first retrieval through `memory_get_context`
- an explicit `build_episode_summary(...)` path
- replace-or-rebuild semantics
- CLI access through:
  - `ctxledger build-episode-summary`
- in-memory and PostgreSQL-backed validation
- transport coverage across serializer, MCP, and HTTP retrieval surfaces

That means the next natural question is not whether summaries can exist.

They can.

The next question is:

- when should summary building happen automatically
- how should workflow-oriented automation invoke it
- how should that automation stay understandable and safe

---

## Core direction

The current recommended direction is:

- **workflow-oriented automation should be possible**
- but it should remain **explicitly scoped and gated**
- and it should **not** immediately become a hidden side effect of all workflow
  or memory writes

In practical terms:

1. keep the explicit builder as the canonical write path
2. treat workflow-oriented automation as an orchestrated caller of that builder
3. start with narrow automation opportunities
4. avoid broad automatic summary generation across all episode writes
5. preserve current workflow-completion auto-memory behavior unless an explicit
   follow-up slice chooses to augment it

This means workflow-oriented automation should be built *on top of* the explicit
builder, not as a competing path.

---

## Why this direction is appropriate now

### 1. The explicit builder exists and should remain the primitive

The explicit builder now gives the system:

- one small canonical summary write path
- a clear replace-or-rebuild model
- deterministic episode-scoped summary text construction
- a testable persistence boundary

That should remain the primitive that automation reuses.

If workflow-oriented automation bypasses it too early, the system risks creating:

- two different summary creation paths
- duplicate policy drift
- inconsistent replacement behavior
- harder-to-debug behavior across environments

### 2. Workflow completion memory already has its own responsibility

The current workflow-completion memory path already handles:

- closeout memory capture
- duplicate suppression
- embedding persistence
- workflow-oriented metadata shaping

That means any automation linking summary building to workflow completion must be
careful not to blur the boundary between:

- closeout memory capture
- hierarchy summary construction

Those are related, but not identical, responsibilities.

### 3. The current hierarchy path is still intentionally constrained

The current summary model is still:

- single-layer
- relationally canonical
- `summary -> memory_item`
- non-recursive
- not graph-required

That means automation should stay similarly constrained.

A broad automation policy would outrun the maturity of the current hierarchy
model.

---

## Recommended automation model

The recommended current model is:

- **explicit builder first**
- **workflow-oriented orchestration second**
- **narrow auto-triggering only after explicit policy is chosen**

In practical terms, the next implementation stages should look like this:

1. preserve manual/explicit summary building as the baseline
2. define one narrow workflow-oriented orchestration boundary
3. only then decide whether a specific workflow event should trigger summary
   building automatically

---

## Recommended first workflow-oriented integration point

The most plausible first workflow-oriented automation point is:

- **after workflow completion auto-memory succeeds**

But the current direction is:

- do **not** make that automatic immediately
- first define what the automation would actually mean

### Why this is the most plausible point

The workflow-completion path already:

- creates durable episodic output
- writes canonical memory items
- has duplicate suppression
- has a meaningful “work unit completed” semantic boundary

That makes it a more coherent future automation candidate than:

- every checkpoint
- every ordinary episode write
- every memory retrieval
- generic startup-time rebuilds

### Why not enable it automatically yet

Even though workflow completion is the most plausible trigger, immediate
automatic summary generation there would force unresolved policy questions:

- which episodes should be summarized
- should only auto-memory episodes be summarized
- should all workflow episodes be summarized
- should summary building happen only on terminal workflows
- should multiple episodes be summarized together
- should low-signal closeouts still build summaries
- how should replacement behave if completion is retried or re-run

Those questions should be answered explicitly before enabling automatic workflow
triggers.

---

## Current recommendation for workflow completion integration

For the current stage, treat workflow completion as:

- the **first intended orchestration point**
- but only under a narrow gated rule set

The recommended short-term implementation reading is:

- the workflow-completion path may call the explicit builder
- but only when a concrete workflow-scoped targeting policy is satisfied
- `build-episode-summary` remains the explicit supported path outside that gated
  flow
- if the gating policy is not satisfied, workflow-completion-triggered summary
  building should be explicitly skipped rather than inferred silently

---

## Recommended first automation scope

If a workflow-oriented automation slice is added, the first scope should remain:

- one episode at a time
- one summary kind at a time
- replace-or-rebuild for matching summary kind
- explicit builder metadata preserved

That means the first workflow-oriented automation should still call something
equivalent to:

- `build_episode_summary(episode_id, summary_kind="episode_summary")`

It should **not** jump immediately to:

- workflow-wide multi-episode batch summarization
- workspace-wide summary regeneration
- recursive summary tree generation
- graph-dependent traversal-based summary construction

---

## Suggested automation policy options

The current realistic options are:

### Option A — explicit only
- summary building remains fully manual/explicit
- workflow automation does not call the builder yet

### Option B — workflow-completion assisted, gated
- after successful workflow-completion memory recording
- and only when a clear policy is satisfied
- call the explicit builder for a narrow target episode

### Option C — broad automatic episode summarization
- every episode write or every closeout path may trigger summary generation

### Current recommendation
Choose **Option B** as the next implementation slice.

Do **not** jump to Option C in `0.6.0`.

---

## Recommended gating rules for the next Option B slice

If workflow-oriented automation is added in the next follow-up slice, it should
obey this concrete rule set:

### Rule 1. Summary building remains post-write, not pre-write
The workflow-completion auto-memory episode and its canonical memory item must
already exist before summary building is attempted.

### Rule 2. The target episode is the newly created workflow-completion auto-memory episode
The first workflow-oriented automation slice should target only:

- the episode created by the current workflow-completion auto-memory path
- not arbitrary earlier workflow episodes
- not all workflow episodes
- not workspace-wide episode sets

This keeps the first trigger local, deterministic, and easy to explain.

### Rule 3. Automation runs only when workflow-completion auto-memory was actually recorded
If workflow completion does not record auto-memory, do not attempt summary
building.

This means summary automation should be skipped when:

- auto-memory gating already skipped closeout recording
- duplicate or near-duplicate suppression prevented auto-memory recording
- closeout memory recording failed before a canonical episode/memory item existed

### Rule 4. Automation is limited to `summary_kind = "episode_summary"`
The first workflow-oriented automation slice should build only:

- `episode_summary`

Different summary kinds should remain explicit manual follow-up behavior until
there is a stronger policy need.

### Rule 5. Replacement stays enabled for the targeted summary kind
The first workflow-oriented automation slice should call the explicit builder
with replacement enabled for the matching summary kind.

That keeps repeated workflow completion behavior deterministic and avoids stale
matching summary accumulation.

### Rule 6. Builder execution is gated by an explicit checkpoint/workflow signal
The first automation slice should not run for every successful completion by
default.

It should require at least one explicit signal such as:

- `latest_checkpoint.checkpoint_json["build_episode_summary"] = true`

A configuration gate may be added later, but the first implementation should
prefer an explicit per-workflow or per-checkpoint trigger.

### Rule 7. Failure must not invalidate successful workflow completion
If summary building fails, workflow completion remains successful.

Automation failure should be surfaced as additive details and/or warnings, not as
a rollback trigger for workflow completion.

### Rule 8. Skip behavior must be explicit
If the gating policy is not satisfied, return explicit summary-build details such
as:

- attempted vs not attempted
- skipped reason
- replacement flag
- built summary kind
- built membership count when successful

### Rule 9. Automation must remain observable
The completion result, logs, or operator-facing details should make it clear:

- whether summary automation was eligible
- whether it ran
- which episode it targeted
- whether it succeeded
- whether it skipped and why
- whether it failed and why

---

## Recommended failure handling

If workflow-oriented summary automation later runs and fails, the current
recommended behavior is:

- do **not** roll back an otherwise successful workflow completion
- do **not** redefine canonical episode or memory-item writes as failed
- surface summary automation failure as:
  - details metadata
  - warning(s)
  - logging
  - explicit operator-visible status where appropriate

This is consistent with the current philosophy used in other non-canonical
derived or adjunct behaviors.

### Why this matters

Summary building, even though canonical once written, is still currently a
follow-up hierarchy behavior rather than the primary operational truth of
workflow completion.

Workflow completion should therefore remain the more durable primary boundary.

---

## Relationship to current auto-memory

The current workflow-completion auto-memory path should be treated as:

- a producer of canonical episode + memory-item closeout records
- not yet a full summary-orchestration engine

### Current rule
Do not silently reinterpret the existing closeout auto-memory path as if it
already performs summary hierarchy automation.

### Future rule
If a follow-up slice connects workflow completion to summary building, document
that as an additive change with its own policy and validation.

---

## Observability requirements for future automation

If workflow-oriented summary automation is added, it should expose enough detail
to answer:

- was summary automation attempted
- what triggered it
- which episode was targeted
- what summary kind was built
- whether existing summary state was replaced
- whether the run skipped and why
- whether it failed and why

Possible metadata surfaces include:

- result details in workflow-completion outcomes
- explicit warning codes
- logs with workflow / attempt / episode / summary identifiers
- CLI-observable state through canonical summary rows

Operational clarity is more important than cleverness here.

---

## Relationship to AGE mirroring

Workflow-oriented automation should not require AGE summary mirroring.

The current recommended order remains:

1. canonical relational summary build path
2. workflow-oriented orchestration policy
3. optional later derived graph mirroring

This preserves the current system rule:

- relational data is canonical
- graph state remains supporting and derived

---

## What should remain out of scope for now

The current workflow-oriented automation direction should **not** yet include:

- automatic summary generation for every episode write
- recursive summary building on completion
- graph-required summary generation
- summary generation during ordinary retrieval
- background workers that continuously regenerate summaries
- hidden summary generation during startup
- mandatory summary generation as a release or completion precondition

Those would over-expand the current milestone.

---

## Recommended next implementation slice

The next sensible implementation slice is now concrete enough to describe as:

1. keep the explicit builder as the implementation primitive
2. target only the newly created workflow-completion auto-memory episode
3. require an explicit checkpoint/workflow signal before running
4. call the builder with:
   - `summary_kind = "episode_summary"`
   - replacement enabled
5. capture additive success/skip/failure details
6. keep workflow completion itself successful even if summary automation skips or
   fails
7. add focused tests for:
   - trigger present -> automation invoked
   - trigger absent -> automation skipped
   - auto-memory skipped -> summary automation skipped
   - builder failure -> workflow completion still succeeds with warning/details
   - repeated completion path -> replacement behavior remains deterministic

This is the smallest meaningful workflow-oriented automation slice that is now
implementation-ready at the policy level.

---

## Alternative acceptable stopping point

It is also acceptable to stop before workflow automation and keep:

- explicit CLI build
- explicit service build
- explicit replace-or-rebuild
- explicit retrieval loop

as the complete `0.6.0` summary loop, if schedule or change-size concerns argue
against another automation slice.

That would still be a legitimate and coherent milestone state.

---

## Working rules

Use these rules for future workflow-oriented summary automation work.

### Builder rule
- automation must reuse the explicit builder path

### Canonical rule
- summaries and memberships remain relationally canonical

### Trigger rule
- workflow completion is the most plausible first trigger, but not yet mandatory

### Failure rule
- summary automation failure should not invalidate otherwise successful workflow
  completion

### Scope rule
- first automation scope should remain one episode, one summary kind, one build
  path

### Observability rule
- automation should be explicit and inspectable

---

## Decision summary

The current direction for workflow-oriented summary automation is:

- preserve the explicit builder as the canonical summary-write primitive
- use workflow completion as the first intended orchestration point
- keep automation narrow and gated
- target only the newly created workflow-completion auto-memory episode
- require an explicit checkpoint/workflow signal before running
- use `summary_kind = "episode_summary"` with replacement enabled
- keep failures non-fatal to otherwise successful workflow completion
- keep graph mirroring optional and later

This is the smallest implementation-ready path from explicit summary building
toward workflow-oriented automation without prematurely overbuilding the summary
system.