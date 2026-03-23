# AGE-Capable Image Selection Decision for the Constrained `supports` Prototype

## Purpose

This note records the current **selection decision state** for choosing an
AGE-capable PostgreSQL image or image strategy for the optional local/dev path
used by the constrained Apache AGE prototype in `0.6.0`.

Its purpose is to turn the current image-selection work from a set of criteria
and candidate records into one concise decision note that:

- summarizes the current comparison state
- records the present provisional conclusion
- defines what still needs to be decided before implementation
- sets the next concrete action

This note is intentionally narrow.

It does **not** broaden the current prototype.

It does **not** commit the repository to broad graph adoption.

It does **not** change visible `memory_get_context` behavior.

It does **not** make AGE mandatory for the default stack.

---

## Related Notes

This decision should be read together with:

- `docs/memory/age_image_selection_note.md`
- `docs/memory/age_image_candidate_decision_record_template.md`
- `docs/memory/age_image_candidate_prebuilt_record.md`
- `docs/memory/age_image_candidate_prebuilt_concrete_record.md`
- `docs/memory/age_image_candidate_repo_build_record.md`
- `docs/memory/age_docker_provisioning_plan.md`

---

## Current Decision Question

What image strategy should the repository use for an **optional AGE-capable
Docker/dev path** that can exercise the current constrained prototype in a real
graph-enabled environment?

The candidate strategy categories currently under consideration are:

1. **prebuilt AGE-capable image path**
2. **repository-owned Docker build path**

The selection standard is not simply:

- “find any image that mentions AGE”

The selection standard is:

- support the constrained prototype’s real validation path
- preserve the unchanged default relational-first stack
- preserve optionality
- preserve explicit bootstrap/readiness workflow
- preserve current PostgreSQL expectations closely enough
- preserve pgvector expectations where feasible
- avoid unnecessary operational ambiguity

---

## Current Comparative Reading

## Candidate A: Prebuilt image path

Current reading:

- operationally attractive
- potentially the fastest route to a real graph-enabled local/dev overlay
- naturally compatible with the current explicit optional overlay model

The first concrete prebuilt candidate now identified is:

- `apache/age:dev_snapshot_master`

However, it is still **not yet ready for adoption** because the concrete
candidate has not yet been validated directly against the repository's actual
readiness/bootstrap/vector-fit expectations.

Current status:

- **needs investigation**

Main unresolved questions:

- does `apache/age:dev_snapshot_master` actually satisfy `LOAD 'age'` in a way
  that works with the current readiness/bootstrap flow?
- does it preserve current PostgreSQL expectations closely enough?
- does it preserve current pgvector expectations cleanly enough for the
  constrained prototype path?
- is it trustworthy and reproducible enough for local/dev use?

## Candidate B: Repository-owned Docker build path

Current reading:

- stronger controlled fallback
- better long-term reproducibility if external image confidence is weak
- better fit if explicit compatibility with PostgreSQL + AGE + pgvector must be
  owned directly by the repository

However, it also has a higher cost:

- more implementation effort
- more maintenance burden
- more image/build complexity owned by the repository

Current status:

- **keep as fallback**

This candidate should become the preferred implementation path if:

- no trustworthy prebuilt image satisfies the constrained prototype’s needs
  cleanly enough
- or prebuilt image compatibility with pgvector / current PostgreSQL assumptions
  remains too uncertain

---

## Current Provisional Decision

The current decision is:

- **treat the repository-owned build path as validated for the default `small`
  deployment**
- **treat that validated path as a PostgreSQL 17-based authenticated local stack
  built and owned by the repository**
- **treat the current preferred base-image assumption for `small` as:**
  - `postgres:17`
- **treat the current preferred extension-installation assumption for `small`
  as:**
  - Apache AGE source build during the derived image build
  - pgvector source build during the derived image build with portability-oriented
    build flags:
    - `make OPTFLAGS=""`
- **treat the authenticated default `small` stack as the canonical validated
  local/dev deployment path**
- **treat `large` as a separate future deployment pattern that is not yet
  implemented**
  - intended direction:
    - Azure Database for PostgreSQL
- **retain the identified concrete prebuilt AGE-capable image as a non-preferred
  investigation candidate**
  - `apache/age:dev_snapshot_master`
- **treat the prebuilt path as secondary unless it later proves clear enough on
  PostgreSQL + pgvector compatibility**

In short:

- **repository-owned PostgreSQL 17 validated default `small` stack first**
- **future `large` deployment later, as a separate implementation track**
- **concrete prebuilt path second, only if it later clears the compatibility
  bar**

This is the current best decision because the main unresolved blocker in the
prebuilt path is no longer abstract uncertainty alone.

It is specifically the lack of a clear pgvector compatibility story for the
current repository expectations.

At the same time, the current working assumption for the preferred path is now:

- the repository-owned PostgreSQL 17 image path now validates successfully for
  the default `small` stack
- AGE and pgvector both work on the validated PostgreSQL 17 path
- the current preferred base-image assumption is:
  - `postgres:17`
- the current preferred extension-installation assumption is:
  - Apache AGE source build against PostgreSQL 17 during image build
  - pgvector source build against PostgreSQL 17 during image build
  - with portability-oriented build flags:
    - `make OPTFLAGS=""`
- therefore the repository should treat the validated PostgreSQL 17
  repository-owned image path as the current default local/dev implementation
  basis

Promoting the repository-owned build path now better preserves:

- explicit control over extension compatibility
- explicit control over PostgreSQL 17 selection
- explicit control over the validated local/dev image build path
- reproducibility for local/dev validation
- a default authenticated `small` stack with Grafana and AGE already validated
- constrained prototype discipline without hidden environment risk

---

## Why This Is the Right Decision Now

### 1. The prototype is already far enough along to justify real environment validation

The repository already has:

- config-gated AGE controls
- readiness checks
- bootstrap command
- runtime introspection details
- operator guidance
- validation runbook and observation template
- provisioning plan

So the next meaningful question is not whether the prototype exists.

It is whether a graph-enabled environment can be provided simply and credibly.

### 2. A strong prebuilt image would still be the lowest-friction path, but it is not the strongest current fit

If a strong prebuilt image existed with clear support for:

- Apache AGE
- current PostgreSQL expectations
- current pgvector expectations

then it would likely provide:

- the smallest implementation slice
- the smallest disruption to the repository
- the clearest optional overlay path
- the fastest route to real graph-enabled validation

However, the first concrete candidate currently identified does not yet provide a
clear enough pgvector compatibility story to justify making the prebuilt path the
preferred implementation direction.

### 3. The repository-owned build path is now the safer preferred path

A repository-owned build path is attractive when:

- compatibility must be tightly controlled
- reproducibility matters more than convenience
- external image confidence is weak
- extension coexistence must be made explicit rather than assumed
- architecture fit, including arm64-oriented local/dev validation, must be
  proven rather than guessed

That is now the repository’s more credible current reading.

Although the repository-owned path increases maintenance scope, the current
evidence suggests that paying that extra cost is more disciplined than
continuing to treat the prebuilt path as the primary implementation direction
while pgvector compatibility remains unclear.

It also better fits the current working assumption that the preferred path
should target:

- PostgreSQL 18
- explicit AGE installation
- explicit pgvector installation
- an arm64-capable base image whose actual buildability is validated by the
  repository rather than assumed from external image claims

### 4. This preserves the current prototype discipline

The current milestone direction remains:

- relational first
- graph where justified
- explicit opt-in
- behavior preservation
- operational clarity over hidden magic

This validated decision preserves those principles while making the default
authenticated `small` stack the canonical local/dev deployment path.

---

## Decision State

Current state:

- **selection validated for the default `small` path**
- **repository-owned PostgreSQL 17 direction chosen for `small`**
- **`large` remains a separate future deployment pattern and is not yet
  implemented**
- **prebuilt path retained only as a secondary comparison record**

This note therefore records a **split decision**:

- validated now for:
  - the default authenticated `small` deployment
- still future-facing for:
  - the `large` deployment pattern

The current practical reading is:

- proceed with the repository-owned PostgreSQL 17 build path as the preferred
  implementation direction for `small`
- treat the authenticated default `small` stack as the canonical validated
  local/dev path
- treat `large` as a later implementation track rather than something implied by
  the validated `small` result
- keep the identified concrete prebuilt image candidate:
  - `apache/age:dev_snapshot_master`
  as a secondary comparison point or possible later simplification path
- only reopen the prebuilt-first decision if a concrete candidate demonstrates a
  clearer AGE + PostgreSQL + pgvector fit than the validated PostgreSQL 17
  repository-owned path

Only after that should the repository reconsider whether the final path should
shift back toward:

- prebuilt image path
- instead of the currently preferred repository-owned build path

---

## What Must Be True to Finalize the Prebuilt Path

The prebuilt path should be finalized only if a concrete candidate shows all of
the following with sufficient confidence:

1. supports `LOAD 'age'`
2. is compatible enough with the project’s PostgreSQL assumptions
3. preserves pgvector expectations cleanly enough for the constrained prototype
4. fits naturally into an explicit optional Compose overlay
5. is reproducible enough for another engineer to use without hidden setup drift
6. does not force changes to the default relational-first stack
7. makes the target validation path plausible:

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

If a concrete prebuilt candidate cannot satisfy that path with acceptable
confidence, the repository should choose the repository-owned build path.

---

## What Must Be True to Finalize the Repository-Owned Build Path

The repository-owned build path should now be treated as finalized for the
default `small` deployment because all of the following are now true under
current evidence:

- no stronger trustworthy prebuilt image has displaced it
- the PostgreSQL 17 repository-owned path has been validated end-to-end for the
  default local stack
- pgvector compatibility was proven only after aligning with the upstream
  portability-oriented build flags:
  - `make OPTFLAGS=""`
- the repository-owned path provides materially better explicitness and control
  for the constrained prototype at acceptable maintenance cost

The implementation should still remain narrow:

- local/dev focused
- default authenticated `small` stack focused
- no separate AGE overlay required for normal local use
- no broad graph platform claims

---

## Explicit Non-Decision

This note does **not** yet decide:

- the future `large` deployment implementation details
- any production graph provisioning standard
- any broader graph semantics

Those belong to the next slice after concrete candidate evaluation.

---

## Next Required Action

The next required action is:

- treat the repository-owned PostgreSQL 17 build candidate as the validated
  default `small` implementation path
- keep the build assumptions concrete and explicit:
  - PostgreSQL base:
    - `postgres:17`
  - Apache AGE source ref:
    - `PG17/v1.7.0-rc0`
  - pgvector source ref:
    - `v0.8.2`
  - pgvector portability-oriented build flags:
    - `make OPTFLAGS=""`
- retain the identified concrete prebuilt AGE-capable PostgreSQL image
  candidate:
  - `apache/age:dev_snapshot_master`
  as a secondary comparison record
- update that record only if new evidence materially improves its
  PostgreSQL + pgvector fit

The most practical next artifacts are now:

- one updated repository-owned build record aligned with the validated
  PostgreSQL 17 path
  - `docs/memory/age_image_candidate_repo_build_record.md`
- cleanup of older planning notes that still describe:
  - PostgreSQL 18 as the intended default
  - optional AGE overlays
- optionally one updated concrete prebuilt candidate record if new evidence
  warrants it

---

## Recommended Immediate Follow-Up

Use this sequence:

1. treat the validated PostgreSQL 17 repository-owned path as the preferred
   implementation candidate
2. update:
   - `docs/memory/age_image_candidate_repo_build_record.md`
   with the validated assumptions, especially:
   - confirm the preferred PostgreSQL 17 base-image path:
     - `postgres:17`
   - confirm the current Apache AGE source-build method
   - confirm the current pgvector source-build method and portability flags
3. keep `docs/memory/age_image_candidate_prebuilt_concrete_record.md` as the
   secondary comparison record for `apache/age:dev_snapshot_master`
4. update this note with the validated preferred-path reading
5. remove stale references to:
   - `docker/docker-compose.age.yml`
   as if it were still the normal implementation target

---

## Working Rule

Use this rule for the next step:

- **prefer the validated PostgreSQL 17 repository-owned path for the default
  `small` deployment**
- **treat the prebuilt path as secondary unless it materially improves the
  current validated result**
- **do not reintroduce an AGE overlay as the normal local path**
- **preserve constrained prototype boundaries**

---

## Decision Summary

Current decision status:

- **validated for the default `small` deployment on PostgreSQL 17**
- **not yet implemented for the future `large` deployment**
- **final enough for the current `small` local/dev path**
- **not final for the broader two-pattern deployment story**

Current provisional choice:

- **promote the repository-owned build path to the preferred implementation
  direction**
  - tracked in:
    - `docs/memory/age_image_candidate_repo_build_record.md`
  - currently read as:
    - arm64-capable PostgreSQL 18 base image
    - explicit Apache AGE installation
    - explicit pgvector installation
- **retain the identified concrete prebuilt AGE-capable image as the
  non-preferred comparison candidate**
  - `apache/age:dev_snapshot_master`
  - tracked in:
    - `docs/memory/age_image_candidate_prebuilt_concrete_record.md`

This is the smallest next decision that can move the repository toward a real
graph-enabled local/dev validation path without prematurely widening prototype
scope or repository maintenance burden.