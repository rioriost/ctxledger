# AGE-Capable Image Candidate Decision Record

## Purpose

This note records the investigation frame for one **concrete prebuilt**
AGE-capable PostgreSQL image candidate for the optional local/dev path used by
the current constrained `supports` prototype.

This record is intentionally concrete in structure but still incomplete in one
important way:

- the exact image name is still **to be determined**

That is intentional.

The purpose of this note is to fix the evaluation shape for the **first real
prebuilt candidate investigation** without pretending a suitable image has
already been confirmed.

It should be read together with:

- `docs/memory/age_image_selection_note.md`
- `docs/memory/age_image_selection_decision.md`
- `docs/memory/age_image_candidate_decision_record_template.md`
- `docs/memory/age_image_candidate_prebuilt_record.md`
- `docs/memory/age_docker_provisioning_plan.md`

This note is not a final adoption record.

It is a concrete investigation record for the next real prebuilt-image check.

---

## Candidate Summary

- candidate name:
  - `TBD concrete prebuilt AGE-capable PostgreSQL image`
- source:
  - `TBD`
- image or build reference:
  - `TBD`
- intended usage:
  - prebuilt image
- evaluation date:
  - 2026-03-23
- evaluator:
  - current `ctxledger` constrained AGE prototype planning pass

---

## Why This Record Exists

The repository already has:

- image-selection criteria
- a generic prebuilt-path record
- a repository-owned build fallback record
- a provisioning plan
- a provisional image-selection decision

What is still missing is:

- the **first actual concrete prebuilt candidate investigation**

This note exists so the next session can fill in one real image candidate rather
than continuing to reason only at the strategy level.

---

## Candidate Type

- category:
  - prebuilt image
- intended integration shape:
  - Compose overlay
- default stack impact:
  - none, if used only through an explicit AGE overlay
- optional-by-default preserved:
  - yes, if the base stack remains unchanged

---

## Current Investigation Status

- exact candidate chosen:
  - no
- image pinned:
  - no
- source verified:
  - no
- prototype-fit confidence:
  - low, until a real image is identified
- current overall status:
  - **needs investigation**

---

## Must-Verify Criteria for the First Concrete Candidate

The first real prebuilt image candidate should not be evaluated casually.

At minimum, it must be checked against all of the following:

1. real support for:
   - `LOAD 'age'`
2. PostgreSQL compatibility close enough to current repository assumptions
3. pgvector compatibility clean enough for current local/dev expectations
4. suitability for an explicit Compose overlay
5. reproducibility for another engineer
6. low enough blast radius against the unchanged default stack
7. compatibility with:
   - `ctxledger apply-schema`
   - `ctxledger age-graph-readiness`
   - `ctxledger bootstrap-age-graph`
   - runtime `age_prototype` introspection

---

## Evaluation Against Required Capabilities

### 1. Apache AGE availability

- expected support for `LOAD 'age'`:
  - unknown until a real candidate is selected
- confidence:
  - low
- notes:
  - this is the first hard gate
  - if the image cannot satisfy this cleanly, it should be rejected immediately

### 2. PostgreSQL compatibility

- expected compatibility with current repository assumptions:
  - unknown
- confidence:
  - low
- notes:
  - the candidate must be close enough to current PostgreSQL expectations to
    avoid unrelated churn in the constrained prototype slice

### 3. pgvector compatibility

- expected compatibility with current pgvector expectations:
  - unknown
- confidence:
  - low
- notes:
  - this is one of the most important practical checks
  - a candidate that supports AGE but breaks current vector expectations is weak

### 4. Overlay friendliness

- suitable for explicit optional Compose overlay:
  - likely, if the candidate is container-friendly and stable
- confidence:
  - medium
- notes:
  - this is usually easier than the extension compatibility checks
  - still needs verification once a real image is chosen

### 5. Reproducibility

- likely reproducible for another engineer:
  - unknown
- confidence:
  - low
- notes:
  - depends on source trust, version pinning, and startup simplicity

### 6. Limited blast radius

- likely to preserve unchanged default stack:
  - yes, if kept behind an explicit overlay
- confidence:
  - medium
- notes:
  - this depends more on repository usage discipline than on the image itself

---

## Operator / Repository Fit

### 1. Explicit bootstrap compatibility

- compatible with current explicit bootstrap command:
  - unknown
- confidence:
  - low
- notes:
  - must be proven by actually running:
    - `ctxledger bootstrap-age-graph`

### 2. Explicit readiness-check compatibility

- compatible with current readiness-check flow:
  - unknown
- confidence:
  - low
- notes:
  - must be proven by actually running:
    - `ctxledger age-graph-readiness`

### 3. Runtime introspection compatibility

- compatible with current runtime observability expectations:
  - likely
- confidence:
  - low
- notes:
  - should work if AGE enablement and readiness are visible through the current
    environment, but still needs actual validation

### 4. Documentation burden

- expected documentation complexity:
  - unknown
- notes:
  - depends on how many caveats the chosen image requires

### 5. Ongoing maintenance burden

- expected maintenance burden:
  - unknown
- notes:
  - lower than a repository-owned build if the image is strong
  - potentially higher operational ambiguity if the image is weakly maintained

---

## Required Candidate Discovery Fields

When a real prebuilt candidate is found, fill these fields before deciding
anything else:

- concrete image name:
- concrete image tag:
- source repository / publisher:
- PostgreSQL major version:
- stated AGE support:
- stated pgvector support:
- known setup caveats:
- expected local/dev use only:
  - yes / no / unknown

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

- low
- notes:
  - confidence remains low until a real image is selected and assessed
  - this record is intentionally the staging point for that assessment

---

## Investigation Questions for the Next Session

The next session should answer these explicitly for one real candidate:

1. What exact image name and tag are being proposed?
2. Does the candidate explicitly support Apache AGE in practice?
3. Does it coexist with pgvector cleanly enough for the repository’s current
   expectations?
4. Can it be used without changing the default relational-first Compose path?
5. Can it support:
   - schema application
   - readiness check
   - bootstrap
   - runtime introspection agreement
6. Is it trustworthy enough to adopt for local/dev constrained prototype work?
7. If not, is the repository-owned build path now clearly preferable?

---

## Risks

### Main risk 1
- description:
  - a candidate may appear promising but fail the real readiness/bootstrap path
- severity:
  - high
- mitigation:
  - require evaluation against the repository’s actual validation target, not
    only descriptive claims

### Main risk 2
- description:
  - a candidate may support AGE but not current vector expectations
- severity:
  - high
- mitigation:
  - treat pgvector compatibility as a first-class gate

### Main risk 3
- description:
  - a weak or poorly maintained image may reduce reproducibility
- severity:
  - medium
- mitigation:
  - prefer pinned, trustworthy sources and document the choice explicitly

---

## Unknowns / Open Questions

- open question 1:
  - what concrete prebuilt image should be evaluated first?
- open question 2:
  - does that candidate support both AGE and current vector expectations well
    enough?
- open question 3:
  - if a plausible candidate exists, is it trustworthy enough to prefer over the
    repository-owned build fallback?

---

## Comparison Notes

### Advantages of pursuing a concrete prebuilt candidate first

- advantage 1:
  - fastest possible route to a real graph-enabled local/dev validation path
- advantage 2:
  - potentially lowest implementation cost
- advantage 3:
  - fits the current provisional decision:
    - prebuilt path first, if credible

### Disadvantages / cautions

- disadvantage 1:
  - image quality is still unknown
- disadvantage 2:
  - extension compatibility is still unknown
- disadvantage 3:
  - this path is not adoptable until a real candidate is pinned and checked

### Relative ranking against the repository-owned build candidate

- better than:
  - repository-owned build path, if a strong concrete image exists
- worse than:
  - repository-owned build path, if image trust or compatibility remains unclear
- roughly equivalent to:
  - none yet, because no real candidate is pinned
- notes:
  - this record is intentionally incomplete until a concrete candidate is found

---

## Provisional Recommendation

- needs investigation before adoption

### Rationale

- the repository’s current provisional decision is to investigate a concrete
  prebuilt image first
- however, no exact candidate has yet been selected
- therefore this record should not claim adoption readiness prematurely

### Conditions for adoption

- condition 1:
  - a specific image name and tag are identified
- condition 2:
  - AGE support is credible and testable
- condition 3:
  - PostgreSQL + pgvector fit is acceptable for the constrained local/dev path
- condition 4:
  - the candidate plausibly supports the repository’s actual validation target

### Next action

- identify one serious concrete prebuilt AGE-capable PostgreSQL image candidate
- replace the `TBD` fields in this record
- then compare the completed record against:
  - `docs/memory/age_image_candidate_repo_build_record.md`

---

## Final Short Summary

- final read:
  - concrete prebuilt candidate investigation slot prepared, but still unfilled
- suitable for the constrained prototype:
  - maybe, pending real candidate selection
- recommended next step:
  - choose one real prebuilt image and complete this record before final image
    selection