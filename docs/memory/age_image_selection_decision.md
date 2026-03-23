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

However, it is still **not yet ready for adoption** because a concrete trusted
candidate image has not been pinned and evaluated directly.

Current status:

- **needs investigation**

Main unresolved questions:

- which specific prebuilt image is credible enough to evaluate?
- does it actually satisfy `LOAD 'age'` in a way that works with the current
  readiness/bootstrap flow?
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

The current provisional decision is:

- **do not select the repository-owned build path yet**
- **do not implement the AGE-capable Docker overlay yet**
- **first identify and evaluate at least one concrete prebuilt AGE-capable image**
- **keep the repository-owned build path as the fallback if the prebuilt option
  fails the compatibility/confidence bar**

In short:

- **prebuilt path first, if credible**
- **repository-owned build second, if needed**

This is the current best decision because it balances:

- operational simplicity
- explicit optionality
- limited blast radius
- and effort discipline

without prematurely committing the repository to maintaining a custom local/dev
PostgreSQL image before it is clearly necessary.

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

### 2. A strong prebuilt image would be the lowest-friction path

If a strong prebuilt image exists, it would likely provide:

- the smallest implementation slice
- the smallest disruption to the repository
- the clearest optional overlay path
- the fastest route to real graph-enabled validation

So it makes sense to check that path first.

### 3. The repository-owned build path is valuable, but should remain a fallback until needed

A repository-owned build path is attractive when:

- compatibility must be tightly controlled
- reproducibility matters more than convenience
- external image confidence is weak

But it also increases maintenance scope.

At the current stage, that extra cost should only be paid if the prebuilt path
fails the actual selection criteria.

### 4. This preserves the current prototype discipline

The current milestone direction remains:

- relational first
- graph where justified
- explicit opt-in
- behavior preservation
- operational clarity over hidden magic

This provisional decision preserves those principles.

---

## Decision State

Current state:

- **selection not final**
- **provisional direction chosen**
- **next comparison narrowed**

This note therefore records a **gated decision**, not a final adoption.

The gate is:

- identify and assess one or more concrete prebuilt image candidates

Only after that should the final decision be made between:

- prebuilt image path
- repository-owned build path

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

The repository-owned build path should be finalized if one or more of these are
true:

- no trustworthy prebuilt image passes the required criteria
- prebuilt image compatibility with pgvector is too weak or unclear
- prebuilt image behavior is too ambiguous for reproducible local/dev use
- a repository-owned path provides materially better explicitness and control for
  the constrained prototype at acceptable maintenance cost

If this path is chosen, the implementation should still remain narrow:

- local/dev focused
- optional overlay only
- no change to default stack
- no broad graph platform claims

---

## Explicit Non-Decision

This note does **not** yet decide:

- the exact image name
- the exact Docker overlay contents
- the exact Dockerfile/build path
- any production graph provisioning standard
- any broader graph semantics

Those belong to the next slice after concrete candidate evaluation.

---

## Next Required Action

The next required action is:

- choose at least one concrete prebuilt AGE-capable PostgreSQL image candidate
- evaluate it using:
  - `docs/memory/age_image_candidate_decision_record_template.md`

If useful, also refine the repository-owned build candidate with more concrete
build assumptions.

The most practical next artifacts are:

- one concrete prebuilt candidate record
  - `docs/memory/age_image_candidate_prebuilt_concrete_record.md`
- optionally one refined repository-owned build record
- then a final image-selection update to this note

---

## Recommended Immediate Follow-Up

Use this sequence:

1. identify one serious concrete prebuilt candidate
2. fill:
   - `docs/memory/age_image_candidate_prebuilt_concrete_record.md`
3. compare it against the current repository-owned build record
4. update this note with a final selection
5. only then implement:
   - `docker/docker-compose.age.yml`

---

## Working Rule

Use this rule for the next step:

- **prefer a concrete prebuilt candidate if it is trustworthy and compatible**
- **fall back to a repository-owned build if the prebuilt path is too uncertain**
- **do not implement the AGE overlay before image selection is explicit**
- **keep the default stack unchanged**
- **preserve constrained prototype boundaries**

---

## Decision Summary

Current decision status:

- **not final**
- **provisional path selected**

Current provisional choice:

- **investigate a concrete prebuilt AGE-capable image first**
  - tracked in:
    - `docs/memory/age_image_candidate_prebuilt_concrete_record.md`
- **retain repository-owned build as the controlled fallback**

This is the smallest next decision that can move the repository toward a real
graph-enabled local/dev validation path without prematurely widening prototype
scope or repository maintenance burden.