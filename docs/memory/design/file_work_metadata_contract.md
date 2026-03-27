# File-Work Metadata Contract

## Purpose

This note defines the bounded current contract direction for **file-work metadata**
in `ctxledger`.

File-work metadata means durable records about **why** a file was touched during
AI-assisted work, without requiring `ctxledger` to index the contents of
Git-managed files themselves.

The goal is to make file-touching work:

- durable across sessions
- queryable later
- reusable for resumability
- reusable for bounded historical progress recall
- reusable for failure-pattern avoidance

This contract is intentionally bounded.
It does **not** define a full source-code indexing system, a repository-wide code
search engine, or a content archive for Git-managed files.

It defines the minimum durable file-work metadata behavior needed for the
`0.9.0` product direction.

---

## Why file-work metadata exists

`ctxledger` already stores meaningful durable state for:

- workflows
- attempts
- checkpoints
- verify reports
- episodes
- memory items
- summaries
- bounded search and retrieval

That is enough to preserve a large amount of process history.

But normal software work also depends on a narrower practical question:

- which file was touched?
- was it created or modified?
- why was it touched?
- what task, checkpoint, failure, or user request did that file work belong to?

Without durable file-work metadata, the repository loses an important part of the
operational trail.

That weakens:

- `resume`
- `continue`
- bounded historical progress questions
- failure and recovery reuse
- explanation of why a particular file was involved in the work

File-work metadata therefore exists to close the gap between:

- durable workflow state
- durable memory state
- concrete file-touching development activity

---

## Contract posture

File-work metadata should be read using these boundaries:

- canonical workflow and checkpoint truth remain primary
- file-work metadata is durable and important, but it does **not** become a
  competing workflow-truth system
- file-work metadata should support retrieval, recall, and explanation
- file-work metadata may participate in vector-oriented search when represented
  through durable memory items
- file-work metadata may participate in bounded graph-linking or relation-writing
  where useful
- file-work metadata should remain explicitly bounded and explainable

This means:

- file-work metadata can support resumability
- file-work metadata can support bounded historical lookup
- file-work metadata can support failure-pattern avoidance
- file-work metadata should not silently redefine canonical workflow state

---

## What counts as file-work metadata

At the current intended boundary, file-work metadata includes durable records of
file-touching work such as:

### File identity

Examples:

- file name
- file path
- normalized repository-relative path where available

### File-work intent

Examples:

- create a file
- modify a file
- update a file
- rename intent if it is explicitly surfaced in durable metadata
- delete intent if it is explicitly surfaced in durable metadata

### File-work purpose

Examples:

- add acceptance test coverage
- refine resume behavior
- update docs for bounded historical recall
- fix a repeated failure pattern
- add operator-facing observability support

### File-work context

Examples:

- related workspace
- related workflow
- related attempt
- related checkpoint
- related ticket
- related user request
- related agent response
- related failure or recovery context

---

## What does not count as file-work metadata

File-work metadata should **not** be read as:

- raw indexing of all Git-managed file contents
- a replacement for source control
- a complete repository-wide code intelligence layer
- a second canonical workflow-status system
- a promise that every file operation in every tool is automatically captured in
  perfect detail
- an unconstrained audit log for every local filesystem event

The bounded contract is about **durable metadata about file-touching work**, not
full content indexing or universal filesystem telemetry.

---

## Core product roles of file-work metadata

File-work metadata exists to support five bounded product roles.

## 1. Resumability support

File-work metadata should help recover:

- which file was being worked on
- whether the work was creation-oriented or modification-oriented
- what purpose the file work served
- which checkpoint or workflow context the file work belonged to

This is useful when a user says:

- `resume`
- `continue`
- `作業を再開`

and the system needs to surface not only the workflow identity, but also the
concrete file-work thread.

## 2. Historical progress recall

File-work metadata should help answer bounded questions such as:

- what file did we edit yesterday for this task?
- which files were touched for this keyword?
- where did we stop in the file work?
- what remains for this file-related task?

## 3. Failure-pattern avoidance

File-work metadata should help surface:

- which file was involved in a prior failure
- why that file was touched at the time
- which file-related change pattern caused trouble
- which recovery path later succeeded for that file or file group

## 4. Interaction-memory enrichment

File-work metadata should help preserve the bridge between:

- what the user asked to change
- what the agent said it would change
- what file-touching work actually became part of durable memory

## 5. Explanation quality

File-work metadata should make it easier to explain:

- why a file appears in historical recall
- how a file was linked to a workflow or checkpoint
- whether the file-work record came from user intent, agent intent, checkpoint
  material, or later durable memory shaping

---

## Canonical boundary

File-work metadata should always be interpreted relative to canonical workflow
truth.

### Canonical first

Canonical truth remains:

- workspaces
- workflow instances
- attempts
- checkpoints
- verify reports
- canonical summary rows
- canonical summary-membership rows
- structured failure rows where applicable

### Derived or supportive file-work reading

File-work metadata should be read as:

- durable
- queryable
- retrieval-relevant
- explanation-relevant
- resumability-relevant

but still subordinate to canonical workflow truth for questions like:

- which workflow is actually active
- what checkpoint was actually recorded
- what verify status was actually persisted

If file-work metadata and canonical workflow state disagree, the canonical
workflow system-of-record wins.

---

## Minimum durable record shape

Each file-work metadata record should preserve, at minimum, enough information to
answer:

- which file was involved
- what kind of file-touching intent was present
- why the file was touched
- how it relates to workflow or checkpoint context
- whether it is useful for later search and retrieval

A bounded minimum record should support fields equivalent to:

- `file_work_metadata_id`
- `file_name`
- `file_path`
- `path_kind`
  - `repo_relative`
  - `workspace_relative`
  - `canonical_or_unknown`
- `operation_kind`
  - `create`
  - `modify`
- `purpose`
- `created_at`
- optional `workspace_id`
- optional `workflow_instance_id`
- optional `attempt_id`
- optional `checkpoint_id`
- optional `ticket_id`
- optional structured metadata

The exact storage model may evolve, but the durable contract should preserve that
minimum reading.

---

## Minimum schema guidance for `0.9.0`

At the bounded `0.9.0` slice, the repository should preserve the ability to
capture at least:

- `file_name`
- `file_path`
- `operation_kind`
  - especially `create` and `modify`
- `purpose`
- relationship to:
  - `workflow_instance_id`
  - `attempt_id` where relevant
  - `checkpoint_id` where relevant

This is the minimum useful schema for the milestone.
Anything broader should remain explicitly bounded and documented.

---

## Required metadata themes

The current bounded contract should preserve the ability to attach metadata such
as:

- user-request origin
- agent-response origin
- checkpoint-derived origin
- failure-context origin
- recovery-context origin
- topic or keyword hints
- repository-relative path normalization state
- multiple touched paths where one durable memory item summarizes a bounded file
  group
- whether the file work was mainline-like or detour-like where that distinction
  materially affects resumability

The exact metadata keys may evolve, but the durable meaning should stay stable.

---

## Storage posture

The bounded current contract does **not** require a dedicated standalone storage
subsystem for file-work metadata if the repository can preserve the same durable
meaning through the existing memory substrate.

That means file-work metadata may be represented through durable memory items,
episodes, summaries, or related derived structures as long as the contract still
supports:

- durable capture
- later retrieval
- explicit file identity
- explicit operation kind
- explicit purpose
- workflow/checkpoint linkage where relevant

The implementation may therefore evolve without breaking the contract, as long as
the reading remains stable.

---

## Retrieval posture

File-work metadata should be retrieval-ready, not merely stored.

At the bounded intended boundary, it should be possible to surface file-work
metadata through representative paths such as:

- workspace-scoped retrieval
- workflow-scoped retrieval
- checkpoint-adjacent retrieval
- keyword-oriented memory search
- bounded historical progress lookup
- failure-oriented lookup when file context matters

The retrieval path should remain explainable.
A caller should be able to understand why a file-work record appeared in the
answer.

---

## Relationship to interaction memory

File-work metadata and interaction memory are distinct but complementary.

Interaction memory preserves:

- what the user asked for
- what the agent answered
- how intent and interpretation evolved

File-work metadata preserves:

- which file was touched
- what operation kind applied
- why the file was touched
- how that file work related to workflow and checkpoint context

A strong bounded `0.9.0` implementation should make it possible to connect these
layers when useful, for example:

- user asks to update `README.md`
- agent confirms it will revise release documentation
- file-work metadata records a `modify` intent for `README.md`
- checkpoint and historical recall can later explain that linkage

---

## Relationship to failure reuse

File-work metadata should contribute to failure reuse when file context matters.

Examples:

- a prior failure happened while modifying a migration file
- a user corrected the agent about changing the wrong file
- a recovery succeeded after switching from one file to another
- a repeated bad pattern can be recognized because the same file-purpose pair
  already failed before

This does not require file-content indexing.
It requires durable linkage between file identity, purpose, and failure/recovery
context.

---

## Historical progress reading

When file-work metadata contributes to a historical progress answer, the intended
reading should be:

1. start from canonical workflow and checkpoint state
2. enrich with durable file-work metadata where the question is file-anchored or
   where file context improves the answer
3. preserve an explanation of:
   - why the file-work record matched
   - what workflow/checkpoint context it belongs to
   - whether the file-work signal came from interaction memory, checkpoint
     capture, or another durable memory path

This keeps historical recall useful without overstating what the system knows.

---

## Explicit out-of-scope boundary for `0.9.0`

The following remain out of scope for the bounded `0.9.0` milestone unless later
docs explicitly widen the contract:

- indexing the contents of all Git-managed files as memory-search inputs
- repository-wide semantic understanding of arbitrary source code contents
- full diff archival as memory truth
- unconstrained filesystem telemetry
- automatic universal capture of every local file change outside the bounded
  `ctxledger` operating path

This boundary is important.
`0.9.0` should preserve useful file-work metadata without silently turning into a
file-content indexing system.

---

## Expected implementation direction for `0.9.0`

A bounded `0.9.0` implementation should move toward all of the following:

- file-work metadata can be stored durably through the existing memory substrate
- file-work metadata distinguishes at least `create` versus `modify`
- file-work metadata preserves purpose, not only path text
- file-work metadata can be linked to workflow/checkpoint context
- file-work metadata can support:
  - resumability
  - bounded historical recall
  - failure reuse
- docs and tests make the bounded scope explicit
- Git-managed file contents themselves remain outside the required memory-search
  surface

---

## Validation expectations

The bounded validation frame should cover representative cases for:

- durable capture of file name and file path
- durable capture of `create` versus `modify`
- durable capture of purpose
- linkage to workflow/checkpoint context
- retrieval through bounded search or historical lookup
- use in failure-oriented retrieval or explanation where relevant
- explicit preservation of the non-goal that Git-managed file contents are not
  required memory-search targets

Focused tests are more important than broad speculative coverage.

---

## Expected client reading

Clients should be able to read file-work metadata as:

- durable operational memory about file-touching work
- subordinate to canonical workflow truth
- useful for resume and historical recall
- useful for failure-pattern avoidance
- explicitly bounded away from full file-content indexing

That is the intended `0.9.0` contract.

---

## Summary

For `0.9.0`, file-work metadata should mean:

- durable records of which file was touched
- explicit `create` / `modify` style intent
- explicit purpose for the file work
- bounded linkage to workflow, checkpoint, interaction, and failure context
- retrieval-ready support for resumability, historical recall, and failure reuse

It should **not** mean:

- indexing Git-managed file contents
- replacing source control
- creating a second workflow truth system
- implying unconstrained code-understanding over the entire repository