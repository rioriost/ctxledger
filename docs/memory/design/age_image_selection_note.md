# AGE-Capable PostgreSQL Image Selection Note for the Constrained `supports` Prototype

For a reusable per-candidate evaluation format to use with this note, see:

- `docs/memory/age_image_candidate_decision_record_template.md`

## Purpose

This note records the selection criteria, decision frame, and recommended next
steps for choosing an **AGE-capable PostgreSQL image** for the current
constrained Apache AGE prototype in `0.6.0`.

Its purpose is not to broaden the prototype.

Its purpose is to make the next Docker/dev provisioning step explicit and
safer by avoiding an ad hoc image choice that later creates unnecessary
rework.

This note is intentionally narrow.

It does **not** define a production deployment standard.

It does **not** define a broad graph platform architecture.

It does **not** change the current constrained prototype boundary.

---

## Current Context

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
- an explicit readiness command:
  - `ctxledger age-graph-readiness`
- runtime introspection details through the debug runtime surface
- operator documentation, validation runbook, and validation observation template
- an AGE-capable Docker/dev provisioning plan

That means the prototype is no longer blocked on internal code shape.

The main likely remaining blocker is environmental:

- the current default local PostgreSQL image may not provide Apache AGE

So before implementing an optional graph-enabled Docker overlay, the repository
needs a clear image-selection reading.

---

## Problem Statement

The current Docker stack is intentionally relational-first and should stay that
way by default.

However, the constrained AGE prototype cannot be validated end-to-end in a real
graph-enabled local/dev environment unless the PostgreSQL image used by that
optional environment can support all of the following at once:

- PostgreSQL compatible with the project’s current expectations
- Apache AGE installed and loadable
- compatibility with the project’s current canonical schema bootstrap path
- compatibility with the project’s existing pgvector usage expectations
- a practical local/dev operator workflow
- explicit opt-in graph-enabled experimentation

Without an explicit image-selection decision, the next provisioning slice risks
becoming one of:

- blind image swapping
- local success but poor reproducibility
- extension incompatibility
- image drift that weakens the constrained prototype’s optionality model

---

## Selection Goal

Choose or define an image strategy that allows the repository to provide an
**optional AGE-capable Docker/dev path** while preserving all of the following:

- default stack remains unchanged
- relational-first local usage remains simple
- graph-enabled path remains explicit
- current constrained prototype behavior remains unchanged
- canonical relational schema remains authoritative
- fallback behavior remains mandatory when graph readiness is not satisfied

---

## Non-Goals

This selection note should **not** be used to justify any of the following:

- making AGE mandatory for all local development
- changing the default PostgreSQL image immediately
- broad graph adoption
- production-grade support guarantees
- multi-hop graph semantics
- graph-first retrieval semantics
- any visible `memory_get_context` redesign
- generalized graph infrastructure work unrelated to the constrained prototype

This note is only about selecting a viable image strategy for a local/dev
prototype path.

---

## Required Capabilities

Any candidate image or image strategy should satisfy the following baseline
requirements.

### 1. Apache AGE availability

The environment must be able to support:

- `LOAD 'age'`

and the current prototype’s AGE capability/readiness checks should be able to
reach:

- `age_available = true`

in that environment.

### 2. PostgreSQL compatibility

The image should be close enough to the project’s current PostgreSQL assumptions
that it does not force unrelated database redesign work.

At minimum, it should be suitable for:

- schema application
- current repository usage
- local/dev validation of the constrained graph-backed path

### 3. pgvector compatibility

The current project already uses pgvector-related behavior.

That means the selected image strategy should either:

- include pgvector support directly
- or provide a credible, clearly documented way to preserve the current vector
  support expectations in the graph-enabled path

A graph-enabled image that breaks the current vector path without a clear
replacement is a weak candidate.

### 4. Local/dev usability

The image should be practical for:

- local Docker Compose usage
- explicit graph-enabled validation
- repeatable operator/developer setup

It should not require fragile, manual post-start steps just to make AGE
basically usable.

### 5. Explicit optionality

The image strategy must support the current architectural reading that:

- AGE remains optional by default

That means the image should fit cleanly into an **overlay** or similarly explicit
opt-in path rather than pushing toward implicit default graph dependence.

---

## Preferred Selection Strategy

The preferred strategy is:

- keep the base stack unchanged
- add an **optional AGE-capable overlay**
- choose an image or build path specifically for that overlay

This preserves the current milestone discipline:

- relational first
- graph where justified
- explicit operational boundaries
- constrained experimentation
- no premature default dependency

---

## Candidate Strategy Types

The next slice will likely need to choose among one of these strategy types.

### Option A: Use a prebuilt PostgreSQL image that already includes AGE and needed extensions

Pros:

- fastest path if a suitable image exists
- lower implementation complexity in the repository
- easier local/dev operator flow
- good fit for an optional Docker Compose overlay

Cons:

- image availability/maintenance quality may vary
- compatibility with both AGE and pgvector may not be guaranteed
- may introduce trust or maintenance concerns if the source is weakly managed

### Option B: Build a project-specific PostgreSQL image for local/dev that installs AGE

Pros:

- higher control
- explicit repository-owned setup
- clearer compatibility story if done carefully
- easier to document and reproduce once stabilized

Cons:

- more initial work
- more image maintenance burden
- may require careful handling for pgvector + AGE coexistence

### Option C: Use a manual/local post-start install flow

Pros:

- low initial repository change

Cons:

- weakest reproducibility
- highest operator friction
- easiest to misconfigure
- bad fit for a constrained prototype meant to be explicitly testable

This is **not preferred** for the current repository direction.

---

## Preferred Choice

The preferred choice is generally:

- **Option A if a clearly suitable and trustworthy image exists**
- otherwise **Option B**

The non-preferred choice is:

- **Option C**

because it weakens the repository’s current push toward explicit, repeatable,
operator-readable prototype handling.

---

## Selection Criteria

Use the following criteria when choosing the image.

### Criterion 1: AGE actually works
The image must support the current prototype’s expected AGE behavior in practice,
not just in description.

Minimum expected evidence:

- `age_available = true`
- graph creation works
- current bootstrap command can run in principle

### Criterion 2: pgvector path is not silently broken
The graph-enabled local/dev path should not unexpectedly regress existing vector
support assumptions without being explicit about it.

Minimum expected evidence:

- current schema application still succeeds
- extension expectations remain understandable
- graph-enabled path does not accidentally make unrelated memory features worse

### Criterion 3: Overlay friendliness
The image should be easy to use in an optional Compose overlay such as:

- `docker/docker-compose.age.yml`

That means the image should support a model where:

- the default stack stays unchanged
- the graph-enabled path is activated only when explicitly requested

### Criterion 4: Reproducibility
The image choice should be easy for another engineer to understand and rerun.

Minimum expected evidence:

- startup path can be documented clearly
- validation runbook can be followed with low ambiguity
- no hidden manual environment drift is required

### Criterion 5: Limited blast radius
Choosing the image should not force unrelated repository changes.

If the image choice implies:

- changing the default stack
- broad schema redesign
- large config rewrites
- broad deployment assumptions

then it is likely a poor fit for the current prototype stage.

---

## Evaluation Questions

For each candidate image or build approach, answer these questions explicitly.

1. Does it provide Apache AGE in a way that supports `LOAD 'age'`?
2. Does it remain compatible with the current PostgreSQL major version
   expectations, or is the difference acceptable for the prototype?
3. Does it preserve or reasonably support pgvector expectations?
4. Can it be used via an explicit optional Compose overlay?
5. Can schema application still succeed cleanly?
6. Can `ctxledger age-graph-readiness` plausibly report:
   - `age_available = true`
7. Can `ctxledger bootstrap-age-graph` plausibly run after schema application?
8. Is the image easy enough to explain in README/operator docs?
9. Does choosing it preserve the current “optional constrained prototype”
   reading?
10. Would another engineer be able to reproduce the same path without informal
    setup knowledge?

---

## Minimum Acceptance Standard for the Chosen Image

The selected image strategy is good enough only if it makes the following real
validation target plausible.

### Before bootstrap

```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_unavailable"
}
```

### After bootstrap

```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_ready"
}
```

### Bootstrap output

```/dev/null/txt#L1-1
AGE graph bootstrap completed for 'ctxledger_memory' (memory_item nodes repopulated=..., supports edges repopulated=...).
```

### Runtime introspection

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

If an image strategy cannot plausibly support that path, it is not a good fit
for the current slice.

---

## Recommended Output of the Selection Step

Use the reusable candidate template:

- `docs/memory/age_image_candidate_decision_record_template.md`

to evaluate each serious image or image-strategy candidate before writing the
final selection summary.

The next selection step should produce one concise decision artifact that states:

- chosen image or image strategy
- why it was chosen
- whether it includes or preserves pgvector support
- whether it will be used via a Compose overlay
- what validation target it is expected to satisfy
- what tradeoffs remain

This can be a short follow-up note or folded directly into the provisioning
slice if the answer is clear enough.

---

## Risks

### Risk 1: False confidence from image description
An image may claim AGE support without actually fitting the repository’s
validation path.

Mitigation:

- judge candidates by the prototype’s real validation target, not by marketing
  description

### Risk 2: pgvector incompatibility
An AGE-capable path may accidentally weaken the project’s existing vector
assumptions.

Mitigation:

- include pgvector compatibility as a first-class selection criterion

### Risk 3: Default path confusion
A graph-enabled image path may be misread as the new default local environment.

Mitigation:

- keep selection framed around an explicit optional overlay

### Risk 4: Prototype overstatement
A successful local graph-enabled image can be mistaken for broader graph
readiness.

Mitigation:

- continue describing the result as a constrained optional prototype path only

---

## Recommended Near-Term Decision Rule

Use this rule for the next step:

- if a trustworthy prebuilt image satisfies AGE + PostgreSQL + pgvector needs
  cleanly enough for local/dev prototype work, use it in an optional overlay
- otherwise, build a repository-owned local/dev AGE-capable image
- do not adopt a manual install flow as the primary path

This keeps the next slice explicit and reproducible.

---

## Working Rule

Use this rule while selecting the image:

- **prefer explicit opt-in**
- **preserve the default stack**
- **require real AGE capability**
- **preserve current vector expectations where feasible**
- **optimize for constrained local/dev validation, not broad platform rollout**

This keeps image selection aligned with the current milestone boundary.

---

## Decision Summary

The repository now needs an explicit image-selection step before implementing the
optional AGE-capable Docker/dev path.

The correct selection standard is not “find any image with AGE.”

It is:

- choose an image or image strategy that supports the constrained prototype’s
  real validation path
- preserves explicit optionality
- does not silently destabilize current PostgreSQL/vector expectations
- fits cleanly into an optional graph-enabled overlay

The preferred implementation path after selection remains:

- keep the default stack unchanged
- add an explicit optional AGE-capable Docker/dev path
- validate the existing constrained prototype in that path

For the per-candidate evaluation format that should feed that decision, see:

- `docs/memory/age_image_candidate_decision_record_template.md`