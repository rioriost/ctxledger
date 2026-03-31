# Grafana Zero-Signal Gap Analysis and Remediation Plan

## Purpose

This note defines the bounded follow-up plan for the current Grafana tiles that
remain at `0` or `No data` in the Docker-backed local `ctxledger` deployment.

It answers a practical release-facing question:

> When Grafana shows zero-state readings for file-work memory, canonical
> summaries, summary memberships, or derived memory, is that expected product
> state, an observability-definition gap, or an implementation gap?

This is a bounded observability/domain plan.
It is not a broad dashboard redesign proposal.

The immediate goals are:

- explain what these tiles were intended to mean
- compare the intent in current docs with the current implementation
- identify which zeros are valid and which are misleading
- define a narrow remediation sequence
- preserve the repository’s canonical-first posture
- make explicit that file-work restoration depends on both:
  - ctxledger runtime/tool capability
  - `.rules` discipline that makes agents record file-touching work in context

---

## Current observed problem

In the current Docker-backed local stack, Grafana can show values such as:

- `File-Work Memory Items = 0`
- `Canonical Summaries = 0`
- `Summary Memberships = 0`
- `Derived Memory Items = No data`

At the same time, the system may already show healthy non-zero values for:

- episodes
- memory items
- interaction memory items
- embeddings
- workflow activity

This creates an operator-reading problem:

- some zero-state panels are reporting **real current product state**
- some are reporting **a mismatch between intended semantics and current query logic**
- some are reporting **derived-layer absence downstream of canonical-layer absence**

Without a narrow follow-up, operators may incorrectly conclude that:

- Docker or Grafana is broken
- the datasource is stale
- memory capture is broadly failing
- derived-layer absence implies canonical-state loss

Those conclusions are too broad for the current repository state.

---

## Canonical reading first

This plan should be read with the repository’s current posture kept explicit:

1. workflow / checkpoint / verify truth is canonical
2. canonical memory artifacts are next
3. canonical summary artifacts are next
4. observability views are a read layer over canonical PostgreSQL state
5. AGE / graph-backed / derived observability remains auxiliary and degradable

That means:

- Grafana is never the source of truth
- a zero tile is only meaningful insofar as it reflects canonical or intentionally
  derived PostgreSQL-backed state
- a derived `No data` reading must not be interpreted as canonical loss

---

## Documentation-backed intended meaning of the affected tiles

## 1. File-work memory tiles

The `0.9.0` docs establish that file-work metadata was intended to become:

- durable
- queryable
- resumability-relevant
- failure-reuse-relevant
- linked to workflow and interaction context where useful

This appears in current docs such as:

- `docs/memory/design/file_work_metadata_contract.md`
- `docs/project/releases/plans/versioned/0.9.0_acceptance_checklist.md`
- `docs/project/releases/plans/versioned/0.9.0_focused_validation_plan.md`
- `docs/project/releases/plans/versioned/grafana_0.9.0_observability_enhancement.md`

The intended operator meaning of a file-work-related Grafana tile is therefore:

- whether durable file-work-aware memory capture is actually visible
- whether interaction capture exists without file-work tagging
- whether the `0.9.0` file-work slice is active in practice, not only on paper

This means the file-work tile was **not** intended merely as a vanity metric.
It was meant to act as an operator-visible signal for whether the bounded
`0.9.0` file-work contract is operationally visible.

---

## 2. Canonical summary and summary membership tiles

The `0.6.0` and later summary docs establish that:

- `memory_summaries` are canonical relational artifacts
- `memory_summary_memberships` are canonical relational artifacts
- workflow-completion summary automation is:
  - narrow
  - checkpoint-gated
  - non-fatal
  - not always-on by default

This appears in current docs such as:

- `docs/memory/design/workflow_summary_automation_direction.md`
- `docs/memory/runbooks/summary_build_runbook.md`
- `docs/memory/decisions/workflow_summary_targeting_policy.md`
- `docs/project/releases/plans/versioned/0.6.0_grafana_dashboard_followup.md`

The intended operator meaning of the summary tiles is therefore:

- whether explicit or gated canonical summary construction has actually occurred
- whether the summary layer is absent because it was never requested
- whether the summary layer exists and can support summary-first retrieval
- whether the graph-backed auxiliary layer has canonical inputs to mirror

These tiles were intended to surface the current bounded summary hierarchy
posture, not imply that summaries are always expected for every workflow.

---

## 3. Derived memory / derived-layer tiles

The docs consistently treat graph-backed and derived summary support as:

- additive
- auxiliary
- degradable
- not canonical truth

This appears in current docs such as:

- `docs/memory/runbooks/summary_build_runbook.md`
- `docs/project/releases/plans/versioned/0.6.0_grafana_dashboard_followup.md`
- `docs/project/releases/plans/versioned/grafana_0.9.0_observability_enhancement.md`
- `docs/operations/runbooks/remember_path_operator_runbook.md`

The intended operator meaning of a derived-memory or derived-layer tile is
therefore:

- whether the derived layer has meaningful canonical substrate to work from
- whether derived visibility is currently available
- whether the operator should read current thinness as:
  - expected
  - degraded-but-canonically-correct
  - or worth investigation

This means a `No data` reading here was always intended to be read as a
secondary signal, not a proof of system breakage.

---

## Current implementation reading

Based on the current repository shape, the observed zero-state readings separate
into three categories.

## 1. Valid current-state zeros

These appear to be **faithful readings of actual current state**.

### Canonical summaries = 0
This is currently plausible and expected when:

- no explicit `build-episode-summary` path has been run
- no workflow completion had summary building requested through the latest
  checkpoint payload
- summary automation remains narrow and checkpoint-gated

This matches the documented policy:
- `default_requested = false`
- summary build requires explicit request posture
- workflow completion should remain successful even when summary build is absent

### Summary memberships = 0
If summary rows are absent, summary memberships being zero is also a valid
downstream reading.

### Derived memory / derived layer = `No data`
If the canonical summary layer is empty, a derived-layer panel having no current
signal is also a valid downstream reading.

These three are best understood as **state explanation gaps**, not immediate
implementation failures.

---

## 2. Likely valid product-state zero, but high-value to improve

### File-work memory items = 0
The database may genuinely contain no currently persisted memory items with
file-work metadata.
If so, the zero itself is valid as a product-state reading.

However, this is still important because the `0.9.0` docs describe file-work
metadata as part of the bounded product direction.
If normal repository work is not producing durable file-work-tagged memory at
all, then either:

- the capture boundary is still too weak
- the intended producers are not yet implemented strongly enough
- the docs overstate the currently achieved product surface

So this zero may be a true reading, but it still represents a release-facing
gap relative to the intended operator story.

---

## 3. Misleading observability-definition gap

There is also a narrower technical gap:

- service-layer file-work counting and Grafana observability SQL do not use the
  same definition of file-work metadata

Current service-side counting logic is intended to treat fields such as:

- `file_name`
- `file_path`
- `file_operation`
- `purpose`

as file-work-relevant signals.

But the current observability SQL for Grafana has been documented and
implemented more narrowly around fields like:

- `file_path`
- `file_paths`
- `file_work_count`
- `file_work_paths`

This means the system can drift into a state where:

- service/CLI logic would treat a memory item as file-work-aware
- Grafana would not count it

That is an observability-definition mismatch.
Even if it is not the cause of today’s exact zero, it is still a correctness gap
for the operator surface.

---

## Main gap statement

The current zero-tile problem is not one single bug.

It is the combination of:

1. **real current bounded product state**
   - summary layer not built yet
   - derived layer therefore thin or absent

2. **likely under-realized milestone behavior**
   - file-work metadata capture is not yet operationally visible enough in normal
     usage

3. **observability-definition drift**
   - service-level file-work semantics and Grafana SQL semantics are not aligned

4. **runtime exposure gap**
   - the current default live runtime can expose too few representative
     file-oriented producer paths for the running `ctxledger` server
   - because of that, the interaction-memory producer can be capable of storing
     bounded file-work metadata while still never receiving representative
     file-oriented traffic in the default stack

5. **rules-versus-runtime coordination gap**
   - file-work restoration is not achieved by runtime capability alone
   - it also depends on agent behavior rules requiring file-touching work to be
     recorded and linked to the active work loop
   - if either side is missing:
     - the tool/runtime cannot capture the event
     - or the agent never emits the record
   - in both cases, resumability and context restoration remain weaker than the
     intended product posture

The remediation plan must therefore avoid an overly simplistic response such as:

- “just change the dashboard”
- “just force non-zero values”
- “just blame Docker”
- “just enable summary generation everywhere”

---

## What the docs imply the plan should optimize for

Across the current docs, the bounded intended operator experience is:

- interaction capture should visibly exist
- file-work-aware capture should be distinguishable from generic interaction
  capture
- summary-layer absence should be interpretable, not mysterious
- derived-layer thinness should be read as downstream and degradable
- all operator readings should remain canonical-first

That means the correct plan is:
The correct plan is:

- improve semantic accuracy first
- improve operator interpretation second
- align runtime/tool capability with agent recording discipline
- only then decide whether broader product behavior needs to change

---

## Decision summary

This plan adopts the following working decisions.

### Decision 1 — Do not treat all zero tiles as defects
Some zeros are correct and reflect bounded current product state.

### Decision 2 — Treat file-work zero as both a product and observability question
A file-work zero may be real, but it is still an important milestone-gap signal.

### Decision 3 — Preserve narrow summary automation policy
Do not “fix” canonical summary zeros by silently converting summary building into
an always-on hidden side effect.

### Decision 4 — Align definitions before expanding behavior
Operator trust requires the service, CLI, and Grafana read layers to count the
same thing when they use the same label.

### Decision 5 — Prefer interpretation panels over fake completeness
When a zero is expected under current policy, Grafana should say so clearly
instead of making operators infer breakage.

### Decision 6 — Treat file-work restoration as a joint model
File-work restoration should be implemented jointly by:

- ctxledger runtime and tool capability
- `.rules` behavior that requires agents to record file-touching work in context

Neither side is sufficient on its own.

---

## Remediation plan

## Phase 1 — Definition alignment

### Goal

Ensure that the same operator concept has the same meaning across:

- service-layer counters
- CLI counters
- observability SQL views
- Grafana panels

### Scope

Update file-work observability definitions so that Grafana aligns with the
intended bounded file-work contract.

### Required changes

#### 1. Align file-work counting fields
The observability SQL should use the same bounded file-work-identifying fields as
the service-side file-work counter.

Minimum alignment target:

- `file_name`
- `file_path`
- `file_operation`
- `purpose`

Optional retained compatibility fields if still useful:

- `file_paths`
- `file_work_count`
- `file_work_paths`

### Deliverables

- updated `docs/sql/observability_views.sql`
- any matching code/comment cleanup needed so the contract is explicit
- tests or validation checks that compare service-side and observability-side
  semantics for representative cases

### Why this phase comes first

If definitions drift, operators cannot trust the dashboards even when product
behavior improves later.

---

## Phase 2 — Interpretation clarity

### Goal

Make zero-state readings understandable without requiring operators to inspect
source code.

### Scope

Improve the dashboard/operator explanation layer while preserving PostgreSQL as
the stable observability source.

### Required changes

#### 1. Add or keep interpretation panels that explain current summary posture
The summary-related reading should clearly distinguish:

- no canonical summaries built yet
- summaries exist but memberships are absent
- canonical summary layer present

#### 2. Add or refine interpretation for capture posture
The file-work/interaction interpretation should clearly distinguish:

- interaction capture visible, file-work capture absent
- file-work capture visible
- generic memory capture visible but `0.9.0`-specific capture absent
- no meaningful memory capture visible

#### 3. Clarify runbook guidance
The Grafana and remember-path runbooks should explicitly tell operators that:

- a summary zero can be expected under current checkpoint-gated policy
- derived `No data` is downstream of canonical absence, not canonical loss
- file-work zero should trigger product-state investigation, not only dashboard
  troubleshooting

### Deliverables

- dashboard JSON updates where needed
- runbook updates in:
  - `docs/operations/runbooks/grafana_operator_runbook.md`
  - `docs/operations/runbooks/remember_path_operator_runbook.md`
  - optionally `docs/memory/runbooks/summary_build_runbook.md`

---

## Phase 3 — Product-surface gap review for file-work capture

### Goal

Decide whether the repository currently satisfies its own bounded `0.9.0`
file-work claims strongly enough.

### Scope

Review where file-work metadata was intended to be produced and whether those
paths are actually materializing durable memory items in representative use.

### Questions to answer

- which current write paths are supposed to create file-work metadata?
- is file-work metadata expected mainly from interaction capture, checkpoint
  shaping, manual memory writes, or file-touching helper paths?
- are normal repository-editing flows actually populating those fields?
- does the default live runtime actually expose file-oriented tool calls that can
  feed the interaction-memory producer?
- do `.rules` explicitly require the agent to emit file-work records whenever
  file-touching work occurs in an active work loop?
- if not, should the docs be narrowed, or should the implementation be extended?

### Likely implementation directions

#### Option A — Strengthen interaction-derived file-work capture
If interaction events already contain bounded file-work intent, propagate that
intent into durable memory metadata more consistently.

#### Option B — Close the runtime exposure gap
If the default live runtime does not expose file-oriented MCP tools, add a
bounded exposure path or another explicit runtime hook so representative
file-touching work can actually produce durable file-work-tagged interaction
memory.

This should be read carefully:

- the goal is not to turn `ctxledger` into a full repository-editing platform
- the goal is to ensure that the file-work observability story has at least one
  real producer in the default operator path
- if file-oriented work continues to happen only outside the live runtime,
  Grafana will continue to report zero file-work memory even when the producer
  logic is technically capable of storing it

#### Option C — Strengthen file-edit/write path metadata shaping
If repository file-edit actions are observable in the current architecture,
create bounded durable metadata records or enrich existing memory records with:

- repository-relative file path
- operation kind
- purpose
- workflow / attempt linkage
- enough work-loop context to restore what the agent was doing later

This should be paired with `.rules` that require agents to emit those records
when file-touching work occurs, so the capability is exercised consistently
rather than only existing in theory.

#### Option D — Narrow docs if the current milestone claim is too strong
If current implementation intentionally does not yet produce file-work-aware
durable metadata except in narrow cases, update docs so operators are not led to
expect a signal that the product does not yet promise strongly enough.

### Preferred direction

Prefer implementation strengthening over documentation narrowing **if** the
required capture remains bounded and explainable.
The repository’s current `0.9.0` docs strongly imply that file-work metadata is
part of the intended milestone behavior, so fully retreating from that claim
should be the fallback, not the default.

Within implementation strengthening, prefer this order:

1. align counting semantics
2. strengthen producer metadata shaping
3. ensure the default runtime actually exposes a representative producer path
4. ensure `.rules` require agents to use that path whenever file-touching work
   occurs in an active work loop

---

## Phase 4 — Focused validation

### Goal

Prove that the repaired observability story is true and stable.

### Required validation areas

#### 1. Observability definition alignment
Representative tests should prove that file-work-identifying metadata counted by
service logic is also visible through observability SQL.

#### 2. Summary zero-state interpretation
Validation should prove that the operator-facing reading for summary absence is
correct under:
- no build requested
- build requested and succeeded
- summaries present but derived layer thin or stale

#### 3. File-work signal visibility
Representative validation should prove that when bounded file-work metadata is
persisted, the dashboard-facing SQL sees it.

#### 4. Derived-layer interpretation
Validation should prove that derived-layer thinness is never documented or
presented as canonical summary loss.

### Candidate validation homes

- focused service tests
- observability SQL verification tests
- Grafana/dashboard query validation where practical
- runbook review and example updates

---

## Concrete implementation slices

The recommended order of actual implementation work is:

1. align file-work counting semantics across service and observability SQL
2. add or refine dashboard interpretation panels
3. update runbooks so zero-state meanings are explicit
4. inspect file-work producers and decide whether bounded implementation
   strengthening is needed
5. verify whether the default runtime exposes any representative file-oriented
   producer path
6. if not, add a bounded runtime exposure path or explicitly narrow the operator
   claim
7. strengthen `.rules` so agents are required to record file-touching work in
   active work loops
8. add focused validation for the repaired observability contract

This should remain one bounded observability domain slice, not a broad platform
rewrite.

---

## What should not be done

The following responses are explicitly discouraged.

### 1. Do not fake non-zero values
Do not make panels non-zero merely to reduce operator discomfort.

### 2. Do not make summary build always-on by accident
The current docs consistently frame summary automation as explicit, gated, and
non-fatal.
That policy should not be silently replaced by global hidden auto-builds.

### 3. Do not treat derived absence as canonical failure
Derived thinness should stay downstream and degradable.

### 4. Do not add many new dashboards
The current docs favor strengthening the existing:
- `runtime_overview`
- `memory_overview`
- `failure_overview`

rather than dashboard sprawl.

### 5. Do not broaden into full file-content indexing
The current `0.9.0` file-work direction is metadata-oriented, not repository
content indexing.

---

## Release-facing success criteria

This plan is successful when all of the following are true.

### 1. Operator meaning is trustworthy
An operator can distinguish:
- expected summary absence
- visible interaction capture
- absent file-work capture
- absent derived layer downstream of canonical absence

without guessing.

### 2. Definitions are aligned
If the repository says “file-work memory items,” the same bounded semantics are
used across service, CLI, and Grafana.

### 3. Summary zeros are interpreted correctly
Operators understand that canonical summaries are not always expected under the
current narrow checkpoint-gated automation policy.

### 4. File-work gap becomes actionable
A zero file-work tile either:
- becomes non-zero through bounded implementation strengthening, or
- is explicitly documented as not yet broadly expected in the current milestone
  reality

### 5. Canonical-first posture remains intact
No dashboard or runbook wording implies that Grafana or the derived graph layer
has become the source of truth.

---

## Recommended next action

The next bounded slice should implement:

1. file-work observability-definition alignment
2. runbook/dashboard interpretation clarification
3. focused review of file-work metadata producers
4. explicit review of the default runtime exposure gap for file-oriented tool
   traffic

This is the smallest slice that improves operator trust without changing the
repository’s deeper product posture prematurely.

### Current follow-up note

A later investigation confirmed that this runtime exposure gap is real in the
current default stack and that the intended fix is a joint runtime-plus-rules
model:

- bounded file-work metadata extraction can exist in the interaction-memory
  producer
- but the running `ctxledger` server may still expose too few representative
  file-oriented producer paths
- and even when the path exists, resumability still depends on `.rules`
  requiring the agent to emit file-work records in the active work loop
- in that posture, live Grafana file-work counters can remain at zero even after
  producer-side logic is improved if either the runtime path or the agent
  recording discipline is missing

That means future remediation should explicitly decide and verify all of:

- expose a bounded file-oriented producer path in the default runtime
- require agents through `.rules` to record file-touching work in context
- confirm that recorded file-work remains searchable and linked to the active
  work loop for later context restoration