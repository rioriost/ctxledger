# Grafana `0.9.0` Observability Enhancement Proposal

## Purpose

This note proposes a bounded Grafana enhancement slice aligned with the current
`0.9.0` repository posture.

It is intended to answer a practical operator question:

> If `0.9.0` strengthened resumability, interaction capture, file-work metadata,
> and bounded failure reuse, what should Grafana show so operators can detect
> healthy behavior, drift, and degradation quickly?

This is not a new product milestone.
It is a focused operator-facing observability proposal for the existing bounded
`0.9.0` release shape.

---

## Current reading

The current repository already provides useful Grafana visibility for:

- workflow counts
- workflow/attempt/verify status distributions
- recent workflow activity
- memory totals
- memory provenance counts
- summary-layer counts
- high-level runtime activity timelines

This baseline is useful, but it is still centered on **volume** and **broad
state**.

For the bounded `0.9.0` slice, operators now also need better visibility into:

- interaction-memory activity
- file-work-memory activity
- whether durable capture is continuing to happen
- whether workflow activity and memory activity still appear operationally
  aligned
- whether failure and verification signals suggest investigation is needed
- whether the system is healthy in a canonical-first sense even when derived
  layers are partial

This proposal therefore focuses on adding operator meaning, not only more
counts.

---

## Design principles

### 1. Canonical-first observability

Grafana must continue to reflect the repository’s canonical posture:

- relational workflow and memory state first
- derived or auxiliary readings second

Dashboard wording should not imply that a Grafana panel is itself the source of
truth.
It is an operator reading layer on top of canonical PostgreSQL state.

### 2. Operational usefulness over metric sprawl

A panel should help answer one of these questions quickly:

- Is the system progressing?
- Is capture still happening?
- Is verification backing up?
- Is failure activity increasing?
- Is interaction/file-work visibility present as expected?
- Is the current state degraded, stalled, or simply quiet?

If a panel does not improve an operator decision, it should not be added.

### 3. Bounded `0.9.0` scope

This proposal is intentionally bounded.

It does **not** assume:

- full incident-management workflows
- broad historical analytics
- unlimited dashboard drilldown
- a complete observability redesign
- a graph-first operator model

It targets the operational consequences of the already-implemented `0.9.0`
slice.

### 4. Prefer explicit interpretation panels

Operators should not need to mentally combine five raw counters to decide
whether something looks healthy.
Where useful, Grafana should include small interpretation tables that explain
the current reading, such as:

- capture active
- workflow progressing but verification lagging
- interaction memory present
- file-work capture absent
- failure activity needs review

---

## Why a `0.9.0` Grafana follow-up is needed

The current `0.9.0` release-facing documents already indicate that operator
observability improved, but only partially, for interaction/file-work-specific
signals.

That means the repository can now do more than the dashboards currently make
easy to see.

Without a dashboard follow-up, an operator may still struggle to answer:

- Are user/agent interactions still being durably captured?
- Is file-work metadata showing up in a meaningful way?
- Is recent workflow activity producing corresponding memory activity?
- Are verification failures or repeated failures becoming the dominant signal?
- Is the system merely idle, or is it unhealthy?

The gap is no longer about missing all observability.
It is about missing the **most operationally useful `0.9.0` interpretation
surface**.

---

## Operational questions the enhanced dashboards should answer

A good bounded `0.9.0` Grafana enhancement should let an operator answer the
following quickly.

### Workflow progression
- Are workflows continuing to move?
- Are checkpoints being created recently?
- Are attempts accumulating in a concerning status?
- Are verify reports keeping up with workflow activity?

### Memory capture
- Are episodes and memory items still being created?
- Is interaction memory visibly present?
- Is file-work memory visibly present?
- Is capture activity recent, or has it gone quiet unexpectedly?

### Alignment between workflow and memory activity
- Does recent workflow activity roughly correspond to recent memory activity?
- Are workflows advancing without expected memory-side visibility?
- Is memory volume increasing while workflow progress appears stalled?

### Verification and failure pressure
- Are verify failures rising?
- Are failures recent and concentrated enough to warrant action?
- Is there evidence of repeated degraded operation rather than isolated noise?

### Canonical-versus-derived posture
- Is canonical relational state healthy even if auxiliary layers are partial?
- Are operators able to distinguish “degraded but still canonically correct”
  from “capture appears broken”?

---

## Recommended dashboard structure

## 1. Keep the existing dashboards, but sharpen their jobs

Recommended dashboard set:

- `runtime_overview`
  - operator health, workflow progression, verification pressure, recent drift
- `memory_overview`
  - capture activity, provenance composition, interaction/file-work visibility
- `failure_overview`
  - failure pressure, recent recurrence, operator triage signals

Do not create many new dashboards for `0.9.0`.
Prefer strengthening the current three-dashboard posture.

---

## 2. Strengthen `runtime_overview`

### Why

This dashboard is the best place to answer:

- Is the system progressing?
- Is verification lagging?
- Does recent activity look healthy or stalled?

### Recommended additions

#### A. Active workflow pressure panel

Add a stat or table that emphasizes currently non-terminal workflow volume.

Purpose:

- distinguish “historical total workflows” from “work still in flight”
- help operators understand current operational load

Suggested reading:

- running workflows
- non-terminal workflows
- workflows updated in the last 24 hours

#### B. Verify backlog / pressure panel

Add a small interpretation panel showing whether verification appears to be
keeping up.

Purpose:

- surface when workflows and attempts are moving but verify reports are sparse
- help operators notice validation drift early

Suggested reading:

- recent workflows updated
- recent checkpoints created
- recent verify reports created
- interpretation such as:
  - `balanced`
  - `verify lag possible`
  - `no recent workflow activity`

#### C. Recent workflow table with stronger triage fields

Extend the existing recent-workflow table to emphasize operator triage.

Recommended fields:

- workspace
- ticket
- workflow status
- latest step
- latest verify status
- updated time
- age since updated

Purpose:

- make stalled or long-idle workflows obvious
- reduce the need to cross-reference CLI output for first-pass triage

#### D. Runtime interpretation panel

Add a table with one-row operator guidance derived from current aggregate state.

Example readings:

- `workflow activity present and verification present`
- `workflow active but verification absent recently`
- `no recent runtime activity`
- `recent checkpoint activity without verify follow-through`

This should remain simple and bounded.
It is not a policy engine.

---

## 3. Strengthen `memory_overview`

### Why

The current memory dashboard already shows totals, provenance, and summary-layer
signals.
For `0.9.0`, it should now answer whether **capture behavior introduced or
strengthened by the milestone is actually visible**.

### Recommended additions

#### A. Interaction memory item count

Add a dedicated stat panel for interaction memory.

Purpose:

- make `0.9.0` interaction capture visible at a glance
- avoid hiding interaction activity inside a broad provenance mix

Suggested label:

- `Interaction Memory Items`

If schema support is needed, this should come from an observability view rather
than direct raw-table dependence in many panels.

#### B. File-work memory item count

Add a dedicated stat panel for file-work memory visibility.

Purpose:

- surface whether file-work-aware capture is present
- help operators detect when interaction capture exists but file-work tagging is
  unexpectedly absent

Suggested label:

- `File-Work Memory Items`

#### C. Interaction/file-work trend panel

Add a time-series panel for recent creation trends related to:

- interaction memory
- file-work memory
- general memory items

Purpose:

- show whether `0.9.0`-specific memory visibility is active
- distinguish flat historical totals from current capture behavior

#### D. Capture freshness panel

Add a small table emphasizing the latest timestamps for:

- latest episode
- latest memory item
- latest interaction memory item
- latest file-work memory item

Purpose:

- help operators decide whether the system is merely quiet or whether a
  particular capture path may be stale

#### E. Provenance plus `0.9.0` interpretation panel

Keep provenance breakdown, but add a small explanatory table for bounded
operator reading.

Example readings:

- `interaction capture visible`
- `file-work capture visible`
- `memory capture active but interaction capture absent`
- `memory active but file-work capture absent`

This is especially useful because raw provenance counts alone still require too
much mental interpretation.

---

## 4. Strengthen `failure_overview`

### Why

`0.9.0` increased the practical value of bounded failure reuse and interaction /
file-work-aware investigation.
The failure dashboard should therefore help answer whether failure signals are
becoming operationally important, not only whether failures exist.

### Recommended additions

#### A. Recent failure activity panel

Add a panel focused on recent failure creation volume.

Purpose:

- distinguish old historical failures from current pressure
- help operators decide whether active investigation is needed now

#### B. Failure recurrence indicator

Add a bounded indicator for repeated failure pressure.

This does not require a full repeated-failure classifier.
A practical first slice could show:

- recent failures by type or reason bucket
- top repeated failure reasons in a recent window
- count of repeated failure signatures above a small threshold

Purpose:

- make “isolated issue” versus “pattern” more visible

#### C. Failure-to-verify correlation view

If the current schema can support it cleanly, add a small panel that helps
operators notice when verify failures and failure records move together.

Purpose:

- improve triage quality
- highlight when verification degradation is not an isolated reporting issue

#### D. Triage table

Add or extend a table with:

- failure type / reason
- latest occurrence
- recurrence count in a bounded window
- related workflow or attempt identifier if available

Purpose:

- support first-pass investigation without leaving Grafana immediately

---

## Recommended new observability views

To keep dashboards maintainable, the `0.9.0` enhancement should add or expand
SQL views rather than placing all logic in raw Grafana SQL.

Recommended additions are below.

## 1. `observability.memory_capture_overview`

Purpose:

- centralize memory-side `0.9.0` operator counts

Recommended fields:

- `episode_count`
- `memory_item_count`
- `interaction_memory_item_count`
- `file_work_memory_item_count`
- `latest_episode_created_at`
- `latest_memory_item_created_at`
- `latest_interaction_memory_item_created_at`
- `latest_file_work_memory_item_created_at`

Why:

- supports at-a-glance capture status
- avoids repeated ad hoc filtering in dashboard JSON

## 2. `observability.memory_item_kind_counts` or equivalent

Purpose:

- expose grouped counts for interaction/file-work-related memory categories in a
  stable way

Recommended fields:

- category or kind
- count

Possible categories:

- interaction
- file_work
- workflow_checkpoint_auto
- workflow_complete_auto
- episode
- derived

Why:

- makes the dashboard easier to evolve without coupling panel logic to internal
  storage details

## 3. `observability.runtime_recent_activity_summary`

Purpose:

- summarize recent-window activity for operator interpretation

Recommended fields:

- workflows_updated_last_24h
- checkpoints_created_last_24h
- verify_reports_created_last_24h
- episodes_created_last_24h
- memory_items_created_last_24h
- interaction_memory_items_created_last_24h
- file_work_memory_items_created_last_24h

Why:

- supports compact interpretation tables
- helps runtime and memory dashboards share the same operator reading

## 4. `observability.failure_recent_summary`

Purpose:

- provide a bounded recent failure reading

Recommended fields:

- failures_created_last_24h
- failures_created_last_7d
- repeated_failure_groups_last_7d
- latest_failure_created_at

Why:

- keeps failure panels simple
- emphasizes current operational pressure rather than historical totals only

---

## Recommended panels by priority

## Priority 1: highest operator value

These panels would deliver the most immediate value for `0.9.0`.

- interaction memory item stat
- file-work memory item stat
- recent capture freshness table
- recent runtime activity summary table
- verify backlog / pressure interpretation panel
- recent failure activity stat or chart

These directly answer whether the `0.9.0` capture and validation posture is
showing up operationally.

## Priority 2: useful next layer

- interaction/file-work trend chart
- repeated failure indicator
- stronger recent workflow triage table
- runtime health interpretation row
- bounded recent-window activity summary view

These improve investigation speed after the first-pass health reading.

## Priority 3: optional follow-up

- more granular reason-bucket failure views
- category-by-category memory capture composition
- richer workflow-to-memory alignment ratios
- panel links to CLI/runbook investigation paths

These are useful, but not required for a credible `0.9.0` enhancement slice.

---

## Recommended operator readings

The dashboards should make the following interpretations easy.

### Healthy bounded `0.9.0` reading
- recent workflow activity exists
- recent checkpoints exist
- verify activity exists
- memory capture is recent
- interaction memory is present
- file-work memory is present when expected
- failures are low or isolated

### Quiet but not obviously unhealthy
- little recent workflow activity
- little recent memory activity
- no strong failure spike
- latest timestamps are old across the board rather than only in one path

### Capture concern
- recent workflow/checkpoint activity exists
- general memory activity is present or expected
- interaction memory or file-work memory remains unexpectedly low or stale

### Verification concern
- workflow activity is recent
- checkpoints are recent
- verify reports are sparse, failed, or absent relative to recent activity

### Failure pressure concern
- recent failure activity is rising
- repeated reasons cluster in a recent window
- verify degradation and failure activity move together

These readings should be visible in the dashboards themselves, not only inferred
from raw numbers.

---

## Important wording guidance

Dashboard text should preserve the repository’s current posture.

Use language like:

- `operator signal`
- `current reading`
- `capture visible`
- `degraded but canonically correct`
- `recent activity absent`

Avoid language like:

- `system truth`
- `guaranteed healthy`
- `all workflows should`
- `all completions must`
- `graph unavailable means broken`

This matters because the repository already distinguishes canonical truth from
derived operational interpretation.

---

## Suggested implementation slice

A small, repository-friendly implementation slice would be:

### Step 1
Add bounded SQL views for:

- interaction/file-work memory counts
- latest interaction/file-work timestamps
- recent-window runtime and memory activity summaries

### Step 2
Update `memory_overview.json` to add:

- interaction memory stat
- file-work memory stat
- capture freshness table
- interaction/file-work trend panel
- `0.9.0` capture interpretation table

### Step 3
Update `runtime_overview.json` to add:

- recent-window runtime summary
- verify pressure interpretation
- stronger triage table fields
- one-row runtime health interpretation

### Step 4
Update `failure_overview.json` with:

- recent failure activity emphasis
- bounded recurrence visibility
- triage-oriented table improvements

This keeps the change focused and consistent with the repository’s preference
for small semantic slices.

---

## Acceptance reading for this proposal

A good bounded acceptance reading for this Grafana enhancement would be:

- Grafana now exposes the main `0.9.0` operational signals that matter for
  interaction capture, file-work capture, verification pressure, and recent
  failure pressure
- operators can distinguish quiet systems from degraded systems more easily
- dashboards remain canonical-first and do not overclaim derived meaning
- the enhancement strengthens operator usefulness without introducing a large
  new observability subsystem

---

## Out of scope

This proposal does not require:

- broad BI-style analytics
- long-horizon reporting dashboards
- per-user behavioral analytics
- full alerting-policy design
- a complete incident response framework
- graph-primary observability
- replacing CLI investigation paths

The goal is narrower:
make the current bounded `0.9.0` system easier to operate.

---

## Practical recommendation

For the bounded `0.9.0` slice, the best default is:

1. add dedicated interaction/file-work operator signals
2. add recent-window interpretation panels
3. emphasize freshness, backlog, and failure pressure
4. keep canonical-first wording throughout

That is the smallest change set most likely to improve real operator outcomes.