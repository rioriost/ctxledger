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
  - `apache/age Docker Official / ASF-published prebuilt image path`
- source:
  - Docker Hub / Apache Software Foundation published image page
- image or build reference:
  - `apache/age:dev_snapshot_master`
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
  - yes
- image pinned:
  - partially
- source verified:
  - partially
- prototype-fit confidence:
  - low to medium, with pgvector compatibility now the main blocking uncertainty
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
  - yes
- confidence:
  - high
- notes:
  - the published image documentation explicitly describes Apache AGE as the image purpose
  - the published quick-start flow includes:
    - `CREATE EXTENSION age;`
    - `LOAD 'age';`
    - `SET search_path = ag_catalog, "$user", public;`
  - this passes the first hard gate at the documentation/packaging level

### 2. PostgreSQL compatibility

- expected compatibility with current repository assumptions:
  - partial
- confidence:
  - medium
- notes:
  - the published image is described as an Apache AGE image for PostgreSQL
  - the published documentation states AGE currently supports PostgreSQL versions
    11 through 18
  - this is promising for the repository's current PostgreSQL assumptions
  - however, the exact PostgreSQL version packaged by the selected tag still
    needs confirmation before adoption

### 3. pgvector compatibility

- expected compatibility with current pgvector expectations:
  - unknown to weak
- confidence:
  - low
- notes:
  - the current Docker Hub documentation reviewed for `apache/age` did not
    establish pgvector support
  - no evidence has yet been recorded that this candidate provides both AGE and
    pgvector in a way that fits the repository's current expectations
  - this is now the main practical blocker for treating the candidate as a
    preferred path
  - a candidate that supports AGE but does not clearly preserve current vector
    expectations should not be preferred over the repository-owned build path

### 4. Overlay friendliness

- suitable for explicit optional Compose overlay:
  - yes, in principle
- confidence:
  - medium
- notes:
  - the candidate is already a container image intended for direct `docker run`
    usage
  - this fits naturally with an explicit optional Compose overlay approach
  - still needs repository-local validation once wired into an overlay

### 5. Reproducibility

- likely reproducible for another engineer:
  - partial
- confidence:
  - medium
- notes:
  - the image is published on Docker Hub by the Apache Software Foundation and
    therefore has a stronger provenance story than an arbitrary third-party image
  - reproducibility still depends on pinning an exact tag and verifying
    repository-local setup compatibility

### 6. Limited blast radius

- likely to preserve unchanged default stack:
  - yes, if kept behind an explicit overlay
- confidence:
  - high
- notes:
  - this candidate can be kept fully opt-in by using it only in a dedicated AGE
    overlay path
  - that preserves the current unchanged relational-first default stack

---

## Operator / Repository Fit

### 1. Explicit bootstrap compatibility

- compatible with current explicit bootstrap command:
  - yes, in principle
- confidence:
  - medium
- notes:
  - the image documentation includes graph creation and Cypher usage patterns
    that align with the repository's bootstrap direction
  - must still be proven by actually running:
    - `ctxledger bootstrap-age-graph`

### 2. Explicit readiness-check compatibility

- compatible with current readiness-check flow:
  - yes, in principle
- confidence:
  - medium
- notes:
  - because the image is intended to expose AGE directly, it should be a good
    candidate for the repository's readiness-check flow
  - must still be proven by actually running:
    - `ctxledger age-graph-readiness`

### 3. Runtime introspection compatibility

- compatible with current runtime observability expectations:
  - likely
- confidence:
  - medium
- notes:
  - should work if the image satisfies the readiness/bootstrap path cleanly in
    the repository environment
  - still needs actual validation against the current debug/runtime surface

### 4. Documentation burden

- expected documentation complexity:
  - low to medium
- notes:
  - the image already has published Docker-oriented quick-start documentation
  - burden increases if pgvector or version-specific caveats must be explained
    separately in the repository docs

### 5. Ongoing maintenance burden

- expected maintenance burden:
  - medium
- notes:
  - lower than a repository-owned build if this image proves compatible enough
+  - still subject to external image/tag evolution and compatibility drift

---

## Required Candidate Discovery Fields

The first concrete candidate is now identified at a basic level:

- concrete image name:
  - `apache/age`
- concrete image tag:
  - `dev_snapshot_master`
- source repository / publisher:
  - Docker Hub / Apache Software Foundation
- PostgreSQL major version:
  - `TBD exact packaged version`
- stated AGE support:
  - yes
- stated pgvector support:
  - unknown
- known setup caveats:
  - extension support is documented, but pgvector coexistence is not yet
    established from the reviewed source
- expected local/dev use only:
  - yes

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

- low to medium
- notes:
  - confidence is higher than the generic prebuilt-path record because a
    concrete candidate has been identified
  - however, confidence is still materially limited by the lack of a clear
    pgvector compatibility story
  - the unresolved checks remain:
    - exact PostgreSQL version fit
    - pgvector compatibility in the repository's graph-enabled path

---

## Investigation Questions for the Next Session

The next session should answer these explicitly for `apache/age:dev_snapshot_master`:

1. What exact PostgreSQL version is packaged in the candidate tag?
2. Does the candidate satisfy `LOAD 'age'` cleanly in the repository's Docker/dev path?
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
  - a candidate may support AGE but not current vector expectations, leaving the
    repository with a graph-capable path that weakens an already-existing vector
    assumption
- severity:
  - high
- mitigation:
  - treat pgvector compatibility as a first-class adoption gate and prefer the
    repository-owned build path if that compatibility remains unclear

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
  - what exact PostgreSQL version is packaged by `apache/age:dev_snapshot_master`?
- open question 2:
  - does this candidate support both AGE and current vector expectations well
    enough?
- open question 3:
  - is this candidate trustworthy enough to prefer over the repository-owned
    build fallback once real repository-local validation is attempted?

---

## Comparison Notes

### Advantages of pursuing this concrete prebuilt candidate

- advantage 1:
  - published by the Apache Software Foundation, which is a materially stronger
    provenance signal than an arbitrary third-party image
- advantage 2:
  - the Docker Hub documentation already describes Docker-based AGE usage,
    including extension loading and graph creation
- advantage 3:
  - still useful as the first concrete check against the current prebuilt-path
    hypothesis, even if it may not end up being the preferred implementation path

### Disadvantages / cautions

- disadvantage 1:
  - pgvector compatibility is still unknown from the reviewed source
- disadvantage 2:
  - exact PostgreSQL version fit is still not confirmed
- disadvantage 3:
  - the candidate is still not adoptable until repository-local validation is
    performed

### Relative ranking against the repository-owned build candidate

- better than:
  - repository-owned build path, only if `apache/age:dev_snapshot_master` proves
    compatible enough for AGE + PostgreSQL + pgvector expectations
- worse than:
  - repository-owned build path, under the current evidence level because
    pgvector compatibility remains unclear
- roughly equivalent to:
  - none
- notes:
  - this candidate is now concrete enough to compare
  - however, under the current evidence, the repository-owned build path reads as
    the safer controlled implementation path

---

## Provisional Recommendation

- keep as non-preferred investigation candidate

### Rationale

- the repository’s current provisional decision was to investigate a concrete
  prebuilt image first
- `apache/age:dev_snapshot_master` is now the first concrete candidate entered
  into that flow
- however, current evidence does not establish a clear pgvector compatibility
  story
- because of that, this record should not be treated as adoption-ready and should
  not currently outrank the repository-owned build path

### Conditions for adoption

- condition 1:
  - `apache/age:dev_snapshot_master` or a better-pinned Apache-published tag is
    confirmed as the image actually to use
- condition 2:
  - AGE support is verified through the repository’s readiness/bootstrap flow
- condition 3:
  - PostgreSQL + pgvector fit is demonstrated clearly enough for the constrained
    local/dev path
- condition 4:
  - the candidate supports the repository’s actual validation target with
    acceptable confidence

### Next action

- confirm the exact PostgreSQL version and practical extension compatibility of
  `apache/age:dev_snapshot_master`
- explicitly decide whether pgvector uncertainty is acceptable
- if that uncertainty remains unresolved, prefer:
  - `docs/memory/age_image_candidate_repo_build_record.md`

---

## Final Short Summary

- final read:
  - first concrete prebuilt candidate identified, but currently downgraded by
    unresolved pgvector uncertainty
- suitable for the constrained prototype:
  - maybe, but not preferred under current evidence
- recommended next step:
  - validate `apache/age:dev_snapshot_master` against the repository’s actual
    readiness/bootstrap/vector-fit expectations
  - if pgvector compatibility remains unclear, prefer the repository-owned build
    path before final image selection