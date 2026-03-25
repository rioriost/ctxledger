# Summary Build Runbook for Explicit Episode Summary Building

## Purpose

This runbook explains how to use the current explicit summary build path for
`ctxledger` hierarchical memory work in `0.6.0`.

It is intended for operators and developers who need to:

- build one canonical summary for a selected episode
- rebuild an existing summary after the source memory items changed
- verify what the summary builder wrote
- understand what current success, skip, and replacement behavior means

This runbook covers the current explicit command:

- `ctxledger build-episode-summary`

It does **not** describe automatic workflow-driven summary generation.
The current `0.6.0` path is still explicit and operator-invoked.

---

## Current behavior at a glance

The current explicit summary build path is:

- canonical-relational first
- episode-scoped
- deterministic
- replace-or-rebuild by default
- independent from ordinary retrieval execution
- independent from broad graph requirements

In practical terms, the command currently:

1. reads one canonical episode
2. reads that episode's canonical memory items
3. builds one summary text
4. writes one canonical `memory_summaries` row
5. writes canonical `memory_summary_memberships` rows
6. replaces existing summaries of the same `summary_kind` by default

The current default summary kind is:

- `episode_summary`

---

## Preconditions

Before using the command, confirm the following:

### 1. The database is reachable

You need a working PostgreSQL connection through:

- `CTXLEDGER_DATABASE_URL`

or a runtime configuration path that supplies the same value.

### 2. Canonical schema is already applied

The summary builder depends on the canonical PostgreSQL schema.

If needed, apply it first:

```/dev/null/sh#L1-1
ctxledger apply-schema
```

### 3. The target episode already exists

The builder does **not** create episodes.
It only builds summaries for an existing `episode_id`.

### 4. The target episode has child memory items

The builder currently summarizes an episode from that episode's existing memory
items.

If the episode has no child memory items, the builder will skip instead of
creating an empty summary.

---

## Command reference

## Basic command

```/dev/null/sh#L1-1
ctxledger build-episode-summary --episode-id <episode-uuid>
```

## Optional arguments

### `--summary-kind`

Override the summary kind.

Current default:

- `episode_summary`

Example:

```/dev/null/sh#L1-1
ctxledger build-episode-summary --episode-id <episode-uuid> --summary-kind episode_summary
```

### `--no-replace-existing`

Keep existing summaries of the same kind instead of replacing them.

By default, the builder uses replace-or-rebuild behavior for the selected
summary kind.

Example:

```/dev/null/sh#L1-1
ctxledger build-episode-summary --episode-id <episode-uuid> --no-replace-existing
```

### `--format json`

Emit machine-readable output.

Example:

```/dev/null/sh#L1-1
ctxledger build-episode-summary --episode-id <episode-uuid> --format json
```

---

## Recommended operator workflow

## Step 1 — Identify the target episode

You need the canonical `episode_id`.

Typical sources include:

- prior workflow or memory inspection
- direct database inspection
- application responses that already expose episode identifiers

If you do not know the episode id yet, find it first through your normal
workflow/memory inspection path.

## Step 2 — Run the builder

Recommended first invocation:

```/dev/null/sh#L1-1
ctxledger build-episode-summary --episode-id <episode-uuid> --format json
```

JSON output is easier to inspect and easier to compare across repeated rebuilds.

## Step 3 — Inspect the result

Focus on these output fields:

- `summary_built`
- `status`
- `skipped_reason`
- `replaced_existing_summary`
- `summary`
- `memberships`
- `details.member_memory_count`

## Step 4 — Inspect the written summary state directly

After a successful build, inspect the returned payload and confirm:

- `summary.memory_summary_id` is present
- `summary.episode_id` matches the target episode
- `summary.summary_kind` matches the requested kind
- `memberships` is not empty when a real summary was built
- `details.member_memory_count` matches the intended child memory set

For repeat runs, also confirm:

- `replaced_existing_summary = true` when a rebuild replaced a matching prior
  summary
- `replaced_existing_summary = false` when the run created a first summary or
  when non-replacement behavior was requested

## Step 5 — Verify retrieval sees the summary

After a successful build, the current expectation is that the canonical summary
may be preferred by `memory_get_context` when summaries are enabled.

Use your normal retrieval path and confirm that the response reflects:

- `summary_selection_applied = true`
- `summary_selection_kind = "memory_summary_first"`

where applicable for the target workflow/episode context.

Also confirm, where relevant:

- the returned `summaries` payload references the expected canonical
  `memory_summary_id`
- the grouped summary output remains present in `memory_context_groups`
- rebuilt summary content is now visible instead of older matching summary state

---

## Output interpretation

## Success

A successful build typically looks like:

- `status = "built"`
- `summary_built = true`
- `skipped_reason = null`
- `summary != null`

Interpretation:

- one canonical summary row was written
- summary memberships were written
- the summary is now eligible for summary-first retrieval

## Skipped

A skipped build typically looks like:

- `status = "skipped"`
- `summary_built = false`
- `summary = null`
- `skipped_reason != null`

Current important skip reason:

- `no_episode_memory_items`

Interpretation:

- the episode exists
- but there was nothing meaningful to summarize under the current first-slice
  rules

## Replacement happened

A replacement/rebuild result typically shows:

- `replaced_existing_summary = true`

Interpretation:

- matching prior summaries of the same `summary_kind` for that episode were
  replaced
- current retrieval should now reflect the rebuilt canonical summary rather than
  the prior matching one

## No replacement happened

This usually means one of:

- no matching summary previously existed
- `--no-replace-existing` was used

---

## Current summary text behavior

The current `0.6.0` builder is intentionally simple and deterministic.

It currently derives summary text from:

- the episode summary text
- the episode's child memory-item contents

This is a first-slice behavior.
It is designed for:

- explicitness
- reproducibility
- easy testing
- easy inspection

It is **not** yet intended to be the final long-term summary-generation policy.

---

## Replacement semantics

## Default mode

By default, the builder uses replace-or-rebuild semantics for the selected
summary kind.

That means:

- if a matching summary kind already exists for the selected episode
- the builder removes the matching old summary state
- then writes the new summary and memberships

This prevents stale matching summaries from accumulating silently under the
default path.

## Non-replacement mode

If you pass:

- `--no-replace-existing`

the builder keeps existing summaries of the same kind.

Use this only when you intentionally want coexistence and understand the effect
on future inspection and retrieval.

For the current first-slice operator workflow, the default replacement behavior
is usually the safer choice.

---

## Verification checklist

After a successful build, verify these points:

### 1. Summary row exists
Confirm the result includes:

- a non-null summary id
- the expected `summary_kind`
- the expected `episode_id`

### 2. Membership count is sensible
Confirm:

- `member_memory_count > 0`
- membership count matches your expectation for the episode's child memory items

### 3. Retrieval sees the rebuilt summary
Where applicable, confirm that current retrieval now prefers the canonical
summary through the current summary-first path.

### 4. Replacement behavior matches intent
If you expected a rebuild:

- verify `replaced_existing_summary = true`
- verify the returned summary id differs from the older matching summary id when
  a replacement actually occurred
- verify the rebuilt summary content is now the one surfaced by retrieval

If you expected a first build:

- verify `replaced_existing_summary = false`

If you used `--no-replace-existing`:

- verify `replaced_existing_summary = false`
- verify coexistence is intentional for the selected `summary_kind`

---

## Failure handling

If the command fails, the current CLI returns a non-zero exit code and prints an
error message.

Example failure categories include:

- missing database URL
- database connection failure
- invalid or unknown episode id
- persistence failure while writing summary state

### Recommended operator reading

Use this interpretation order:

1. configuration problem
   - missing or incorrect database URL
2. target problem
   - wrong `episode_id`
3. data-state problem
   - episode exists but has no child memory items
4. persistence/runtime problem
   - database or write failure

---

## Practical examples

## Example 1 — First explicit build

```/dev/null/sh#L1-1
ctxledger build-episode-summary --episode-id 11111111-1111-1111-1111-111111111111 --format json
```

Use this when:

- the episode already exists
- you want the first canonical summary for it

## Example 2 — Rebuild after source memory changed

```/dev/null/sh#L1-1
ctxledger build-episode-summary --episode-id 11111111-1111-1111-1111-111111111111 --summary-kind episode_summary --format json
```

Use this when:

- the episode's child memory items have changed
- you want the matching summary rebuilt cleanly

## Example 3 — Keep prior matching summaries

```/dev/null/sh#L1-1
ctxledger build-episode-summary --episode-id 11111111-1111-1111-1111-111111111111 --no-replace-existing --format json
```

Use this cautiously when:

- you intentionally want additional summary rows to coexist

---

## Current limitations

The current first explicit summary build path does **not** yet provide:

- summary-to-summary recursive building
- workspace-wide bulk summary building
- hidden automatic summary generation on every episode write
- automatic build on ordinary retrieval
- graph-required summary generation
- final long-term summary ranking/generation policy
- a dedicated operator dashboard for summary build status

These are later concerns.

---

## Current best practices

For the current `0.6.0` slice, prefer:

- explicit build first
- JSON output during validation/debugging
- default replacement behavior unless you have a strong reason not to
- post-build retrieval verification
- keeping graph considerations separate from the explicit summary build path

---

## Troubleshooting quick guide

## Problem: `episode_id was not found`
Likely cause:

- wrong episode id
- episode does not exist in canonical storage

Action:

- re-check the target episode id from your workflow/memory inspection path

## Problem: build skipped with `no_episode_memory_items`
Likely cause:

- the episode exists
- but there are no child memory items attached to it

Action:

- inspect whether the episode actually has canonical memory items
- confirm that the current episode is the one you intended to summarize

## Problem: rebuilt summary does not appear in retrieval
Likely causes:

- retrieval path is not targeting the expected workflow/episode scope
- summaries are disabled in the retrieval request
- you are reading a narrower shaping path such as `include_episodes = false`
- you are still inspecting an older compatibility-oriented surface instead of the
  grouped summary-first output

Action:

- verify the retrieval request shape
- confirm summaries are enabled
- confirm you are not using a deliberately narrow response mode
- inspect the returned `summaries` payload and `memory_context_groups` rather
  than relying only on flatter compatibility fields

## Problem: replacement appears to have happened but old summary state is still visible
Likely causes:

- you are inspecting a different summary kind than the one you rebuilt
- you intentionally used `--no-replace-existing`
- you are comparing against older cached output rather than a fresh retrieval
  result

Action:

- re-check the requested `summary_kind`
- confirm whether `--no-replace-existing` was used
- compare the returned `memory_summary_id` and summary text from a fresh
  retrieval run

## Problem: replacement did not happen
Likely causes:

- no matching summary kind existed
- `--no-replace-existing` was used

Action:

- inspect the command arguments
- inspect the returned `replaced_existing_summary` field

---

## Operational stance

The current explicit summary build path should be treated as:

- safe
- narrow
- operator-invoked
- canonical-relational
- easy to validate
- suitable for current `0.6.0` summary loop work

It should **not** yet be treated as a broad autonomous summary subsystem.

---

## Summary

Use `ctxledger build-episode-summary` when you want to:

- create or rebuild one canonical summary for one existing episode
- keep the current process explicit and inspectable
- validate the current summary-first retrieval loop
- preserve the current relational-first hierarchy boundaries

The current first-slice operator rule is:

- build explicitly
- verify explicitly
- replace matching summaries by default
- keep broader automation and graph mirroring as later follow-up decisions