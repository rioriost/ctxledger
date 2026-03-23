# AGE-Capable Image Candidate Decision Record

## Purpose

This note records the evaluation of one candidate image strategy for the
optional AGE-capable Docker / development path used by the current constrained
`supports` prototype.

This record evaluates the **repository-owned Docker build path**.

It should be read together with:

- `docs/memory/age_image_selection_note.md`
- `docs/memory/age_image_candidate_decision_record_template.md`
- `docs/memory/age_docker_provisioning_plan.md`

This note is intentionally narrow.

It is not a production deployment approval record.

It is not a broad graph platform decision.

It is only for deciding whether a repository-owned local/dev image build path is
a good fit for the current constrained validation path.

---

## Candidate Summary

- candidate name:
  - repository-owned AGE-capable PostgreSQL image build path
- source:
  - repository-maintained Docker build defined inside `ctxledger`
- image or build reference:
  - repository-owned local/dev PostgreSQL image build
- intended usage:
  - repository-owned build
- evaluation date:
  - 2026-03-23
- evaluator:
  - current `ctxledger` prototype planning pass

---

## Candidate Type

- category:
  - repository-owned Docker build
- intended integration shape:
  - Compose overlay
- default stack impact:
  - none, if used only through an explicit overlay
- optional-by-default preserved:
  - yes

---

## Evaluation Against Required Capabilities

### 1. Apache AGE availability

- expected support for `LOAD 'age'`:
  - yes
- confidence:
  - medium to high
- notes:
  - this is one of the main advantages of the repository-owned build path
  - if the repository owns the build steps, AGE installation can be made
    explicit and reproducible for the constrained prototype

### 2. PostgreSQL compatibility

- expected compatibility with current repository assumptions:
  - yes, in principle
- confidence:
  - medium
- notes:
  - compatibility depends on how carefully the build stays aligned with the
    project's current PostgreSQL expectations
  - repository ownership gives more control than an external prebuilt image, but
    still requires careful implementation

### 3. pgvector compatibility

- expected compatibility with current pgvector expectations:
  - yes, in principle
- confidence:
  - medium
- notes:
  - this is one of the strongest arguments for the repository-owned build path
  - if the repository controls the image, it can explicitly preserve both AGE and
    pgvector expectations instead of hoping a third-party image already does

### 4. Overlay friendliness

- suitable for explicit optional Compose overlay:
  - yes
- confidence:
  - high
- notes:
  - this fits cleanly with the current recommendation to keep the default stack
    unchanged and add an opt-in graph-enabled path only through an overlay

### 5. Reproducibility

- likely reproducible for another engineer:
  - yes
- confidence:
  - high
- notes:
  - reproducibility is one of the strongest advantages of this candidate
  - once implemented, the repository can own the exact build path and document it
    clearly

### 6. Limited blast radius

- likely to preserve unchanged default stack:
  - yes
- confidence:
  - high
- notes:
  - as long as the image is introduced only through an explicit AGE overlay, the
    default local/dev path can remain relational-first and unchanged

---

## Operator / Repository Fit

### 1. Explicit bootstrap compatibility

- compatible with current explicit bootstrap command:
  - yes
- confidence:
  - high
- notes:
  - this candidate is a strong fit for the current explicit bootstrap model
  - the build can be designed specifically so `ctxledger bootstrap-age-graph`
    works in a graph-enabled local/dev environment

### 2. Explicit readiness-check compatibility

- compatible with current readiness-check flow:
  - yes
- confidence:
  - high
- notes:
  - the repository-owned path can be shaped directly around
    `ctxledger age-graph-readiness`

### 3. Runtime introspection compatibility

- compatible with current runtime observability expectations:
  - yes
- confidence:
  - high
- notes:
  - this candidate should work naturally with the current runtime
    `age_prototype` payload if AGE is provisioned correctly

### 4. Documentation burden

- expected documentation complexity:
  - medium
- notes:
  - documentation burden is higher than a very strong prebuilt image
  - however, it is still manageable and has the advantage of being fully under
    repository control

### 5. Ongoing maintenance burden

- expected maintenance burden:
  - medium to high
- notes:
  - this is the main cost of the repository-owned path
  - image maintenance, extension compatibility, and version drift become the
    repository's responsibility

---

## Expected Validation Path

### Before bootstrap target

```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_unavailable"
}
```

### After bootstrap target

```/dev/null/json#L1-6
{
  "age_enabled": true,
  "age_graph_name": "ctxledger_memory",
  "age_available": true,
  "age_graph_status": "graph_ready"
}
```

### Bootstrap success target

```/dev/null/txt#L1-1
AGE graph bootstrap completed for 'ctxledger_memory' (memory_item nodes repopulated=..., supports edges repopulated=...).
```

### Runtime introspection target

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

### Confidence this candidate can satisfy the target

- medium to high
- notes:
  - this candidate is more work up front, but it provides the strongest path to
    making the repository's actual validation target explicit and reproducible
  - confidence depends on keeping the build small, local/dev-focused, and aligned
    with the current constrained prototype only

---

## Risks

### Main risk 1
- description:
  - higher implementation and maintenance cost than a strong prebuilt image
- severity:
  - medium
- mitigation:
  - keep the scope strictly local/dev and constrained-prototype-focused
  - avoid turning the build into a broad PostgreSQL platform effort

### Main risk 2
- description:
  - repository-owned image may drift from upstream PostgreSQL/extension behavior
- severity:
  - medium
- mitigation:
  - pin versions explicitly and document extension expectations clearly

### Main risk 3
- description:
  - build complexity may exceed what is justified for the prototype stage
- severity:
  - medium
- mitigation:
  - prefer the simplest build that satisfies:
    - AGE support
    - pgvector support
    - canonical schema compatibility
    - explicit overlay usage

---

## Unknowns / Open Questions

- open question 1:
  - what is the smallest repository-owned build that can provide both AGE and
    current vector expectations cleanly?
- open question 2:
  - how much version pinning and extension setup will be needed to keep the path
    reproducible?
- open question 3:
  - is the additional maintenance burden justified compared with a strong
    trustworthy prebuilt image?

---

## Comparison Notes

### Advantages of this candidate

- advantage 1:
  - highest control over AGE + PostgreSQL + pgvector compatibility
- advantage 2:
  - best reproducibility if implemented carefully
- advantage 3:
  - best fit for the repository's preference for explicit, recoverable, and
    operator-readable prototype handling

### Disadvantages of this candidate

- disadvantage 1:
  - higher initial implementation cost
- disadvantage 2:
  - ongoing maintenance burden shifts into the repository
- disadvantage 3:
  - more build/packaging detail to own and document

### Relative ranking against other candidates

- better than:
  - manual post-start installation flow
  - weak or ambiguous prebuilt images
- worse than:
  - a clearly trustworthy prebuilt image that already satisfies AGE +
    PostgreSQL + pgvector needs with low ambiguity
- roughly equivalent to:
  - a strong prebuilt image on eventual capability, but not on maintenance cost
- notes:
  - this candidate becomes preferable when external image compatibility or trust
    is too uncertain

---

## Concrete Build Assumptions

### 1. Integration shape

- preferred implementation shape:
  - explicit optional Docker Compose overlay
- expected overlay file:
  - `docker/docker-compose.age.yml`
- expected default-stack impact:
  - none
- notes:
  - the default relational-first stack should remain unchanged
  - the AGE-capable path should be activated only for constrained prototype work

### 2. PostgreSQL base strategy

- preferred base strategy:
  - repository-owned PostgreSQL image based on an arm64-capable PostgreSQL 18
    base image, with pgvector and Apache AGE added explicitly during the derived
    image build
- exact base image:
  - `postgres:18`
- PostgreSQL version pinning strategy:
  - `18`
- notes:
  - the current working assumption is that both pgvector and Apache AGE support
    PostgreSQL 18
  - the build should use PostgreSQL 18 explicitly rather than inheriting version
    choice accidentally
  - the first preferred base-image assumption is the official PostgreSQL 18 image
    path:
    - `postgres:18`
  - arm64 support should still be treated as something to prove by actually
    building the derived image rather than assuming blindly

### 3. Apache AGE installation strategy

- preferred AGE strategy:
  - explicit installation in the repository-owned image build on top of the
    chosen arm64-capable PostgreSQL 18 base image
- installation mechanism:
  - add Apache AGE during the derived image build
  - preferred current mechanism:
    - source build against PostgreSQL 18 during image build
- notes:
  - the resulting image must support:
    - `CREATE EXTENSION age;`
    - `LOAD 'age';`
    - `SET search_path = ag_catalog, "$user", public;`
  - AGE support should be built into the image rather than relying on manual
    post-start installation
  - a source-build assumption is currently preferred because it makes the
    PostgreSQL 18 fit more explicit for the constrained local/dev path
  - arm64 compatibility still needs to be proven by actually building and
    validating the image

### 4. pgvector installation strategy

- preferred pgvector strategy:
  - explicit installation in the same repository-owned image build on top of the
    chosen arm64-capable PostgreSQL 18 base image
- installation mechanism:
  - add pgvector during the derived image build
  - preferred current mechanism:
    - source build against PostgreSQL 18 during image build
- notes:
  - this is one of the strongest reasons to prefer the repository-owned path
  - the graph-enabled path should preserve current vector expectations clearly
    enough for local/dev constrained prototype work
  - using the same general source-build assumption as AGE keeps the derived image
    story simpler and more explicit at the current stage
  - arm64 compatibility still needs to be proven by actually building and
    validating the image

### 5. Schema/bootstrap/readiness compatibility targets

- schema application compatibility:
  - required
- readiness command compatibility:
  - required
- bootstrap command compatibility:
  - required
- runtime introspection compatibility:
  - required
- notes:
  - the build should support:
    - `ctxledger apply-schema`
    - `ctxledger age-graph-readiness`
    - `ctxledger bootstrap-age-graph`
    - runtime `age_prototype` reporting through `/debug/runtime`

### 6. Build scope limits

- intended scope:
  - local/dev only
- non-goals:
  - production deployment standard
  - broad graph lifecycle automation
  - generalized PostgreSQL platform ownership
- notes:
  - the image should remain as small and explicit as possible
  - this build exists to support the constrained prototype, not broad graph
    adoption

---

## Recommendation

- preferred implementation path

### Rationale

- the repository-owned build path is now the safest and clearest implementation
  direction under current evidence
- it is especially attractive because the current working assumption is now:
  - both pgvector and Apache AGE support PostgreSQL 18
  - but arm64 support still needs to be proven in practice
- that makes a repository-owned image based on an arm64-capable PostgreSQL base
  image the clearest path for local/dev validation
- the added implementation and maintenance burden is acceptable at the current
  prototype stage because it buys explicit control over:
  - PostgreSQL 18 fit
  - arm64 base-image choice
  - AGE installation
  - pgvector installation
  - local/dev reproducibility

### Conditions for adoption

- condition 1:
  - current prebuilt evidence remains too weak on AGE + PostgreSQL + pgvector
    compatibility together, especially for the desired arm64-oriented path
- condition 2:
  - the repository is willing to own a small local/dev PostgreSQL build path
- condition 3:
  - the implementation remains explicitly scoped to the constrained prototype and
    optional overlay usage
- condition 4:
  - the resulting image is treated as a build-and-validate path rather than as an
    assumed arm64 success story until it is actually proven

### Next action

- refine this candidate from a strategic fallback into the concrete preferred
  local/dev implementation path
- use the concrete build assumptions above to make the remaining implementation
  details explicit:
  - confirm the official PostgreSQL 18 base-image path:
    - `postgres:18`
  - refine the exact Apache AGE source-build method
  - refine the exact pgvector source-build method
- then implement it through an explicit optional Compose overlay while leaving
  the default stack unchanged
- treat the first success criterion as:
  - the derived PostgreSQL 18 image builds and validates on the intended
    arm64-oriented path

---

## Final Short Summary

- final read:
  - preferred controlled implementation path under current evidence
- suitable for the constrained prototype:
  - yes
- recommended next step:
  - refine this record with concrete build assumptions and use it as the basis
    for the optional AGE-capable Docker/dev overlay