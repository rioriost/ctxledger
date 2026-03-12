# v0.1.0 Implementation Plan Review and Task Inventory

## 1. Purpose

This document compares the current repository state against `docs/imple_plan_0.1.0.md` and records the remaining implementation gaps, ambiguities, and follow-up tasks.

It is intended to serve as:

- a handoff-friendly review artifact
- a short-term execution guide for the next development steps
- a plan-alignment checkpoint for `v0.1.0`

This review is based on the currently documented and visible repository state at the time of writing, especially:

- `docs/imple_plan_0.1.0.md`
- `README.md`
- `src/ctxledger/server.py`
- existing tests and operational docs

---

## 2. Review Summary

## 2.1 High-Level Assessment

The repository appears to be **substantially advanced** relative to the original implementation plan in several areas:

- PostgreSQL-backed workflow persistence
- workflow service implementation
- projection writer support
- HTTP runtime and debug/ops surfaces
- projection failure lifecycle handling
- documentation quality
- test coverage breadth

However, when evaluated strictly against the `v0.1.0` implementation plan, there are still **material unresolved items**.

The most important remaining gaps are:

1. **Required MCP resource surface is not confirmed as implemented**
2. **Plan/docs naming and implementation naming are inconsistent in at least one core workflow tool**
3. **Some acceptance criteria appear only partially evidenced by the current public runtime surface**

---

## 2.2 Overall Status by Category

### Strongly aligned or likely complete
- PostgreSQL schema and persistence baseline
- workflow service core
- Docker-based local deployment
- projection writer and projection-state handling
- memory subsystem as explicit stub/deferred surface
- health/readiness/debug operational support
- security/deployment/API documentation
- test suite presence and breadth

### Partially aligned
- MCP exposure for workflow control
- implementation-plan naming alignment
- acceptance-criteria traceability

### Likely incomplete or unverified
- required MCP resources
- resource-level test evidence
- full plan-to-runtime contract alignment

---

## 3. Method and Confidence Levels

This review classifies items into three buckets:

- **Confirmed aligned**  
  Current repository evidence strongly suggests the plan item is implemented or satisfied.

- **Partially aligned / needs validation**  
  There is evidence of related implementation, but the exact plan requirement is not yet fully confirmed.

- **Gap / likely unresolved**  
  Current evidence suggests the plan item is absent, mismatched, or still open.

Because this review is repository-state based rather than execution-audit based, some items should be validated with a direct runtime check before declaring final completion.

---

## 4. Confirmed Aligned Areas

## 4.1 Core workflow service exists

The implementation plan expects workflow control to be the primary completed layer in `v0.1.0`.

Current evidence indicates this is broadly true:

- `src/ctxledger/workflow/service.py` exists
- workflow persistence concepts are implemented
- resume/projection-related behavior is present
- tests such as:
  - `tests/test_workflow_service.py`
  - `tests/test_postgres_integration.py`
  - `tests/test_server.py`
  suggest substantial workflow behavior coverage

### Assessment
**Confirmed aligned**

---

## 4.2 Memory subsystem is explicitly stubbed/deferred

The plan allows memory features to remain stubbed or deferred in `v0.1.0`.

Current evidence:

- `src/ctxledger/memory/service.py` exists
- memory operations return explicit not-implemented behavior
- request/response shapes are defined
- this matches the intended architectural placeholder behavior

### Assessment
**Confirmed aligned**

---

## 4.3 PostgreSQL schema and persistence baseline exist

The plan requires PostgreSQL-backed canonical state, initialized tables, and durable persistence support.

Current evidence:

- `schemas/postgres.sql` is referenced by tests
- tests explicitly assert core workflow tables exist
- Docker Compose mounts schema bootstrap into Postgres init
- postgres-specific implementation and unit-of-work support exist
- persistence repositories are present

### Assessment
**Confirmed aligned**

---

## 4.4 Docker-based local deployment exists

The plan requires local Docker-based deployment support.

Current evidence:

- `docker/docker-compose.yml` exists
- includes:
  - `postgres`
  - `ctxledger`
  - environment configuration
  - schema bootstrap mount
  - persistent Postgres volume
  - exposed ports
  - healthcheck/dependency wiring

This strongly aligns with the deployment plan.

### Assessment
**Confirmed aligned**

---

## 4.5 Documentation deliverables are broadly present

The plan expected updates or creation of:

- `README.md`
- `docs/mcp-api.md`
- `docs/deployment.md`
- `docs/architecture.md`
- `docs/imple_plan_0.1.0.md`

Current evidence shows these files exist and have been actively maintained, with particularly detailed documentation around:

- API semantics
- deployment
- security
- projection lifecycle
- operational guidance

### Assessment
**Confirmed aligned**

---

## 4.6 Test layer exists and is non-trivial

The plan states `v0.1.0` should introduce a basic test layer and validate core workflow paths.

Current evidence:

- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_postgres_db.py`
- `tests/test_postgres_integration.py`
- `tests/test_projection_writer.py`
- `tests/test_server.py`
- `tests/test_workflow_service.py`

This exceeds the initial "no tests yet" assumption in the plan.

### Assessment
**Confirmed aligned**

---

## 5. Partially Aligned Areas

## 5.1 MCP workflow surface exists, but naming is inconsistent

The implementation plan requires the following MCP tools:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

The README also documents these names as workflow tools.

Current runtime registration evidence in `src/ctxledger/server.py` now shows stdio tool registrations for:

- `workflow_resume`
- `projection_failures_ignore`
- `projection_failures_resolve`
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

This now matches the plan and README naming for the resume workflow tool.

### Assessment
**Confirmed aligned**

### Follow-up note
Keep the public naming aligned as:

- HTTP route: `workflow_resume`
- stdio tool: `workflow_resume`

Internal Python method names such as `resume_workflow(...)` may remain implementation details.

---

## 5.2 Acceptance criteria likely satisfied internally, but not all are proven at the public surface

The plan acceptance criteria include public and behavioral expectations such as:

- workflow tools callable
- durable records
- reconstruction after restart
- complete closes workflow
- projection generation
- docs explain usage
- tests validate lifecycle

A number of these are strongly suggested by current code and tests.  
However, the public MCP surface evidence is incomplete for some required tools and resources.

### Assessment
**Partially aligned / needs validation**

### Follow-up task
Create a short acceptance-check matrix showing for each criterion:

- implemented
- tested
- publicly exposed
- documented

---

## 6. Gaps / Likely Unresolved Items

## 6.1 Required MCP tool surface is now implemented and naming is aligned

### Plan requirement
Required MCP tools in `v0.1.0`:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

### Current visible evidence
A concrete runtime audit of `src/ctxledger/server.py` now shows:

- HTTP handler registrations include:
  - `workflow_resume`
  - `workflow_closed_projection_failures`
  - `projection_failures_ignore`
  - `projection_failures_resolve`
  - optional debug handlers:
    - `runtime_introspection`
    - `runtime_routes`
    - `runtime_tools`
- stdio tool registrations include:
  - `workflow_resume`
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_complete`
  - `projection_failures_ignore`
  - `projection_failures_resolve`
  - `memory_remember_episode`
  - `memory_search`
  - `memory_get_context`

A follow-up audit of visible service-layer implementation and server-side tool-handler definitions shows:

- workflow service methods do exist for:
  - `register_workspace`
  - `start_workflow`
  - `create_checkpoint`
  - `complete_workflow`
- corresponding visible MCP tool-handler definitions are also present for:
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_complete`

This sharpens the current assessment:

- the previously missing workflow MCP operations are now exposed in the visible stdio runtime wiring
- the main remaining workflow-surface issue is no longer missing exposure for those four tools
- the remaining plan misalignment is concentrated in naming consistency around resume, plus unresolved resource support

The previously observed naming mismatch has now been resolved:

- HTTP route: `workflow_resume`
- stdio tool: `workflow_resume`

### Why this matters
The original workflow MCP exposure gap is now closed without leaving a split public name for the resume operation.

### Status
**Confirmed aligned**

### Remaining follow-up
Keep documentation, tests, and changelog entries consistent with the canonical public name:

- `workflow_resume`

---

## 6.2 Required MCP resources are not confirmed as implemented

### Plan requirement
Required resources:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

### Current visible evidence
These resources are documented in:

- `docs/imple_plan_0.1.0.md`
- `README.md`
- `docs/mcp-api.md`

However, a concrete grep-based implementation audit of the currently visible Python sources did not reveal evidence for:

- resource handler registration
- resource resolver layer
- `workspace://...` runtime wiring
- `memory://...` runtime wiring

No direct implementation evidence has yet been confirmed for:

- resource handler registration
- resource resolver layer
- tests for resource access
- runtime introspection including resources

### Why this matters
Resources are explicitly listed as required in the implementation plan, not optional.

### Status
**Gap / likely unresolved**

### Task
Confirm whether resource support exists.

If not:
- add resource registration and resolver implementation for:
  - `workspace://{workspace_id}/resume`
  - `workspace://{workspace_id}/workflow/{workflow_instance_id}`

If it does exist elsewhere:
- add explicit tests
- ensure docs accurately describe the implementation path

### Suggested priority
**Highest**

---

## 6.3 Public workflow tool naming is inconsistent across plan, README, and runtime

### Observed inconsistency
Plan and README emphasize:

- `workflow_resume`

Visible runtime registration shows:

- `resume_workflow`

### Why this matters
This is not a cosmetic issue. It affects:

- client expectations
- documentation correctness
- MCP compatibility surface
- acceptance criteria traceability
- change history clarity

### Status
**Gap / unresolved naming decision**

### Task
Choose one canonical public name and align:

- implementation
- tests
- README
- `docs/mcp-api.md`
- `docs/imple_plan_0.1.0.md` if needed
- changelog

### Suggested priority
**High**

---

## 6.4 Resource-related tests are not confirmed

The implementation plan explicitly calls out a test layer and prioritizes core workflow path validation.

Current tests strongly cover:

- workflow service
- server behavior
- projection writer
- postgres integration
- config
- CLI

But resource-specific tests are not yet confirmed.

### Status
**Gap / likely unresolved**

### Task
Add or confirm tests for:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

Suggested cases:

- happy path
- unknown workspace/workflow
- stable response shape
- canonical reconstruction semantics

### Suggested priority
**High**

---

## 6.5 Public MCP interface audit is incomplete

The repository contains significant implementation work, but the public interface appears to have evolved beyond the original plan, especially with:

- projection failure action tools
- HTTP operational endpoints
- debug/runtime introspection
- memory stubs
- docs that may be ahead of runtime wiring

This means the project likely needs a one-pass public interface audit.

### Status
**Gap / governance task**

### Task
Create a definitive matrix of:

- public tool names
- public resource names
- HTTP routes
- whether implemented
- whether tested
- whether documented

### Suggested priority
**Medium**

---

## 7. Task Inventory

## 7.1 Highest-Priority Tasks

### Task A — Reconcile the workflow MCP surface after core tool exposure work
Concrete runtime audit result:

- confirmed visible stdio tools:
  - `workflow_resume`
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_complete`
  - `projection_failures_ignore`
  - `projection_failures_resolve`
  - `memory_remember_episode`
  - `memory_search`
  - `memory_get_context`
- confirmed visible workflow service methods:
  - `register_workspace`
  - `start_workflow`
  - `create_checkpoint`
  - `complete_workflow`
- confirmed visible MCP tool-handler definitions for:
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_complete`

Interpretation:
- the previously missing plan-required workflow MCP tools now appear to be exposed
- the remaining workflow-surface gap is no longer basic MCP exposure for those four tools
- the remaining work is now centered on naming consistency and broader public-surface reconciliation

Next step:
- keep the new MCP workflow tools as part of the baseline
- shift focus from “missing workflow tool exposure” to “surface alignment and naming cleanup”

### Task B — Resolve `workflow_resume` vs `resume_workflow`
Concrete runtime audit result:

- confirmed visible HTTP route: `workflow_resume`
- confirmed visible stdio tool: `resume_workflow`

Next step:
- pick the canonical public name
- align all layers

### Task C — Confirm and implement required MCP resources
Concrete implementation audit result:

- no visible resource registration or resolver wiring was found in the inspected Python implementation
- no visible `workspace://...` or `memory://...` runtime wiring was found

Next step:
- confirm whether resource support exists outside the inspected surface
- if not, implement required MCP resources:
  - `workspace://{workspace_id}/resume`
  - `workspace://{workspace_id}/workflow/{workflow_instance_id}`

---

## 7.2 High-Priority Tasks

### Task D — Add/confirm tests for MCP resources
Add tests proving the required resource layer exists and behaves predictably.

### Task E — Produce a public surface matrix
Create a short reference document or table covering:

- MCP tools
- MCP resources
- HTTP routes
- debug endpoints
- memory stubs
- implementation status
- documentation status
- test status

### Task F — Reconcile README with actual runtime surface
Ensure `README.md` reflects what the runtime really exposes today.

---

## 7.3 Medium-Priority Tasks

### Task G — Acceptance criteria evidence table
Add a document or section mapping each acceptance criterion to repository evidence:

- implementation file
- test file
- documentation file

### Task H — Decide whether implementation plan should be revised
If the public surface intentionally changed from the original plan, update:

- `docs/imple_plan_0.1.0.md`
- or add a note explaining divergence

---

## 8. Proposed Execution Order

Recommended next sequence:

1. **Audit actual MCP tool registration**
2. **Resolve tool naming mismatch**
3. **Audit or implement MCP resources**
4. **Add missing resource tests**
5. **Reconcile docs with actual public surface**
6. **Create acceptance / surface matrix**
7. **Only then declare `v0.1.0` fully aligned with the plan**

---

## 9. Decision Notes for the Next Work Loop

## 9.1 What should not be re-opened unnecessarily

The following areas appear healthy enough that they should not be reworked unless a concrete bug is found:

- projection failure lifecycle docs/tests alignment
- security guidance for HTTP action routes
- deployment guidance for proxy/logging around action routes
- memory subsystem stub posture
- general PostgreSQL/docker baseline

## 9.2 What should be treated as the current main open question

The central question is now:

**Does the repository actually expose the plan-required MCP tools and resources, or has the implementation drifted into a different public surface that needs formal reconciliation?**

Current concrete audit findings sharpen that question:

- `workflow_resume` is visible as both an HTTP route and a stdio tool
- `workspace_register`, `workflow_start`, `workflow_checkpoint`, and `workflow_complete` are now visibly registered in the inspected stdio runtime wiring
- corresponding workflow service methods and visible MCP tool-handler definitions for those operations are present
- the previous workflow-tool exposure gap has therefore narrowed to naming/surface alignment rather than missing workflow-domain behavior
- no resource registration or `workspace://...` resolver wiring was visibly confirmed in the inspected implementation

That is the key blocker to declaring the `v0.1.0` implementation plan complete.

---

## 10. Short Conclusion

The current repository is not a minimal skeleton anymore; it contains substantial real implementation and documentation work.

But relative to `docs/imple_plan_0.1.0.md`, the following still need resolution:

- required MCP resource exposure
- required MCP resources remain the main unresolved surface item
- explicit public-surface alignment should be maintained as implementation evolves

Until those are resolved or formally reconciled, `v0.1.0` should be treated as **close, but not yet cleanly closed against the implementation plan**.

---

## 11. Recommended Next Action

Start from the concrete audit findings already established:

1. treat the currently confirmed stdio tool set as:
   - `workflow_resume`
   - `workspace_register`
   - `workflow_start`
   - `workflow_checkpoint`
   - `workflow_complete`
   - `projection_failures_ignore`
   - `projection_failures_resolve`
   - `memory_remember_episode`
   - `memory_search`
   - `memory_get_context`
2. treat the currently confirmed HTTP workflow/ops route set as including:
   - `workflow_resume`
   - `workflow_closed_projection_failures`
   - `projection_failures_ignore`
   - `projection_failures_resolve`
   - optional debug routes
3. treat the next unresolved public-surface question as:
   - whether resource support is actually implemented
4. treat resource wiring as unconfirmed and likely missing until direct implementation evidence is found
5. compare all of the above against:
   - `docs/imple_plan_0.1.0.md`
   - `README.md`
   - `docs/mcp-api.md`

Then convert the result directly into implementation tasks rather than continuing documentation-first work in the abstract.