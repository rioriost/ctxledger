# AGE-Capable Docker / Dev Provisioning Plan for the Constrained `supports` Prototype

For the image-selection decision that should precede this provisioning slice, see:

- `docs/memory/age_image_selection_note.md`

## Purpose

This note defines the recommended plan for adding an **optional AGE-capable
Docker / development provisioning path** for the current constrained Apache AGE
prototype in `0.6.0`.

Its purpose is to close the main remaining operational gap between:

- a partially implemented constrained AGE prototype
- and a local/dev environment that can actually exercise that prototype in a
  graph-enabled state

This note is intentionally narrow.

It does **not** broaden the prototype boundary.

It does **not** change visible `memory_get_context` behavior.

It does **not** make AGE a default or mandatory dependency for ordinary local
development.

---

## Current Situation

The repository now already contains a meaningful constrained AGE prototype
surface, including:

- a narrow one-hop `supports` lookup boundary
- relational baseline implementations
- AGE capability and graph-readiness checks
- a PostgreSQL AGE-backed lookup path with explicit fallback
- service-layer adoption through a narrow lookup boundary
- explicit prototype controls:
  - `CTXLEDGER_DB_AGE_ENABLED`
  - `CTXLEDGER_DB_AGE_GRAPH_NAME`
- an explicit bootstrap command:
  - `ctxledger bootstrap-age-graph`
- a CLI readiness check:
  - `ctxledger age-graph-readiness`
- runtime introspection details through the debug runtime surface
- operator documentation, validation runbook, and observation template

That means the prototype is no longer blocked on conceptual shape.

The main remaining likely blocker is:

- the default local Docker PostgreSQL image may not actually provide Apache AGE

So the next operational need is clear:

- add an explicit, optional environment path that can make `age_available =
  true` in local/dev validation

---

## Problem Statement

The current default local stack is intentionally relational-first and should stay
that way by default.

However, the constrained AGE prototype cannot be validated end-to-end in a
graph-enabled environment unless local/dev provisioning can provide:

- PostgreSQL reachable by the current app/runtime
- Apache AGE installed and loadable
- a path for canonical schema application
- a path for explicit graph bootstrap and readiness validation

Without that, the most likely real validation outcome remains:

- `age_available = false`
- `age_graph_status = "age_unavailable"`

That degraded-path result is useful, but it does not validate the actual
graph-ready path.

---

## Primary Goal

Provide one **optional Docker/dev provisioning path** that allows the current
constrained prototype to reach a graph-enabled state in local or shared
development environments.

A successful result should make it possible to validate this sequence for real:

1. start an AGE-capable environment
2. apply canonical relational schema
3. run `ctxledger age-graph-readiness`
4. observe:
   - `age_available = true`
   - likely `age_graph_status = "graph_unavailable"` before bootstrap
5. run `ctxledger bootstrap-age-graph`
6. rerun readiness
7. observe:
   - `age_graph_status = "graph_ready"`

---

## Non-Goals

This slice should **not** attempt to do any of the following:

- replace the default relational-first Docker path
- make AGE mandatory for ordinary development
- introduce broad graph lifecycle automation
- change the canonical relational storage boundary
- broaden graph semantics beyond the constrained prototype
- redesign grouped response behavior
- introduce multi-hop traversal
- add graph-first ranking or planning behavior
- introduce production-grade graph operations guarantees

This is a provisioning slice for the current prototype, not a graph platform
rollout.

---

## Recommended Decision

The recommended approach is:

- **keep the default Docker path unchanged**
- **add an optional AGE-specific Docker overlay or variant**
- **treat AGE-capable local/dev provisioning as explicit opt-in**
- **preserve current fallback behavior and relational-first defaults**

In practical terms:

- the normal default stack should remain usable without AGE
- graph-enabled experimentation should use a separate clearly named path
- that path should be documented as being for the constrained prototype
- operator expectations should remain explicit and narrow

---

## Recommended Provisioning Shape

Before implementing this provisioning shape, the image-selection step should be
treated as explicit rather than implicit.

Use:

- `docs/memory/age_image_selection_note.md`
- `docs/memory/age_image_candidate_decision_record_template.md`

to decide whether the repository should rely on:

- a trustworthy prebuilt AGE-capable image
- or a repository-owned local/dev PostgreSQL image build path

The intended reading is:

- the image selection note defines the decision criteria
- the candidate template records the evaluation of each serious option

## Option A: Default authenticated `small` stack (preferred and now validated)

Recommended shape:

- treat the authenticated `small` stack as the canonical local/dev deployment
  path:
  - `docker/docker-compose.yml`
  - `docker/docker-compose.small-auth.yml`
- keep AGE within that default stack by:
  - using the repository-owned PostgreSQL image path directly in the base stack
  - enabling AGE in the application configuration by default
  - ensuring the `age` extension exists during startup
  - bootstrapping the default constrained graph during startup:
    - `ctxledger_memory`

This replaces the earlier optional overlay framing.

The repository no longer needs a separate AGE-specific Compose overlay for normal
local operator use.

### Why this is preferred

This option is preferred because it now provides all of the following in one
validated path:

- current default local simplicity
- authenticated HTTPS access
- Grafana enabled by default
- PostgreSQL 17 through the repository-owned AGE-capable image path
- AGE enabled by default
- automatic schema application
- automatic AGE extension setup
- automatic constrained graph bootstrap
- easier operator onboarding because the normal startup path is the graph-capable
  path

It also aligns with the validated current repository direction, where the
default `small` stack is the canonical local environment rather than one overlay
among several competing local startup patterns.

---

## Option B: Separate AGE overlay (no longer preferred)

This would mean keeping AGE behind a distinct Compose overlay instead of treating
it as part of the normal authenticated `small` stack.

### Why this is no longer preferred

This is no longer desirable because it would:

- reintroduce unnecessary operator branching for local startup
- make the validated default local path harder to explain
- preserve obsolete distinctions between "normal local stack" and
  "graph-capable local stack"
- add documentation and operational overhead without current benefit

The repository has now moved beyond that earlier provisional shape.

---

## Recommended Implementation Boundary

The provisioning slice should remain narrow and focused on environment
capability.

It should include only what is needed to make the current prototype locally
exercisable in the default authenticated `small` stack:

- an AGE-capable PostgreSQL image or Docker build path
- default-stack wiring through:
  - `docker/docker-compose.yml`
  - `docker/docker-compose.small-auth.yml`
- documentation for how to start the validated default stack
- compatibility with:
  - `ctxledger apply-schema`
  - `ctxledger age-graph-readiness`
  - `ctxledger bootstrap-age-graph`
- focused validation instructions for the default path

It should **not** include:

- broad new runtime behavior
- graph write-path redesign
- generalized graph synchronization tooling
- broader graph semantics
- service contract changes

---

## Expected Operator Flow After This Slice

The intended operator flow after this provisioning slice should be:

1. start the default authenticated `small` stack:
   - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build`
2. allow startup to:
   - apply the canonical schema
   - ensure the `age` extension exists
   - bootstrap the default constrained graph:
     - `ctxledger_memory`
   - prepare Grafana-facing observability database access
3. confirm:
   - `CTXLEDGER_DB_AGE_ENABLED=true`
   - `CTXLEDGER_DB_AGE_GRAPH_NAME=ctxledger_memory`
4. run:
   - `ctxledger age-graph-readiness`
5. inspect `/debug/runtime` if desired
6. use:
   - `ctxledger bootstrap-age-graph`
   only when the operator intentionally wants to rebuild the constrained graph
7. record the result using the validation observation template

This keeps the default graph-enabled path explicit and operationally
understandable while eliminating the now-obsolete separate overlay flow.

---

## Environment Requirements for the New Path

The AGE-capable provisioning path should satisfy these practical requirements:

### 1. AGE installed and loadable
The PostgreSQL environment must be able to satisfy:

- `LOAD 'age'`

and should support the current constrained graph path without ad hoc manual
package installation after container startup.

### 2. Canonical schema compatibility
The environment must still be compatible with:

- the existing canonical PostgreSQL schema
- pgvector support already used by the project where applicable

### 3. Explicit graph usage
The environment now enables the constrained AGE prototype by default in the
validated `small` stack.

That means the default local/dev path should carry:

- `CTXLEDGER_DB_AGE_ENABLED=true`
- `CTXLEDGER_DB_AGE_GRAPH_NAME=ctxledger_memory`

Even with that default, the broader prototype reading remains constrained:

- relational PostgreSQL tables remain canonical
- the AGE graph remains derived and rebuildable
- explicit bootstrap remains the operator-visible rebuild mechanism
- graph readiness
- explicit bootstrap

### 4. Safe degraded interpretation
If the overlay is not used, the default environment should still naturally
support the current degraded-path interpretation:

- relational-first behavior
- fallback-preserving prototype behavior
- no accidental hidden graph dependence

---

## Recommended Validation Target

A successful provisioning slice should allow this real validation sequence.

### Before bootstrap

Expected readiness shape:

```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_unavailable"
}
```

### After bootstrap

Expected readiness shape:

```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_ready"
}
```

### Bootstrap success output

Expected current shape:

```/dev/null/txt#L1-1
AGE graph bootstrap completed for 'ctxledger_memory' (memory_item nodes repopulated=..., supports edges repopulated=...).
```

### Runtime introspection

Expected `age_prototype` shape:

```/dev/null/json#L1-9
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "observability_routes": [
    "/debug/runtime",
    "/debug/routes",
    "/debug/tools"
  ],
  "age_available": true,
  "age_graph_status": "graph_ready"
}
```

---

## Acceptance Criteria

This provisioning slice is successful when all of the following are true:

1. the repository provides an explicit optional local/dev path for AGE-capable
   PostgreSQL
2. the default local stack remains unchanged and relational-first
3. `ctxledger age-graph-readiness` can report:
   - `age_available = true`
   in the AGE-enabled path
4. `ctxledger bootstrap-age-graph` can run in the AGE-enabled path
5. post-bootstrap readiness can report:
   - `graph_ready`
6. runtime introspection agrees with CLI readiness in the graph-enabled path
7. the docs explain when to use the AGE path and when not to
8. the new path is clearly documented as constrained prototype support rather
   than broad graph adoption

---

## Recommended Deliverables

The most likely deliverables for this slice are:

- one Docker Compose overlay or equivalent graph-enabled container path
- supporting image/build definition changes if needed
- README additions for the graph-enabled path
- validation runbook additions specific to the AGE-capable environment path
- one recorded validation observation using:
  - `docs/memory/age_prototype_validation_observation_template.md`

---

## Risks

### 1. Environment complexity creep
Adding AGE-capable provisioning can become much larger than intended.

Mitigation:
- keep the scope strictly local/dev and prototype-oriented
- avoid turning the slice into a full production graph deployment design

### 2. Default path confusion
Operators may think AGE is now mandatory.

Mitigation:
- keep the default stack unchanged
- document the AGE path as optional and prototype-only

### 3. Image compatibility issues
An AGE-capable PostgreSQL image may not align neatly with existing extensions or
assumptions.

Mitigation:
- validate compatibility with canonical schema application and current local/dev
  commands before broadening anything else

### 4. Overstating graph readiness
A graph-enabled environment can be mistaken for broad graph feature readiness.

Mitigation:
- keep validation criteria tied only to the constrained prototype
- continue documenting the narrow scope explicitly

---

## Recommended Documentation Reading After This Slice

Once the provisioning path exists, the operator reading flow should likely be:

1. `docs/memory/age_image_selection_note.md`
   - for the chosen AGE-capable image or image strategy
2. `docs/memory/age_image_candidate_decision_record_template.md`
   - for per-candidate evaluation records that support the selection decision
3. `README.md`
   - for entry-level setup guidance
4. `docs/memory/age_graph_population_bootstrap.md`
   - for bootstrap semantics
5. `docs/memory/age_prototype_validation_runbook.md`
   - for practical validation sequence
6. `docs/memory/age_prototype_validation_observation_template.md`
   - for recording the result

This keeps the setup story practical and explicit.

---

## Working Rule

Use this rule for the AGE-capable provisioning slice:

- **keep the default stack unchanged**
- **make the graph-enabled path explicit**
- **preserve optionality**
- **validate the constrained prototype, not broad graph semantics**
- **do not widen visible retrieval behavior**

This keeps the provisioning work aligned with the current prototype boundary.

---

## Decision Summary

The recommended next slice after the current constrained AGE prototype work is:

- add an **optional AGE-capable Docker / dev provisioning path**

The preferred form is:

- an explicit Docker Compose overlay or equivalent graph-enabled local/dev path

This slice should make it possible to validate the existing constrained
prototype in a real graph-enabled environment while preserving:

- relational canonical storage
- optional AGE adoption
- explicit bootstrap
- explicit readiness checking
- mandatory relational fallback
- unchanged visible retrieval semantics