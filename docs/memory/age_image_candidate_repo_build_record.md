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
  - not yet implemented
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

## Recommendation

- keep as fallback

### Rationale

- the repository-owned build path is the safest technical fallback if no
  trustworthy prebuilt image can satisfy the constrained prototype's real needs
  cleanly
- it is especially attractive if pgvector compatibility and reproducibility are
  too uncertain in external candidates
- however, because it carries more implementation and maintenance burden, it
  should not automatically be the first choice if a strong prebuilt option exists

### Conditions for adoption

- condition 1:
  - no trustworthy prebuilt image cleanly satisfies AGE + PostgreSQL + pgvector
    expectations
- condition 2:
  - the repository is willing to own a small local/dev PostgreSQL build path
- condition 3:
  - the implementation remains explicitly scoped to the constrained prototype and
    optional overlay usage

### Next action

- compare this candidate directly against at least one serious prebuilt image
  candidate
- adopt this path if the prebuilt option fails the compatibility or confidence
  bar
- if adopted, implement it through an explicit optional Compose overlay while
  leaving the default stack unchanged

---

## Final Short Summary

- final read:
  - strong controlled fallback, possibly the best option if external images are
    too uncertain
- suitable for the constrained prototype:
  - yes
- recommended next step:
  - compare this candidate against one or more concrete prebuilt image
    candidates, then choose between operational simplicity and repository-owned
    control