# Observability 0.4.0 Implementation Plan

## 1. Purpose

This document defines the implementation plan for the `0.4.0` observability milestone.

The goal of `0.4.0` is to improve operator visibility into the canonical state of `ctxledger` as a **Durable Workflow Runtime and Multi-Layer Memory** system.

This milestone intentionally prioritizes:

- workflow observability
- memory observability
- operator-facing CLI inspection
- optional deployable Grafana-based dashboard support

This milestone explicitly does **not** prioritize hierarchical retrieval as its primary scope.  
That work is now deferred to `0.5.0`.

---

## 2. Why this milestone exists

The current system already stores meaningful durable state in PostgreSQL, including:

- workspaces
- workflow instances
- attempts
- checkpoints
- verify reports
- episodes
- memory items
- memory embeddings
- operational failure state

At this stage, the bottleneck is no longer only persistence.  
The bottleneck is **operability**:

- can an operator tell whether workflows are being captured correctly?
- can an operator tell whether memory is accumulating correctly?
- can an operator tell whether embeddings are being generated and stored?
- can an operator tell whether failures are building up?
- can an operator inspect recent activity without querying PostgreSQL manually?

This plan addresses that gap.

---

## 3. Scope of 0.4.0

## 3.1 In scope

### CLI observability
Add read-only operator-facing CLI commands for inspecting canonical runtime state.

Initial target commands:

- `ctxledger stats`
- `ctxledger workflows`
- `ctxledger memory-stats`
- `ctxledger failures`

### Optional Grafana deployment support
Provide a lightweight dashboard deployment path using Grafana as an optional companion service.

Expected deliverables:

- Docker Compose overlay for Grafana
- PostgreSQL datasource setup guidance
- initial dashboard definitions or dashboard provisioning path
- operator documentation for local/internal deployment

### Documentation alignment
Update docs so that observability is described as the `0.4.0` focus and Grafana is the named optional dashboard path.

### Read-only operator safety
The observability surfaces introduced in `0.4.0` should be read-only and should not mutate canonical state.

---

## 3.2 Explicitly out of scope

The following should not be treated as `0.4.0` requirements:

- hierarchical memory retrieval
- hierarchical summaries as a first-class retrieval surface
- relation-aware traversal UX
- advanced memory graph exploration UI
- write-oriented operator UI
- replacing MCP with a browser-native workflow console
- fine-grained authorization model changes
- broad analytics warehouse features

These belong to later milestones, especially `0.5.0` and beyond.

---

## 4. Product outcomes

A successful `0.4.0` should let an operator answer the following quickly:

### Workflow state
- how many workspaces exist?
- how many workflows are running?
- how many workflows have completed?
- what are the most recently updated workflows?
- are checkpoints being recorded?
- are verify reports being recorded?

### Memory state
- how many episodes exist?
- how many memory items exist?
- how many embeddings exist?
- which provenance types are active?
- when was memory last updated?

### Failure state
- are operational failures accumulating?
- are projection-related failures still present?
- are there open failures requiring attention?
- what has recently failed?

### Activity state
- what changed most recently?
- is the system active right now?
- are workflows and memory evolving as expected?

---

## 5. Design principles

## 5.1 Canonical-first observability
All observability views should derive from PostgreSQL canonical state.

Do not treat:

- `.agent/`
- generated files
- projection artifacts

as the primary observability source.

## 5.2 Read-only by default
The `0.4.0` CLI and Grafana surfaces should be inspection-first, not mutation-first.

## 5.3 Lightweight deployment
The dashboard deployment path should be:

- optional
- container-friendly
- low-friction
- suitable for local/internal operator use

## 5.4 Honest scope
Do not present observability views as workflow-editing UIs or as a replacement for MCP tools.

## 5.5 Operator usefulness over feature breadth
A smaller set of high-signal views is better than a broad but confusing surface.

---

## 6. CLI plan

## 6.1 `ctxledger stats`

### Purpose
Return a compact high-level summary of canonical workflow and memory state.

### Initial target contents
- total workspaces
- workflow instances by status
- workflow attempts by status
- checkpoint count
- verify report count by status
- episode count
- memory item count
- memory embedding count
- failure counts
- latest activity timestamps

### Example output shape
```/dev/null/txt#L1-20
ctxledger stats

Workspaces:
- total: 40

Workflows:
- running: 28
- completed: 30
- failed: 0
- cancelled: 0

Attempts:
- running: 28
- succeeded: 30
- failed: 0
- cancelled: 0

Memory:
- episodes: 34
- memory_items: 24
- memory_embeddings: 3
```

### Notes
This command should be optimized for human-readable terminal output first.  
Structured output may be added later if useful.

---

## 6.2 `ctxledger workflows`

### Purpose
List recent workflows and their operational status.

### Initial target columns
- `workflow_instance_id`
- `workspace_id` or canonical-path hint
- `ticket_id`
- `workflow_status`
- latest checkpoint step
- latest verify status
- latest update timestamp

### Useful flags
- `--limit`
- `--status`
- `--workspace-id`
- `--ticket-id`

### Example output shape
```/dev/null/txt#L1-12
ctxledger workflows --limit 5

- 11111111-... [running]
  workspace=/Users/example/project-a
  ticket=FEATURE-123
  latest_step=implement_cli_stats
  verify_status=pending
  updated_at=2026-03-15T11:00:00+00:00
```

### Notes
This command is intended to make workflow inspection possible without using SQL or a client-side MCP workflow.

---

## 6.3 `ctxledger memory-stats`

### Purpose
Expose canonical memory accumulation state.

### Initial target contents
- episode count
- memory item count
- memory embedding count
- memory relation count
- memory item provenance breakdown
- recent memory activity timestamps

### Useful breakdowns
- `episode`
- `workflow_complete_auto`
- `explicit`
- `derived`
- `imported`

### Example output shape
```/dev/null/txt#L1-14
ctxledger memory-stats

Counts:
- episodes: 34
- memory_items: 24
- memory_embeddings: 3
- memory_relations: 0

Provenance:
- episode: 22
- workflow_complete_auto: 2
- explicit: 0
- derived: 0
- imported: 0
```

---

## 6.4 `ctxledger failures`

### Purpose
List recent failures and their current lifecycle state.

### Initial target contents
- failure scope/type where applicable
- projection failure state if still present in schema/runtime
- `open / resolved / ignored`
- target path if relevant
- error code
- error summary
- occurred/resolved times
- retry count

### Useful flags
- `--limit`
- `--status`
- `--open-only`

### Notes
Even if projection becomes less central to the long-term product direction, the existing canonical failure records are still useful operational evidence and should remain inspectable during the transition.

---

## 6.5 CLI output policy

For `0.4.0`, CLI outputs should be:

- concise
- readable in plain terminals
- stable enough for operator use
- explicit about “no data” states

CLI outputs should avoid:

- raw SQL-oriented formatting
- overly nested JSON by default
- ambiguous empty responses

Optional future enhancement:
- `--json` structured output mode

This is useful, but not required for initial `0.4.0`.

---

## 7. Grafana plan

## 7.1 Why Grafana

Grafana is the preferred optional dashboard choice because it is:

- lightweight enough for internal deployment
- easy to run in a container
- compatible with PostgreSQL as a datasource
- strong for count, status, and time-based dashboards
- lower implementation cost than building a custom Web UI first

Grafana should be treated as the initial `0.4.0` dashboard path, not as a permanent exclusivity decision for all future UI work.

---

## 7.2 Deployment shape

### Expected topology
- `postgres`
- `ctxledger`
- optional `grafana`

### Deployment style
- Docker Compose overlay
- separate from the base runtime stack
- easy to enable or omit

### Candidate file
- `docker/docker-compose.observability.yml`

### Initial responsibilities
- run Grafana
- connect to PostgreSQL
- expose dashboard UI for local/internal operator inspection
- provision datasource and initial dashboards where practical

---

## 7.3 Grafana datasource model

Primary datasource:

- PostgreSQL

The dashboard should query canonical tables directly or through carefully chosen SQL queries.

Potential future option:
- expose a smaller observability-oriented SQL view layer
- but not required for initial `0.4.0`

---

## 7.4 Initial Grafana dashboard set

### Dashboard 1: Runtime overview
Panels:
- total workspaces
- workflows by status
- attempts by status
- checkpoints total
- verify reports by status
- recent activity timestamps

### Dashboard 2: Memory overview
Panels:
- episodes total
- memory items total
- embeddings total
- memory relations total
- provenance breakdown
- recent memory activity

### Dashboard 3: Failure overview
Panels:
- open failures
- resolved failures
- ignored failures
- recent failure timeline
- top recent error messages

### Dashboard 4: Workflow activity
Panels:
- workflows created over time
- checkpoints created over time
- verify reports created over time
- running workflow count trend

---

## 7.5 Dashboard query style

For initial `0.4.0`, queries should favor:

- simple aggregate SQL
- explicit filters
- stable column aliases
- low operational surprise

Examples of useful query types:
- `count(*)`
- grouped counts by status
- max timestamp per table
- recent ordered rows
- grouped provenance counts

Avoid in `0.4.0`:
- deeply clever SQL
- query logic that obscures operator understanding
- excessive dependence on future schema changes

---

## 7.6 Access model

Grafana is optional and primarily intended for:

- local/internal operator visibility
- deployment verification
- lightweight operational dashboards

It should not be treated as:
- a public customer UI
- the canonical mutation interface
- a replacement for MCP

### Access guidance
- keep behind the same internal/proxy discipline as other operational surfaces
- do not default to broad public exposure
- document credentials and deployment expectations clearly

---

## 8. Documentation plan

The following documentation should align with the `0.4.0` observability milestone:

- `README.md`
- `docs/roadmap.md`
- `docs/deployment.md`
- `docs/mcp-api.md`
- `docs/architecture.md` if observability sections need expansion
- `docs/CHANGELOG.md` if implementation lands in subsequent commits

Potential new docs:
- `docs/observability.md`
- `docs/grafana_operator_runbook.md`

Not all are required immediately, but operator deployment guidance for Grafana is likely worth adding once implementation begins.

---

## 9. Implementation sequence

## Phase 1 — CLI summary surfaces
Implement:

- `ctxledger stats`
- `ctxledger workflows`
- `ctxledger memory-stats`

Goal:
- immediate operator value
- low implementation risk
- direct use of canonical DB state

## Phase 2 — failure inspection
Implement:

- `ctxledger failures`

Goal:
- make operational drift/failure accumulation visible
- reduce need for direct DB inspection

## Phase 3 — Grafana deployment support
Add:

- Compose overlay
- datasource config guidance
- dashboard provisioning path
- initial dashboards

Goal:
- lightweight visual operator dashboard

## Phase 4 — docs and release hardening
- document usage examples
- define expected deployment path
- confirm observability claims match shipped functionality

---

## 10. Validation plan

## 10.1 CLI validation
For each new CLI command:
- verify command works against a real PostgreSQL-backed environment
- verify human-readable output is useful
- verify empty-state behavior is explicit
- add unit tests for formatting where practical
- add integration tests for real DB-backed summary correctness where practical

## 10.2 Grafana validation
- verify container starts successfully
- verify datasource can connect to PostgreSQL
- verify initial dashboards render
- verify representative queries work against realistic local data
- verify dashboard setup remains optional and does not affect base runtime startup

## 10.3 Scope validation
Before calling `0.4.0` done, confirm:
- observability claims are true in docs
- Grafana is actually deployable, not merely mentioned
- CLI covers workflow + memory + failure inspection at a useful level

---

## 11. Risks

## 11.1 Scope creep into a full custom UI
Risk:
- `0.4.0` grows into a bespoke application dashboard

Mitigation:
- keep Grafana as the named optional dashboard path
- keep UI work read-only
- avoid custom frontend work unless clearly justified

## 11.2 Ambiguous operator semantics
Risk:
- dashboard numbers become confusing or misleading

Mitigation:
- prefer simple aggregate definitions
- document what each count means
- align CLI and dashboard terminology

## 11.3 Coupling to unstable schema details
Risk:
- dashboards break as schema evolves

Mitigation:
- use conservative queries
- keep dashboard definitions versioned with the repo
- consider small compatibility adjustments alongside schema changes

## 11.4 Overclaiming observability coverage
Risk:
- docs say “full observability” when only a subset exists

Mitigation:
- describe `0.4.0` as lightweight operator-facing observability
- keep claims specific:
  - CLI inspection
  - Grafana dashboard deployment
  - canonical workflow/memory visibility

---

## 12. Success criteria

`0.4.0` should be considered successful when:

- operators can inspect workflow state from the CLI
- operators can inspect memory state from the CLI
- operators can inspect recent failure state from the CLI
- Grafana can be deployed as an optional containerized dashboard
- Grafana dashboards expose useful workflow/memory/failure metrics from PostgreSQL
- docs clearly describe the observability scope
- no hierarchical-retrieval claims are accidentally pulled back into `0.4.0`

---

## 13. Relationship to 0.5.0

This observability work should make later hierarchical retrieval easier, not harder.

`0.5.0` can then build on:
- better operational confidence
- clearer runtime visibility
- stronger understanding of actual workflow/memory usage patterns
- existing durable counts and activity signals

`0.4.0` improves the ability to see the system.  
`0.5.0` should improve the ability to retrieve knowledge from it.

---

## 14. Recommended next concrete work items

1. define CLI command UX and exact output fields
2. implement shared DB-backed summary queries
3. add CLI tests
4. add Grafana Compose overlay
5. define first dashboard JSON/provisioning path
6. write operator runbook for Grafana deployment
7. verify end-to-end against realistic local data