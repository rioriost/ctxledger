# Phase E Summary Hierarchy Refinement Checklist for `0.6.0`

## Purpose

This note defines the **Phase E refinement checklist** for the current
`0.6.0` summary hierarchy work.

It is intended to help close out the first summary hierarchy wave in a way that
is:

- explicit
- reviewable
- testable
- operationally understandable
- consistent with the canonical relational-first design
- realistic about what is already done versus what still needs confirmation

This checklist is not a new architecture proposal.

It is a closeout-oriented refinement note for the current implemented slices.

---

## Current scope being refined

The current summary hierarchy work already includes:

- canonical `memory_summaries`
- canonical `memory_summary_memberships`
- summary-first retrieval through `memory_get_context`
- explicit episode-scoped summary building
- replace-or-rebuild semantics for matching summary kinds
- CLI access through:
  - `ctxledger build-episode-summary`
- transport-surface coverage through:
  - serializer
  - MCP
  - HTTP
- PostgreSQL-backed builder-to-retrieval integration coverage

Phase E refinement is about confirming that this first loop is:

- stable
- understandable
- sufficiently documented
- sufficiently validated
- appropriately bounded

---

## Phase E closeout intent

Before treating the current summary hierarchy wave as a solid `0.6.0` slice,
the repository should be able to answer "yes" to most or all of these:

1. Is the canonical summary model clearly documented?
2. Is the summary build path explicit and operator-visible?
3. Is retrieval behavior explainable and test-backed?
4. Does the PostgreSQL-backed path behave consistently with the in-memory path?
5. Are current limitations explicit rather than implicit?
6. Are failure and degradation expectations understandable?
7. Is the remaining next work obvious without reopening already-settled
   boundaries?

This checklist is organized around those questions.

---

## 1. Canonical model confirmation

### 1.1 Summary ownership
Confirm that the current implementation and docs consistently reflect:

- `memory_summaries` are canonical relational records
- `memory_summary_memberships` are canonical relational records
- AGE summary mirroring, if later added, remains derived and optional
- summary membership is not treated as generic `memory_relations`

### 1.2 Scope of the current hierarchy model
Confirm that docs and code still align on the current first hierarchy shape:

- `summary -> memory_item`

And that the following remain intentionally deferred:

- summary-to-summary recursion
- graph-native hierarchy truth
- generic hierarchy node abstraction

### 1.3 Summary kinds
Confirm that current summary-kind semantics remain narrow and explicit.

Questions to verify:

- Is `episode_summary` the current primary supported kind?
- Are any other summary kinds present in code or docs?
- If multiple kinds are possible, are their expectations documented clearly
  enough?

---

## 2. Explicit build path confirmation

### 2.1 Builder entry points
Confirm that the current explicit build path is visible and coherent across:

- service layer
- CLI
- docs

Current expected explicit build path:

- `MemoryService.build_episode_summary(...)`
- `ctxledger build-episode-summary`

### 2.2 Replace-or-rebuild semantics
Confirm that the current behavior is still clearly defined as:

- replace or rebuild matching summary kinds for the selected episode when
  replacement is enabled

Questions to verify:

- Is replacement behavior consistent between in-memory and PostgreSQL-backed
  paths?
- Do tests cover stale-summary removal sufficiently?
- Is the non-replacement path either covered or explicitly deferred?

### 2.3 Deterministic build behavior
Confirm that the current first builder remains:

- deterministic
- explainable
- based on canonical episode + memory items
- not graph-required
- not LLM-required

If that changes later, it should be treated as a separate design step.

---

## 3. Retrieval contract refinement

### 3.1 Summary-first selection
Confirm that retrieval still behaves as currently intended:

- canonical summaries are preferred when present and summaries are enabled
- fallback remains the episode-derived summary path when canonical summaries are
  absent
- `summary_selection_kind` is explicit and test-backed

Expected current values include:

- `memory_summary_first`
- `episode_summary_first`

### 3.2 Narrow suppression behavior
Confirm that the current constrained suppression rules still hold:

- `include_summaries = false`
  - suppresses canonical summary-first selection
- `include_episodes = false`
  - preserves the narrow episode-less path
  - does not newly surface canonical summary-first grouped output there

These rules are easy to regress accidentally, so they should remain explicit.

### 3.3 Grouped output reading
Confirm that the current grouped-primary interpretation still reads cleanly:

- `memory_context_groups` is the primary grouped hierarchy-aware surface
- summary-scoped grouped output remains understandable
- compatibility fields still behave consistently
- summary-first grouped output stays explainable without broad redesign

### 3.4 Retrieval loop after rebuild
Confirm that replace-or-rebuild behavior is reflected in retrieval:

- rebuilt summaries appear
- replaced summaries no longer appear as current canonical summaries
- retrieval does not accidentally surface stale matching summaries after rebuild

---

## 4. Validation checklist

### 4.1 Focused service validation
Confirm focused coverage exists for:

- canonical summary-first selection
- fallback to episode-derived summaries
- suppression under `include_summaries = false`
- preservation of narrow `include_episodes = false` shaping
- multiple summary ordering
- membership ordering
- empty-membership summaries
- builder success
- builder skip behavior
- builder replace-or-rebuild behavior
- builder-to-retrieval loop behavior

### 4.2 Transport validation
Confirm coverage exists for:

- serializer output
- MCP memory tool handler output
- HTTP MCP RPC output

The goal is to ensure that summary-first payloads survive transport adaptation.

### 4.3 PostgreSQL integration validation
Confirm coverage exists for:

- PostgreSQL-backed summary retrieval
- PostgreSQL-backed summary building
- PostgreSQL-backed builder-to-retrieval loop
- PostgreSQL-backed replacement behavior in retrieval

### 4.4 Full-suite validation
Confirm that the broader repository suite has been rerun after the latest summary
hierarchy slices and remains green.

The practical closeout expectation is:

- current focused suites are green
- current full suite is green

---

## 5. Workflow-oriented automation refinement

### 5.1 Current posture
Confirm that workflow-oriented summary automation is still correctly understood
as:

- considered
- bounded
- not yet broadly automatic

The current explicit builder should remain the primary write primitive unless a
later follow-up intentionally changes that.

### 5.2 Current next decision point
The current implemented and design-reviewed direction is:

- workflow completion remains the most plausible first orchestration point
- but broad automatic summary building should still be deferred
- the current explicit CLI/service build path is sufficient for the present
  `0.6.0` summary loop

Questions that still remain worth tracking for a later slice:

- if workflow completion begins invoking summary building, should that behavior
  be:
  - always-on
  - gated
  - operator-controlled
  - configuration-controlled
- should the first automation target only workflow-completion auto-memory
  episodes, or a broader episode set
- what additive success/skip/failure details should be surfaced when automation
  is attempted

### 5.3 Failure posture
If workflow-oriented automation is added later, confirm that the intended current
direction remains:

- summary automation failure should not invalidate otherwise successful workflow
  completion
- automation details should be surfaced explicitly

---

## 6. Optional AGE summary mirroring refinement

### 6.1 Canonical boundary
Confirm that docs still clearly distinguish:

- relational summary truth
- optional derived graph mirroring

The current reviewed direction should be treated as:

- summary mirroring remains deferred
- relational summary build/retrieval is already sufficient for the first
  implemented summary loop
- graph mirroring should not be added merely because AGE support exists in the
  repository

### 6.2 Minimum mirrored shape
If summary mirroring is revisited later, confirm that the current smallest
acceptable shape remains:

- `memory_summary`
- `memory_item`
- `summarizes`

And that broader graph expansion remains deferred.

### 6.3 Justification threshold
Confirm that the repository still requires a concrete traversal benefit before
adding summary mirroring.

That means summary mirroring should not be introduced merely because graph
support exists in principle.

At the current stage, the practical answer should be read as:

- no such concrete traversal benefit is yet strong enough to justify
  implementation
- therefore summary mirroring remains a design-ready but intentionally deferred
  follow-up

---

## 7. Operator-facing refinement

### 7.1 README visibility
Confirm that README guidance is sufficient for the current explicit build path:

- command exists in command listings
- minimal usage example exists
- replace behavior is explained at least briefly

### 7.2 CLI output quality
Confirm that the CLI build command returns usable operator-facing output for:

- build success
- skip/no-op
- replacement behavior
- JSON automation-friendly use

### 7.3 Need for a dedicated runbook
Decide whether the current state now justifies a small operator note or runbook
for summary building, especially if the path is expected to be used repeatedly.

Possible trigger conditions:

- repeated manual use in development/test
- debugging canonical summary retrieval
- repeated rebuilds after episode edits
- preparing a later workflow-oriented automation slice

---

## 8. Remaining technical cleanup candidates

These are not necessarily required for Phase E closeout, but they are valid
cleanup candidates to evaluate.

### 8.1 Builder boundary cleanup
Potential refinement:

- move summary build orchestration into a narrower dedicated service/helper
  boundary if the current `MemoryService` ownership feels too broad

### 8.2 Result/metadata polish
Potential refinement:

- tighten or normalize builder result metadata
- make replacement details more explicit
- improve consistency between text and JSON output surfaces

### 8.3 Documentation consistency
Potential refinement:

- ensure README, changelog, plan notes, and design notes all use the same
  current-state language for:
  - summary ownership
  - summary-first retrieval
  - explicit build path
  - replacement semantics

---

## 9. Closeout criteria

The current summary hierarchy slice is in good Phase E shape if:

- the canonical relational model is clear
- explicit build and retrieval paths are both present
- replacement behavior is tested
- transport surfaces preserve summary-first data
- PostgreSQL-backed behavior is validated
- full-suite validation is green
- current non-goals are clearly stated
- the next follow-up work can proceed without reopening foundational decisions

---

## 10. Non-goals of this checklist

This checklist does **not** require:

- summary-to-summary recursion
- graph-native summary truth
- automatic summary generation for every episode
- broad retrieval redesign
- final long-term summary ranking policy
- full workflow-summary automation rollout
- immediate AGE summary mirroring
- Mnemis alignment work

Those remain later concerns.

---

## 11. Recommended next actions after checklist review

If this checklist is reviewed and the current slice is considered sufficiently
stable, the next realistic action choices are:

1. continue with workflow-oriented automation only as a narrow, gated follow-up
   built on top of the explicit builder
2. add a small operator runbook for summary building if repeated manual use is
   expected
3. keep optional derived AGE summary mirroring deferred unless a concrete
   traversal benefit becomes strong enough to justify implementation
4. stop the current summary hierarchy work loop for now and treat the explicit
   build/retrieval loop as a valid `0.6.0` milestone slice until a later
   automation or graph follow-up is intentionally chosen

---

## Summary

Phase E for the current summary hierarchy work is mainly about confirming that
the first explicit summary loop is:

- canonical
- explicit
- validated
- explainable
- operator-visible
- safe to build on

The current repository is already far along that path.

This checklist exists to make the remaining refinement work explicit and
reviewable rather than leaving closeout quality to implication.