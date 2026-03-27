# Episode-Less Summary-First Behavior Choice Decision

> Historical design record: this document captures a bounded `0.6.0` decision state.
> Read it as first-slice decision history, not as the authoritative current
> `0.9.0` release contract. For current release-facing behavior, prefer the
> product, runbook, and release acceptance/closeout docs.

## Context

Recent `0.6.0` work around `memory_get_context` has already clarified the current grouped retrieval model substantially.

The current state now has a relatively stable reading for:

- summary-first primary grouped shaping
- auxiliary-only no-match shaping
- episode-less `include_episodes = false` shaping
- grouped ordering
- primary vs auxiliary retrieval-route metadata
- the distinction between canonical grouped output and flatter compatibility or convenience views

In that current reading:

- `memory_context_groups` is treated as the primary hierarchy-aware grouped surface
- summary-first is an important current primary grouped selection route
- auxiliary grouped surfaces remain top-level siblings
- relation-aware behavior remains intentionally constrained
- episode-less shaping is intentionally narrower than episode-oriented shaping

That means there is now a real design question about whether the current episode-less path should remain strictly narrower, or whether it should begin surfacing a limited summary-first grouped view.

## Current behavior

At the current stage, when:

- `include_episodes = false`

the response takes a narrower episode-less shaping path.

In that shape, the response does **not** currently surface:

- summary-first grouped output
- direct episode-scoped grouped output
- summary-selection metadata such as:
  - `summary_selection_applied`
  - `summary_selection_kind`
- other episode-oriented explanation fields tied to the hidden primary path

Instead, the response should currently be read from the grouped routes and top-level details fields that are actually emitted for that shape.

This current reading is now covered in tests and aligned in the docs.

## Decision question

Should the current episode-less path remain fully narrow, or should it begin to surface a limited summary-first grouped view?

More specifically:

- when `include_episodes = false`
- and summaries are enabled
- and a query is present or some visible episode-set would otherwise exist under episode-oriented shaping

should the response begin to expose a summary-scoped grouped entry such as a summary-first marker, while still withholding episode-scoped grouped output?

## Option A: keep the current episode-less path narrow

### Description

Keep the current behavior unchanged.

When `include_episodes = false`:

- do not surface summary-first grouped output
- do not surface direct episode-scoped grouped output
- do not surface summary-selection metadata
- do not surface episode-oriented explanation fields in inactive placeholder form
- continue to read the response from the grouped routes and details that are actually emitted

### Benefits

- preserves the now-stable current contract
- keeps episode-less shaping easy to reason about
- avoids hidden-primary-path confusion
- avoids creating a new partial middle shape between:
  - full episode-oriented shaping
  - summary-only primary shaping
  - fully episode-less shaping
- minimizes ripple effects across tests and docs

### Costs

- episode-less responses remain less expressive for grouped consumers
- summary-oriented consumers do not get a grouped primary-chain hint in that shape
- grouped-primary-surface consistency is somewhat weaker in episode-less mode

## Option B: add limited summary-first grouped surfacing in episode-less mode

### Description

Introduce a new intermediate shape for some episode-less responses.

For example, when:

- `include_episodes = false`
- `include_summaries = true`
- and some summary-first reading would otherwise be visible under episode-oriented shaping

the response could surface:

- a summary-scoped grouped entry
- possibly limited summary-selection metadata

while still not surfacing:

- episode-scoped grouped entries
- direct episode memory-item groups

### Potential benefits

- strengthens the role of grouped output as the primary hierarchy-aware surface
- gives grouped consumers a visible primary-chain hint even in episode-less mode
- may make summary-oriented retrieval feel more consistent across shaping modes

### Potential costs

- introduces a new partial shape that is harder to explain
- reopens recently clarified contract boundaries
- blurs the current distinction between:
  - summary-only primary shaping
  - episode-less shaping
- requires rethinking which top-level details fields should be:
  - absent
  - false
  - partially surfaced
- increases test and documentation maintenance burden

## Decision

At the current `0.6.0` stage, the chosen direction is:

- **Option A**
- keep the current narrow episode-less path

In other words:

- retain the current narrow episode-less path
- do not introduce summary-first grouped surfacing there in the current `0.6.0` contract

## Why Option B is deferred

### 1. The current contract was only recently stabilized

The current episode-less reading is now covered well enough across tests and docs.

Changing it immediately would reopen the exact interpretation area that was just clarified.

### 2. This is a real behavior change, not a small wording improvement

If introduced, this change would alter:

- grouped output shape
- summary-selection visibility
- route interpretation
- details-field expectations

That makes it a legitimate next behavior choice, but not a low-cost continuation of the recent consolidation work.

### 3. The current distinction remains valuable

The current model draws a clean line between:

- episode-oriented shaping
- summary-only primary shaping
- auxiliary-only no-match shaping
- episode-less shaping

That clarity is currently more valuable than a slightly more expressive episode-less grouped surface.

## Working rule for now

Until a later behavior slice explicitly chooses otherwise:

- `include_episodes = false` should continue to suppress visible summary-first grouped output
- episode-less responses should continue to be read only from grouped routes and details that are actually emitted
- episode-oriented explanation fields should not be inferred from hidden primary-path state

## What would justify revisiting this later

This decision should be revisited only if one of these becomes clearly important:

1. grouped consumers need a summary-first primary-chain signal in episode-less mode to remain usable
2. product requirements begin treating summary-oriented recall as valuable even when episode-level visibility is suppressed
3. a broader grouped-selection redesign makes the current episode-less suppression model less coherent than a limited summary-first surface
4. a later hierarchy or graph-backed phase makes the current distinction unnecessarily restrictive

## Non-goals of this note

This decision note does **not**:

- change current implementation behavior
- add new response fields
- broaden relation traversal
- change auxiliary-group positioning
- introduce graph-first semantics
- redesign grouped output structure
- decide any AGE behavior

It only records the current choice point and the present recommendation.

## Decision summary

The next meaningful behavior question is whether episode-less shaping should begin surfacing a limited summary-first grouped view.

For the current `0.6.0` stage, the answer is:

- **Option A**

The current narrow episode-less contract should remain in place unless a later stage produces a clearer product or retrieval-semantics reason to introduce that intermediate shape.