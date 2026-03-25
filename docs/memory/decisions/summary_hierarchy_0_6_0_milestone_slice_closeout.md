# `0.6.0` Summary Hierarchy Milestone Slice Closeout Note

## Purpose

This note records the current closeout state for the implemented
**summary hierarchy slice** within `0.6.0`.

It is intended to answer a practical milestone question:

> Can the current summary hierarchy work be treated as a valid and coherent
> `0.6.0` milestone slice, and if so, what exactly was completed and what still
> remains deferred?

This note is not a new architecture proposal.

It is a **closeout-oriented state note** for the summary hierarchy work already
landed or explicitly deferred.

---

## Closeout status

**Current reading:** the repository now has a valid `0.6.0` summary hierarchy
milestone slice, and the implemented slice now aligns with the current
closeout-oriented validation reading for the milestone.

That slice should currently be read as:

- canonical relational summary ownership
- canonical relational summary-membership ownership
- first constrained summary-first retrieval
- direct summary-member memory-item expansion
- first explicit episode-scoped summary builder
- replace-or-rebuild semantics for matching episode summaries
- explicit CLI access for summary building
- focused service / transport / PostgreSQL integration validation
- green broad repository validation
- explicit closeout reading for the current minimal hierarchy model,
  retrieval contract boundaries, and AGE derived-state boundary

This does **not** mean `0.6.0` is globally “finished forever.”

It means the current summary hierarchy wave is now strong enough to be treated as
a coherent milestone slice rather than an incomplete experiment.

---

## What the current slice includes

## 1. Canonical relational summary model

The current slice includes canonical relational persistence for:

- `memory_summaries`
- `memory_summary_memberships`

This means summary state is now a durable first-class part of the relational
model.

The current ownership rule remains:

- relational PostgreSQL is canonical
- graph state, if added later, remains derived

## 2. First minimal hierarchy shape

The current first hierarchy shape is:

- `summary -> memory_item`

This is intentionally the smallest useful hierarchy layer.

The current slice does **not** require:

- summary-to-summary recursion
- graph-native hierarchy truth
- generic hierarchy node abstraction

## 3. First constrained summary-first retrieval path

`memory_get_context` now has a real constrained summary-first path.

Current intended behavior includes:

- prefer canonical summaries when they exist and summaries are enabled
- expand selected canonical summaries to direct member memory items
- fall back to episode-derived summary behavior when canonical summaries are absent
- keep grouped hierarchy output primary
- keep the current narrow `include_episodes = false` behavior
- preserve compatibility-oriented surfaces where needed
- keep retrieval-route explainability explicit through additive details metadata

This means the current slice already delivers a meaningful retrieval improvement,
not just storage primitives.

## 4. First explicit summary build path

The current slice includes an explicit write-side summary builder through:

- `MemoryService.build_episode_summary(...)`

and through the CLI:

- `ctxledger build-episode-summary`

This builder is currently:

- explicit
- episode-scoped
- deterministic
- relationally canonical
- replace-or-rebuild by default for matching summary kind

## 5. Replace-or-rebuild behavior

The current build path no longer merely detects prior summary state.

It can now:

- find matching prior summaries for the same episode and summary kind
- remove their memberships
- remove those summaries
- write rebuilt summary state

This closes an important practical gap between “summary creation exists” and
“summary rebuilds are operationally safe.”

## 6. Builder-to-retrieval loop validation

The current slice includes proof that:

- a builder-created canonical summary is used by summary-first retrieval
- rebuilt canonical summary state replaces the prior matching summary in retrieval
- summary-first retrieval does not keep surfacing stale matching summary state
  after rebuild

This is one of the strongest signals that the current slice is a real milestone
state rather than a partially connected prototype.

## 7. Transport-surface validation

The current slice includes validation across:

- serializer output
- MCP tool-handler output
- HTTP MCP RPC output

That means summary-first data is not only present in service-layer internals, but
also survives transport adaptation.

## 8. PostgreSQL-backed validation

The current slice includes PostgreSQL-backed validation for:

- canonical summary persistence
- canonical summary-membership persistence
- explicit summary building
- summary-first retrieval
- builder-to-retrieval integration
- replace-or-rebuild behavior in the canonical relational path

This matters because `0.6.0` should be judged against canonical PostgreSQL
behavior, not only in-memory behavior.

## 9. Operator-facing explicit build path

The current slice now has an operator/developer-visible entry point through:

- `ctxledger build-episode-summary`

And repository guidance now explains how to use it.

That makes the summary build path operationally understandable rather than
test-only.

---

## Why this counts as a valid milestone slice

The current summary hierarchy wave meets the most important closeout conditions
for a `0.6.0` slice and now reads cleanly against the current refinement
checklist for model clarity, retrieval explainability, validation coverage, and
bounded next-step framing:

### 1. It is coherent
The read path, write path, persistence path, and operator path now connect in a
meaningful way.

### 2. It is bounded
The slice is still intentionally small:

- one summary layer
- one direct child expansion layer
- no recursive hierarchy
- no graph-required summary truth

### 3. It is validated
It is not merely designed or partially implemented; it is test-backed across
focused and broader validation.

### 4. It preserves the architectural boundary
The slice still follows the current design rules:

- relational first
- graph optional
- behavior-preserving outside the target area
- explicit operational boundaries

### 5. It leaves the next step obvious
A good milestone slice should narrow the future path rather than confuse it.

The current slice does that.

---

## Current validation state

The current implemented summary hierarchy loop has been validated through:

- focused service tests
- focused context-detail tests
- focused transport-contract tests for summary-first and narrowed episode-less
  shaping
- serialization tests
- MCP transport tests
- HTTP transport tests
- PostgreSQL repository tests
- PostgreSQL integration tests
- broader full-suite validation

Current broad validation reading:

- the full repository suite is green

At this stage, the summary hierarchy slice should be treated as
**stability-confirmed enough for milestone closeout**.

The current closeout reading also means the following can now be treated as
affirmatively answered for this slice:

- the canonical summary model is documented clearly enough for `0.6.0`
- the first hierarchy shape remains intentionally:
  - `summary -> memory_item`
- the first retrieval improvement is concretely implemented as:
  - summary-first selection
  - direct summary-member memory-item expansion
- narrowed shaping behavior remains explicit for:
  - `include_summaries = false`
  - `include_episodes = false`
- transport and integration layers preserve the current summary-first contract
- broad validation is sufficient to treat the slice as closed unless a new
  follow-up deliberately broadens scope

---

## What is intentionally deferred

Treat the following as deferred work, not as evidence that the current slice is
unfinished in a problematic way.

## 1. Workflow-oriented automatic summary generation

Current explicit builder support exists.

Broad automatic workflow-driven summary generation does not.

That is deferred because it introduces policy questions such as:

- when to trigger
- which episodes to summarize
- what should happen on failure
- how much automation is appropriate in `0.6.0`

## 2. Derived AGE summary support beyond the current bounded slice

The current design direction for derived AGE summary support exists, and the
current repository already includes a narrow bounded derived-summary traversal
support path.

What remains intentionally out of scope for this closeout is any broader claim
that AGE has become canonical summary truth, a generic hierarchy engine, or a
required correctness layer for ordinary retrieval.

That broader work remains deferred because the current first summary loop already
works relationally, and any future graph expansion should still be justified by a
concrete traversal benefit rather than by architectural enthusiasm.

## 3. Recursive summary hierarchy

The current first hierarchy shape is intentionally shallow.

Recursive summary-to-summary hierarchy remains deferred.

## 4. Final long-term summary generation policy

The current builder is deterministic and explicit.

That is correct for the current slice.

More sophisticated summary generation policy is later work.

## 5. Full summary automation platform behavior

The repository does not yet have:

- background summary workers
- broad rebuild daemons
- automatic summary generation on every episode write
- graph-required summary generation

Those are all intentionally out of scope for this slice.

---

## What should be considered done for this slice

For practical planning purposes, the following should be considered **done** for
the current summary hierarchy slice:

- canonical summary persistence
- canonical summary-membership persistence
- summary-first retrieval
- explicit summary build path
- replace-or-rebuild behavior
- operator-facing explicit build command
- builder-to-retrieval loop
- serializer / MCP / HTTP validation
- PostgreSQL-backed integration coverage
- closeout-level docs and changelog visibility

That is enough to say:

- the first summary hierarchy loop is implemented
- the first summary hierarchy loop is validated
- the first summary hierarchy loop is a valid `0.6.0` milestone slice

---

## Recommended milestone reading

The best current reading is:

> `0.6.0` now includes a valid first canonical summary hierarchy slice, centered
> on relationally owned summaries, explicit summary building, summary-first
> retrieval, and tested replace-or-rebuild behavior, while keeping workflow
> automation and graph mirroring intentionally deferred.

That is the clearest and most accurate milestone-level statement.

---

## Next-step candidate notes

The current slice does not force one immediate implementation path, but it does
make the next sensible options much clearer.

## Candidate 1 — workflow-scoped summary automation targeting policy

Recommended note topic:

- define how workflow-oriented automation would choose the target episode for a
  future gated summary-build hook

This should answer questions such as:

- should workflow completion target only the auto-memory episode
- should it target the latest episode
- should it target only certain summary kinds
- should it be gated by checkpoint payload or configuration
- what should be reported on skip/failure

This is the most natural next policy note if automation is revisited.

## Candidate 2 — optional derived AGE summary mirroring trigger and refresh policy

Recommended note topic:

- define when and how canonical summaries would be mirrored into AGE if graph
  mirroring later becomes justified

This should answer questions such as:

- what trigger owns refresh
- whether refresh is explicit or rebuild-first
- what readiness means
- what the fallback rules are
- what concrete traversal path justifies the mirroring

This is the most natural next graph-oriented note if the repository wants to
move beyond pure relational summary traversal.

## Candidate 3 — operator-facing summary build runbook expansion

The explicit runbook can still be expanded if the command is expected to be used
regularly.

Possible follow-up scope:

- common verification workflow
- example inspect/rebuild cycle
- replacement troubleshooting
- expected retrieval confirmation steps

This is useful if operational repeat use becomes common.

## Candidate 4 — summary build boundary extraction note

Although the builder boundary has already improved, a future refinement note
could still decide whether:

- summary build should remain a `MemoryService` concern
- or move into a narrower dedicated summary-build service module

This is a structural refinement candidate, not an urgent architecture need.

## Candidate 5 — release-facing status note for `0.6.0`

If a more externally oriented release or roadmap note is desired, it could
summarize:

- what the current slice implemented
- what remains intentionally deferred
- what `0.7.0` might evaluate later

This is optional, but can be useful for milestone communication.

---

## Suggested priority among next-step candidates

Given the current implemented state, the most reasonable next-step priority is:

1. workflow-scoped summary automation targeting policy
2. optional derived AGE summary mirroring trigger/refresh policy
3. operator-facing summary build runbook expansion
4. boundary extraction refinement only if it clearly improves maintainability
5. release-facing status note if needed for communication

This order preserves the current milestone boundaries while keeping future work
clear and incremental.

---

## Final closeout reading

The current summary hierarchy work should now be treated as:

- a valid `0.6.0` milestone slice
- implemented
- validated
- documented
- operationally understandable
- still intentionally bounded

The repository does **not** need to reopen foundational summary hierarchy
questions before moving on.

The correct next work is no longer:

- “can summaries exist canonically?”

It is now:

- “if we extend this loop, which bounded follow-up do we choose next?”