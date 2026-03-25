# AGE-Capable Image Candidate Decision Record

## Purpose

This note records the evaluation of one candidate image strategy for the
optional AGE-capable Docker / development path used by the current constrained
`supports` prototype.

This record evaluates the **prebuilt image path**.

It should be read together with:

- `docs/memory/age_image_selection_note.md`
- `docs/memory/age_image_candidate_decision_record_template.md`
- `docs/memory/age_docker_provisioning_plan.md`

This note is intentionally narrow.

It is not a production deployment approval record.

It is not a broad graph platform decision.

It is only for deciding whether a prebuilt image path is a good fit for the
current constrained local/dev validation path.

---

## Candidate Summary

- candidate name:
  - prebuilt AGE-capable PostgreSQL image path
- source:
  - external prebuilt image candidate to be selected
- image or build reference:
  - not yet pinned
- intended usage:
  - prebuilt image
- evaluation date:
  - 2026-03-23
- evaluator:
  - current `ctxledger` prototype planning pass

---

## Candidate Type

- category:
  - prebuilt image
- intended integration shape:
  - Compose overlay
- default stack impact:
  - none, if used only through an explicit overlay
- optional-by-default preserved:
  - yes, if the base stack remains unchanged

---

## Evaluation Against Required Capabilities

### 1. Apache AGE availability

- expected support for `LOAD 'age'`:
  - yes, if the image is genuinely AGE-capable
- confidence:
  - medium
- notes:
  - this is the main reason to consider the candidate
  - it still requires actual verification against the repository’s readiness and
    bootstrap commands

### 2. PostgreSQL compatibility

- expected compatibility with current repository assumptions:
  - partial
- confidence:
  - medium
- notes:
  - compatibility depends on the PostgreSQL version and extension packaging used
    by the candidate image
  - the image must remain close enough to the current repository expectations to
    avoid unrelated database churn

### 3. pgvector compatibility

- expected compatibility with current pgvector expectations:
  - partial
- confidence:
  - low
- notes:
  - this is one of the main unresolved risks for the prebuilt path
  - a candidate that provides AGE but weakens or breaks current vector support
    would be a poor fit unless that tradeoff is made explicit and accepted

### 4. Overlay friendliness

- suitable for explicit optional Compose overlay:
  - yes
- confidence:
  - high
- notes:
  - this is the strongest advantage of the prebuilt path
  - if a good image exists, it fits naturally into `docker/docker-compose.age.yml`

### 5. Reproducibility

- likely reproducible for another engineer:
  - partial
- confidence:
  - medium
- notes:
  - reproducibility is good only if the image is pinned clearly and behaves
    consistently across environments
  - an unpinned or weakly maintained image would reduce confidence

### 6. Limited blast radius

- likely to preserve unchanged default stack:
  - yes
- confidence:
  - high
- notes:
  - as long as the image is used only via an explicit overlay, the base stack
    can stay relational-first and unchanged

---

## Operator / Repository Fit

### 1. Explicit bootstrap compatibility

- compatible with current explicit bootstrap command:
  - yes, in principle
- confidence:
  - medium
- notes:
  - this must be proven by actually running:
    - `ctxledger bootstrap-age-graph`

### 2. Explicit readiness-check compatibility

- compatible with current readiness-check flow:
  - yes, in principle
- confidence:
  - medium
- notes:
  - this must be proven by actually running:
    - `ctxledger age-graph-readiness`

### 3. Runtime introspection compatibility

- compatible with current runtime observability expectations:
  - yes
- confidence:
  - medium
- notes:
  - if the image satisfies AGE support cleanly, the current runtime
    introspection path should work without architectural changes

### 4. Documentation burden

- expected documentation complexity:
  - low to medium
- notes:
  - if the image is simple and trustworthy, docs are straightforward
  - if the image has caveats around extension behavior or setup order, burden
    increases

### 5. Ongoing maintenance burden

- expected maintenance burden:
  - medium
- notes:
  - less build maintenance than a repository-owned image
  - more dependency trust and upgrade risk from an external source

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

- medium
- notes:
  - confidence depends mainly on whether a trustworthy candidate exists that
    also preserves enough PostgreSQL + pgvector compatibility
  - the prebuilt strategy is attractive operationally, but still needs concrete
    candidate proof

---

## Risks

### Main risk 1
- description:
  - candidate image may advertise AGE support but fail the repository’s actual
    readiness/bootstrap flow
- severity:
  - high
- mitigation:
  - require validation against the current CLI readiness and bootstrap commands
    before adoption

### Main risk 2
- description:
  - candidate may not preserve current pgvector expectations cleanly
- severity:
  - high
- mitigation:
  - make pgvector compatibility a first-class adoption criterion rather than a
    follow-up surprise

### Main risk 3
- description:
  - candidate source quality or maintenance may be weak
- severity:
  - medium
- mitigation:
  - prefer a clearly maintained source and pin the chosen image explicitly in the
    eventual overlay

---

## Unknowns / Open Questions

- open question 1:
  - which concrete prebuilt image candidates are credible enough to evaluate?
- open question 2:
  - does the best candidate also support pgvector cleanly enough for the current
    repository expectations?
- open question 3:
  - does the candidate require any extra local/dev setup steps beyond the current
    prototype flow?

---

## Comparison Notes

### Advantages of this candidate

- advantage 1:
  - potentially the fastest path to a real graph-enabled local/dev overlay
- advantage 2:
  - keeps repository-owned Docker complexity lower if the image is good enough
- advantage 3:
  - fits naturally with the current explicit optional overlay strategy

### Disadvantages of this candidate

- disadvantage 1:
  - more uncertainty around extension compatibility
- disadvantage 2:
  - more trust placed in external image maintenance
- disadvantage 3:
  - pgvector + AGE coexistence may be ambiguous until proven

### Relative ranking against other candidates

- better than:
  - manual post-start installation flow
- worse than:
  - repository-owned build path, if external compatibility is weak or unclear
- roughly equivalent to:
  - repository-owned build path on implementation effort only if a very strong
    prebuilt candidate exists
- notes:
  - this candidate should be preferred only if it satisfies the prototype’s real
    validation target with low ambiguity

---

## Recommendation

- needs investigation

### Rationale

- the prebuilt path is the most attractive operationally if a trustworthy image
  exists
- however, the current decision should not adopt it blindly without a concrete
  candidate and explicit validation of:
  - AGE support
  - PostgreSQL compatibility
  - pgvector compatibility
  - overlay suitability

### Conditions for adoption

- condition 1:
  - identify a concrete candidate image and pin it explicitly
- condition 2:
  - confirm it can satisfy `LOAD 'age'` and the current readiness/bootstrap flow
- condition 3:
  - confirm it preserves current pgvector expectations cleanly enough for the
    graph-enabled prototype path

### Next action

- identify one or more concrete prebuilt AGE-capable PostgreSQL images
- evaluate each against this record
- compare them against the repository-owned build candidate before final
  selection

---

## Final Short Summary

- final read:
  - promising but still unproven
- suitable for the constrained prototype:
  - maybe
- recommended next step:
  - convert this generic prebuilt strategy record into one or more concrete
    image-specific records and compare them against the repository-owned build
    path