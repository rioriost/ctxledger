# Summary Build Runbook for Explicit Episode Summary Building

## Purpose

This runbook explains the current operator flow for canonical summary building
and derived AGE summary graph refresh in `ctxledger`.

It is intended for operators and developers who need to:

- build one canonical summary for a selected episode
- rebuild an existing summary after the source memory items changed
- verify what the summary builder wrote
- verify what retrieval now returns after a rebuild
- refresh derived AGE summary graph state after canonical summary changes
- interpret graph-ready, graph-stale, degraded, and unknown readiness states
- read the currently defined AGE operator metrics that summarize canonical summary volume and derived-graph readiness posture
- understand how explicit build, gated auto build, and graph refresh relate

This runbook covers:

- `ctxledger build-episode-summary`
- workflow-completion-gated summary build behavior
- `ctxledger refresh-age-summary-graph`
- `ctxledger age-graph-readiness`

It also explains how those paths relate to:

- `memory_get_context`
- canonical relational summary state
- derived graph-backed auxiliary summary-member traversal

The current operator posture is:

- canonical summary build remains relationally authoritative
- graph refresh remains derived and rebuildable
- explicit build is the primary operator path
- workflow-completion summary build remains narrow, gated, and non-fatal

---

## Current behavior at a glance

The current operator flow is:

- canonical-relational first
- episode-scoped on the explicit build path
- deterministic on the explicit build path
- replace-or-rebuild by default
- independent from ordinary retrieval execution
- compatible with derived AGE summary graph refresh
- explicit about canonical vs derived ownership

There are now three closely related but distinct operator-visible paths:

1. explicit canonical build
   - `ctxledger build-episode-summary`
2. workflow-completion-gated canonical auto build
   - only when the latest checkpoint requests summary build
3. derived graph refresh
   - `ctxledger refresh-age-summary-graph`

In practical terms, explicit or gated canonical build currently:

1. reads canonical episode and memory state
2. builds one canonical summary text
3. writes one canonical `memory_summaries` row
4. writes canonical `memory_summary_memberships` rows
5. replaces existing summaries of the same `summary_kind` by default

Derived graph refresh currently:

1. reads canonical summary and membership state
2. mirrors that state into the constrained AGE summary-member graph
3. updates derived graph-backed auxiliary traversal readiness
4. does not redefine canonical truth

The current default summary kind is:

- `episode_summary`

### Canonical vs derived reading

For the current slice, read the operator flow as:

- canonical relational summary state is the source of truth
- derived AGE summary graph state is supplementary and rebuildable
- summary build success does not depend on graph refresh having already happened
- graph degradation should be interpreted as reduced auxiliary support or
  observability, not as canonical summary loss

This distinction matters during verification:
if canonical summary build succeeds but graph-backed auxiliary behavior is stale
or absent, the corrective action is graph refresh or graph-readiness inspection,
not reinterpretation of relational summary state as missing.

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

## Step 1 — Identify the target episode and intent

You need to know which of these operator intents you are following:

- explicit canonical build for one episode
- verification of a gated workflow-completion auto build
- derived graph refresh after canonical summary changes

For the explicit path, you need the canonical `episode_id`.

Typical sources include:

- prior workflow or memory inspection
- direct database inspection
- application responses that already expose episode identifiers

If you do not know the episode id yet, find it first through your normal
workflow/memory inspection path.

## Step 2 — Build or verify canonical summary state

For the explicit operator path, run:

```/dev/null/sh#L1-1
ctxledger build-episode-summary --episode-id <episode-uuid> --format json
```

For the workflow-completion-gated path, the operator action is different:

- verify that the latest checkpoint requested summary build
- verify the workflow completion result fields
- verify the resulting canonical summary rows and memberships if a build was attempted

The current gated auto-build path should be read as:

- narrow
- checkpoint-gated
- non-fatal
- canonical-relational first

Recommended operator reading:

- explicit build remains the normal direct operator tool
- gated auto build remains a workflow-completion convenience path
- graph refresh still remains a separate derived-state action

## Step 3 — Inspect canonical build outcome

For an explicit build result, focus on these output fields:

- `summary_built`
- `status`
- `skipped_reason`
- `replaced_existing_summary`
- `summary`
- `memberships`
- `details.member_memory_count`

For a workflow-completion-gated build result, focus on summary-build-related
completion details such as:

- whether summary build was requested
- whether summary build was attempted
- whether summary build succeeded
- whether a prior summary was replaced
- which canonical summary id was built
- how many memberships were written

## Step 4 — Inspect the written canonical summary state

After a successful explicit or gated build, inspect the resulting canonical
summary state and confirm:

- `summary.memory_summary_id` is present
- `summary.episode_id` matches the target episode
- `summary.summary_kind` matches the requested or expected kind
- `memberships` is not empty when a real summary was built
- the member count matches the intended child memory set

For repeat runs, also confirm:

- `replaced_existing_summary = true` when a rebuild replaced a matching prior
  summary
- `replaced_existing_summary = false` when the run created a first summary or
  when non-replacement behavior was requested

## Step 5 — Verify retrieval sees canonical summary state first

After a successful build, the current expectation is that canonical summary
state may be preferred by `memory_get_context` when summaries are enabled.

Use your normal retrieval path and confirm that the response reflects:

- `summary_selection_applied = true`
- `summary_selection_kind = "memory_summary_first"`

where applicable for the target workflow/episode context.

Also confirm, where relevant:

- the returned `summaries` payload references the expected canonical
  `memory_summary_id`
- grouped summary output remains present in `memory_context_groups`
- rebuilt summary content is now visible instead of older matching summary state
- direct summary-member memory-item expansion reflects the expected member set

The important operator rule is:

- verify canonical summary visibility before treating graph-backed auxiliary
  behavior as the main concern

## Step 6 — Refresh derived AGE summary graph state when needed

If you are validating graph-backed auxiliary summary-member behavior, refresh the
derived summary graph after a build or rebuild:

```/dev/null/sh#L1-1
ctxledger refresh-age-summary-graph
```

Use this when:

- you want graph-backed auxiliary summary-member traversal to reflect the latest
  canonical summary state
- you recently rebuilt canonical summaries and want derived graph state to catch
  up
- you are debugging summary-related readiness or observability behavior
- a gated workflow-completion build succeeded and you now want derived graph
  state to mirror that canonical change

Do **not** read this as a requirement for canonical summary correctness.
The canonical relational summary build is already valid even before derived graph
state is refreshed.

## Step 7 — Check AGE summary graph readiness and operational interpretation

After refresh, or when debugging graph-backed auxiliary behavior, inspect
readiness:

The current operator metrics that matter most in this step are:

- `memory_summary_count`
- `memory_summary_membership_count`
- `age_summary_graph_ready_count`
- `age_summary_graph_stale_count`
- `age_summary_graph_degraded_count`
- `age_summary_graph_unknown_count`

At the current stage, these metrics should be read as follows:

- `memory_summary_count`
  - canonical count of relational summary rows in `memory_summaries`
- `memory_summary_membership_count`
  - canonical count of relational membership rows in `memory_summary_memberships`
- `age_summary_graph_ready_count`
  - current operator-facing count for runs where derived AGE summary graph state is read as ready
- `age_summary_graph_stale_count`
  - current operator-facing count for runs where derived AGE summary graph state is read as stale relative to canonical summary memberships
- `age_summary_graph_degraded_count`
  - current operator-facing count for runs where derived AGE summary graph state is degraded
- `age_summary_graph_unknown_count`
  - current operator-facing count for runs where derived AGE summary graph state is currently unknown

These are operator metrics, not a replacement for canonical relational inspection.
Read them as concise operational indicators that help you decide whether to:

- trust current graph-backed auxiliary summary-member traversal as ready
- refresh derived graph state
- investigate degraded graph behavior
- continue treating canonical relational summary state as the sole reliable source of truth for the moment

```/dev/null/sh#L1-1
ctxledger age-graph-readiness
```

At the current stage, the readiness payload should be read using:

- `graph_status`
- `readiness_state`
- `ready`
- `stale`
- `degraded`
- `operator_action`

Recommended operator interpretation:

- `readiness_state = "ready"`
  - graph-backed auxiliary summary-member traversal is available as expected
  - no graph corrective action is currently required

- `readiness_state = "stale"`
  - canonical summary state exists, but derived graph state is behind canonical
    membership state
  - preferred corrective action is:
    - `ctxledger refresh-age-summary-graph`

- `readiness_state = "degraded"`
  - graph-backed auxiliary behavior should be treated as degraded
  - ordinary canonical summary correctness should still be interpreted from
    relational state first
  - use `operator_action` to decide whether to:
    - verify AGE availability
    - bootstrap the graph
    - refresh the graph
    - inspect graph-read failure behavior

- `readiness_state = "unknown"`
  - do not assume graph-backed auxiliary support is ready
  - continue to read relational summary state as canonical
  - inspect readiness conditions before treating graph-backed behavior as absent
    by design

This runbook flow is intentionally ordered:

1. build or verify canonical summary state
2. verify canonical retrieval behavior
3. refresh derived graph state if needed
4. interpret readiness outcome
5. read operator metrics in the same canonical-first order
6. only then diagnose graph-backed auxiliary behavior

When operator visibility is needed beyond the direct readiness command, also use
the operator-facing stats surfaces and read the AGE-related fields there in the
same canonical-first order:

- `ctxledger stats`
- `ctxledger memory-stats`

In those outputs, the current AGE operator metrics should be interpreted as:

- canonical summary volume first:
  - `memory_summary_count`
  - `memory_summary_membership_count`
- derived graph posture second:
  - `age_summary_graph_ready_count`
  - `age_summary_graph_stale_count`
  - `age_summary_graph_degraded_count`
  - `age_summary_graph_unknown_count`

That reading order matters.
If canonical summary metrics show real summary state while readiness-oriented
graph metrics indicate stale, degraded, or unknown graph posture, the next
action should still begin from canonical relational interpretation rather than
from a graph-first assumption.

observability, check current graph readiness:

```/dev/null/sh#L1-1
ctxledger age-graph-readiness
```

Interpret the result this way:

- graph ready
  - derived summary graph state is available for the current bounded auxiliary
    path
- graph not ready / degraded
  - canonical relational summary state may still be healthy
  - ordinary summary-first retrieval should still be interpreted from canonical
    relational state first
  - the likely impact is reduced auxiliary graph-backed enrichment or reduced
    graph observability, not summary loss

This keeps the current `0.6.0` boundary explicit:

- canonical build and retrieval correctness come from relational state
- graph-backed summary behavior remains additive and degradable

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