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

### Initial scaffold build findings

- validation date:
  - 2026-03-23
- validation scope:
  - first bounded Docker build attempts for the repository-owned PostgreSQL 18
    derived image scaffold
- result:
  - successful PostgreSQL 18-derived image build with concrete compatibility
    findings captured along the way
- notes:
  - the first build attempt failed immediately because the initially chosen AGE
    ref:
    - `v1.5.0`
    - does not exist as a cloneable branch/tag in the Apache AGE repository for
      the intended PostgreSQL 18 path
  - that finding led to an immediate correction of the scaffold assumption:
    - use:
      - `PG18/v1.7.0-rc0`
    - as the current PostgreSQL 18-oriented AGE source ref
  - after updating the scaffold to that AGE ref, the build progressed into the
    Apache AGE compilation step on top of:
    - `postgres:18`
    - with:
      - `postgresql-server-dev-18`
  - the next bounded validation passes exposed two concrete missing AGE
    build-tool dependencies:
    - `flex`
    - required to generate:
      - `src/backend/parser/ag_scanner.c`
    - `bison`
    - required to generate:
      - `src/backend/parser/cypher_gram.c`
  - those findings mean the PostgreSQL 18 AGE source-build path needs parser
    generator packages in addition to the general extension build toolchain
  - after adding:
    - `flex`
    - `bison`
    - the bounded build progressed through the AGE stage and advanced into the
      pgvector build stage
  - the first pgvector scaffold ref:
    - `v0.8.0`
    - then failed to compile against PostgreSQL 18 because
      `src/hnswvacuum.c` calls:
      - `vacuum_delay_point`
      - with too few arguments for the PostgreSQL 18 signature
  - that finding confirmed the repository should treat pgvector compatibility as
    its own explicit PostgreSQL 18 validation question rather than assuming the
    first pin was sufficient
  - after updating the scaffold to:
    - `v0.8.2`
    - the derived image build completed successfully
  - this means the current repository-owned path has now demonstrated a working
    PostgreSQL 18-derived image build with:
    - Apache AGE:
      - `PG18/v1.7.0-rc0`
    - pgvector:
      - `v0.8.2`
    - parser generators:
      - `flex`
      - `bison`
  - the current remaining work is no longer image-build completion itself
  - the remaining validation surface is now runtime-oriented:
    - PostgreSQL 18 container startup/data-layout compatibility
    - extension creation/loading
    - schema compatibility
    - readiness/bootstrap behavior
    - runtime `age_prototype` inspection
  - the first runtime validation attempt exposed a concrete PostgreSQL 18
    startup/layout blocker:
    - the container does not become healthy because PostgreSQL 18 reports data
      at:
      - `/var/lib/postgresql/data`
      - as an unused mount/volume
  - this blocker appears before extension creation/loading checks and should be
    treated as a Compose/runtime-layout issue rather than an image-build issue
  - the current repository learning is that PostgreSQL 18 runtime layout
    expectations differ materially from the earlier default-stack mount shape
  - the most important immediate lessons are:
    - exact source refs matter materially for this path and must be treated as
      repository-owned compatibility inputs, not placeholders
    - PostgreSQL 18 compatibility must be proven independently for both AGE and
      pgvector rather than inferred from one extension succeeding

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

### Main risk 4
- description:
  - the chosen Apache AGE source ref may compile far enough to look plausible but
    still fail or stall before a usable install is produced on PostgreSQL 18
- severity:
  - medium
- mitigation:
  - treat bounded build attempts as the decision mechanism
  - record each ref/package adjustment explicitly
  - do not treat PostgreSQL 18 compatibility as proven until the derived image
    finishes building and the installed extension can be exercised

### Main risk 5
- description:
  - the repository-owned AGE build may require additional parser-generation
    dependencies beyond the initially assumed generic PostgreSQL extension
    toolchain
- severity:
  - medium
- mitigation:
  - keep recording concrete missing-tool findings from bounded builds
  - include the required parser generators explicitly in the Dockerfile/toolchain
    assumptions
  - avoid treating the package list as complete until AGE build/install finishes
    successfully

### Main risk 6
- description:
  - future pgvector ref changes may reintroduce PostgreSQL 18 incompatibility
    even though the current repository-owned image build now succeeds
- severity:
  - medium
- mitigation:
  - treat pgvector source compatibility as an independent validation question
  - keep the current working compatible pin explicit:
    - `v0.8.2`
  - record concrete PostgreSQL 18 compile failures before changing refs
  - prefer a ref with demonstrated PostgreSQL 18 compatibility rather than
    assuming a newer or different pin is sufficient

### Main risk 7
- description:
  - the PostgreSQL 18 runtime container may still fail to initialize cleanly even
    after a successful derived image build because the overlay's volume/data-path
    assumptions do not yet match PostgreSQL 18's runtime layout expectations
- severity:
  - medium
- mitigation:
  - treat PostgreSQL 18 startup/layout behavior as a separate validation slice
  - record the exact runtime complaint before changing the overlay again
  - prefer the smallest Compose/runtime adjustment that removes the
    `/var/lib/postgresql/data` unused-mount complaint and allows clean
    initialization

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
- open question 4:
  - does the current PostgreSQL 18-oriented AGE ref:
    - `PG18/v1.7.0-rc0`
    - continue to complete successfully in the derived image build on the
      intended arm64-oriented path?
- open question 5:
  - does the current pgvector ref:
    - `v0.8.2`
    - continue to build/install cleanly on the same PostgreSQL 18-derived image
      path on the intended arm64-oriented path?
- open question 6:
  - what is the minimal PostgreSQL 18 Compose/runtime configuration that allows
    the container to initialize cleanly without the reported unused-mount data
    complaint at:
    - `/var/lib/postgresql/data`
- open question 7:
  - after the PostgreSQL 18 runtime layout issue is resolved, can the resulting
    environment satisfy:
    - `CREATE EXTENSION age;`
    - `LOAD 'age';`
    - `CREATE EXTENSION vector;`
- open question 8:
  - after the PostgreSQL 18 runtime layout issue is resolved, does the resulting
    stack remain compatible with:
    - `ctxledger apply-schema`
    - `ctxledger age-graph-readiness`
    - `ctxledger bootstrap-age-graph`
    - runtime `age_prototype` inspection?

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
  - current scaffold source ref after first build finding:
    - `PG18/v1.7.0-rc0`
  - concrete source-build method:
    - install the PostgreSQL 18 server development headers and normal image-build
      toolchain packages required for an extension build
    - include parser generator tools required by the AGE build:
      - `flex`
      - `bison`
    - clone or fetch a pinned Apache AGE source release or commit during the
      image build
    - build AGE against the PostgreSQL 18 installation using the extension's
      standard PGXS-oriented build/install flow:
      - `make`
      - `make install`
    - place the resulting shared library and extension SQL/control files into the
      PostgreSQL 18 extension directories inside the derived image
- notes:
  - the resulting image must support:
    - `CREATE EXTENSION age;`
    - `LOAD 'age';`
    - `SET search_path = ag_catalog, "$user", public;`
  - AGE support should be built into the image rather than relying on manual
    post-start installation
  - a source-build assumption is currently preferred because it makes the
    PostgreSQL 18 fit more explicit for the constrained local/dev path
  - this should be treated as a normal PostgreSQL extension build inside the
    image rather than as post-start runtime provisioning
  - the Docker scaffold has now produced one concrete source-ref finding:
    - `v1.5.0`
    - should not be used for the PostgreSQL 18 path
    - `PG18/v1.7.0-rc0`
    - is the current better-fit scaffold ref because it at least reaches active
      compilation on the PostgreSQL 18-derived image
  - the Docker scaffold has also produced two concrete build-dependency findings:
    - `flex`
    - needed for AGE scanner generation
    - `bison`
    - needed for AGE grammar generation
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
  - concrete source-build method:
    - install the PostgreSQL 18 server development headers and normal image-build
      toolchain packages required for an extension build
    - clone or fetch a pinned pgvector source release or commit during the image
      build
    - build pgvector against the PostgreSQL 18 installation using the
      extension's standard PGXS-oriented build/install flow:
      - `make`
      - `make install`
    - place the resulting shared library and extension SQL/control files into the
      PostgreSQL 18 extension directories inside the derived image
- notes:
  - this is one of the strongest reasons to prefer the repository-owned path
  - the graph-enabled path should preserve current vector expectations clearly
    enough for local/dev constrained prototype work
  - using the same general source-build assumption as AGE keeps the derived image
    story simpler and more explicit at the current stage
  - this should preserve the ability to run `CREATE EXTENSION vector;` during
    schema setup on the same derived PostgreSQL 18 image
  - the first Docker scaffold ref:
    - `v0.8.0`
    - should now be treated as an invalid PostgreSQL 18 pin for this path
  - the first bounded PostgreSQL 18 build pass reached a concrete incompatibility
    in pgvector:
    - `src/hnswvacuum.c`
    - fails because:
      - `vacuum_delay_point`
      - is called with too few arguments for PostgreSQL 18
  - the current Docker scaffold ref is now:
    - `v0.8.2`
  - `v0.8.2` has now completed build/install successfully in the same derived
    PostgreSQL 18 image path
  - this means the repository now has a concrete working pgvector pin for the
    current image-build slice, while runtime validation still remains
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

- continue this candidate as the concrete preferred local/dev implementation path
- use the current implementation basis:
  - the official PostgreSQL 18 base-image path:
    - `postgres:18`
  - the current better-fit Apache AGE scaffold ref:
    - `PG18/v1.7.0-rc0`
  - the pinned pgvector scaffold ref:
    - `v0.8.0`
- keep the default stack unchanged while validating the explicit optional Compose
  overlay path
- treat the current image-build success as established with:
  - the now-identified AGE parser-generation dependencies included:
    - `flex`
    - `bison`
  - Apache AGE:
    - `PG18/v1.7.0-rc0`
  - pgvector:
    - `v0.8.2`
- then validate in this order:
  - PostgreSQL 18 runtime startup/layout compatibility
  - AGE install/load behavior
  - pgvector install behavior
  - schema/bootstrap/readiness compatibility on the resulting stack

---

## Final Short Summary

- final read:
  - preferred controlled implementation path under current evidence
- suitable for the constrained prototype:
  - yes
- recommended next step:
  - use this updated record, including the now-successful PostgreSQL 18-derived
    image build findings and the newly identified runtime data-layout blocker, as
    the basis for the next narrow runtime validation pass on the optional
    AGE-capable Docker/dev overlay