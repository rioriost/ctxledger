# Test Suite Split and Coverage Improvement 0.5.5 Plan

## 1. Purpose

This document defines the implementation plan for the `0.5.5` milestone.

The goal of `0.5.5` is to improve the maintainability and confidence level of the test suite by:

- splitting oversized files under `tests/`
- keeping individual test files reviewable and easier to navigate
- increasing coverage in under-tested or weakly asserted areas
- preserving current behavior while making future changes safer

This milestone is primarily a **test-structure and quality** release.

It is not intended to introduce broad product-surface changes.

---

## 2. Milestone goals

`0.5.5` focuses on two concrete outcomes.

### 2.1 Test file size control

The current test suite contains several files that have grown well beyond a maintainable size.

For this milestone, the working guideline is:

- target roughly **2000 lines or less per test file**

This is a maintainability heuristic, not a hard parser-enforced limit.

The point is to keep files:

- understandable in one sitting
- easier to review in diffs
- easier to search and navigate
- less likely to accumulate unrelated concerns

### 2.2 Coverage improvement

The suite already has strong overall coverage, but high total coverage does not guarantee that all important behaviors are equally protected.

This milestone therefore also targets:

- stronger coverage in weak or recently changed areas
- more meaningful assertions around edge cases and failures
- better protection for integration boundaries and regression-prone paths
- improved confidence when refactoring internal code

---

## 3. Why this milestone exists

The repository currently has broad automated coverage and a large amount of implementation surface area across:

- CLI behavior
- configuration loading
- MCP handlers and module structure
- HTTP/server behavior
- workflow services
- PostgreSQL repositories and helpers
- PostgreSQL integration paths

That breadth is good, but it also creates pressure on the test suite.

Several files under `tests/` have become large enough that they now carry maintainability cost:

- related scenarios are hard to locate quickly
- helper logic and assertions become buried
- unrelated changes land in the same file
- review scope becomes noisy
- future extraction work becomes riskier

At the same time, recent releases have involved reliability and cleanup work where regression protection matters.

`0.5.5` exists to improve the shape of the test suite before more feature and refactoring work continues.

---

## 4. Current-state snapshot

Based on the current repository state, the largest test files include:

- `tests/test_coverage_targets.py` — roughly `9700+` lines
- `tests/test_postgres_integration.py` — roughly `3400+` lines
- `tests/test_server.py` — roughly `3200+` lines
- `tests/test_workflow_service.py` — roughly `2600+` lines

There are also several files approaching the same risk zone:

- `tests/test_postgres_db.py` — roughly `1800+` lines
- `tests/test_mcp_tool_handlers.py` — roughly `1600+` lines
- `tests/test_cli.py` — roughly `1500+` lines

This confirms that the milestone should prioritize a responsibility-based reorganization of `tests/` rather than ad hoc file splitting.

---

## 5. Primary objective

Restructure the test suite so that tests are grouped by responsibility first, with oversized files then dissolved into those responsibility-aligned locations, while also improving coverage where it materially reduces regression risk.

The intended result is:

- responsibility-oriented test layout
- smaller and better-scoped test files
- clearer ownership of test concerns
- preserved test behavior and intent
- better targeted regression protection
- easier future maintenance

---

## 6. Scope

## 6.1 In scope

### Responsibility-based test reorganization
Reorganize `tests/` around stable subsystem and responsibility boundaries first, then split large files by moving their contents into those destinations.

### Coverage improvement
Add or strengthen tests in weakly protected behaviors, especially around:

- failure handling
- edge cases
- state transitions
- serialization and response shaping
- integration-path assumptions
- regressions exposed by recent cleanup/refactoring work

### Shared test helper cleanup
Where useful, introduce or improve shared fixtures, builders, or helpers so that split files remain readable and do not duplicate excessive setup.

### Naming and layout cleanup
Adopt a test file naming and grouping pattern that makes the suite easier to navigate.

### Validation and regression checking
Ensure that split files and new coverage preserve current suite behavior and do not accidentally weaken protection.

---

## 6.2 Out of scope

Unless required for correctness, `0.5.5` should not become:

- a broad rewrite of application code
- a major test-framework migration
- a large semantic redesign of the product
- a restructuring of `src/` unrelated to testability
- a pursuit of arbitrary coverage percentage at the expense of test quality
- a mass conversion of explicit tests into overly generic parametrized meta-tests
- a cleanup of every moderately large test file regardless of value

---

## 7. Success criteria

`0.5.5` should be considered successful when:

- oversized files in `tests/` have been split into clearer units
- the biggest files are no longer carrying multiple loosely related domains
- new test organization is understandable without hidden conventions
- targeted coverage has been added in meaningful gaps
- focused and full-suite validation pass
- coverage remains healthy and ideally improves
- the resulting layout makes future work easier rather than more abstract

---

## 8. Guiding principles

## 8.1 Split by behavior, not by arbitrary chunks

Do not split a file into `part1`, `part2`, or similarly opaque fragments.

Prefer groupings that express intent, such as:

- command family
- endpoint family
- repository behavior group
- workflow lifecycle stage
- happy path vs error path
- read API vs mutation API
- transport contract vs internal helper parity

## 8.2 Preserve readability

Smaller files are useful only if they remain clear.

Avoid introducing excessive indirection through helpers that hide important setup or assertions.

## 8.3 Keep assertions meaningful

Coverage improvement should not mean adding shallow tests that only execute lines.

Prefer tests that prove:

- outputs are correct
- errors are explicit
- state changes are correct
- boundaries behave as intended

## 8.4 Prefer stable responsibility seams

When reorganizing tests, align file and directory boundaries with stable subsystem responsibilities so the organization lasts beyond this milestone.

## 8.5 Rehome tests before inventing new catch-all buckets

If a test in a large file clearly belongs to an existing or newly defined subsystem area, move it there rather than creating another miscellaneous holding area.

## 8.6 Minimize churn where possible

Do not rename or move everything for cosmetic symmetry.

Prioritize the files that are oversized or structurally confusing first.

## 8.7 Protect recent and risky areas

Favor new tests in areas that have recently changed, historically regressed, or have subtle branching behavior.

---

## 9. File splitting strategy

## 9.1 General approach

For each oversized or structurally mixed test file:

1. identify the major responsibility groups already present
2. map each group to its long-term destination in the `tests/` layout
3. identify file-local helpers and fixtures
4. decide which helpers should remain local, which should move to domain-local support, and which should move to shared support
5. move tests into responsibility-named files and directories
6. keep imports and fixture usage explicit
7. run focused validation after each reorganization step
8. only then move on to the next large file

This should be done incrementally rather than through one large mechanical rewrite.

---

## 9.2 Priority order

Recommended reorganization priority:

1. define the target responsibility-based `tests/` layout
2. dissolve `tests/test_coverage_targets.py` into responsibility-owned destinations
3. reorganize `tests/test_server.py`, `tests/test_workflow_service.py`, and `tests/test_postgres_integration.py` into the same structure
4. review adjacent files that should move with them to avoid responsibility overlap

Priority candidates for that work:

- `tests/test_coverage_targets.py`
- `tests/test_server.py`
- `tests/test_workflow_service.py`
- `tests/test_postgres_integration.py`
- `tests/test_mcp_tool_handlers.py`
- `tests/test_mcp_modules.py`
- `tests/test_cli.py`
- `tests/test_postgres_db.py`
- `tests/test_postgres_helpers.py`

The goal is not only to reduce line counts, but to ensure that responsibility for each subsystem is readable from the test layout itself.

---

## 10. Proposed target structure

The exact final layout can evolve during implementation, but the split should follow a coherent pattern.

## 10.1 Responsibility-based target layout

The exact final layout can evolve during implementation, but the suite should move toward a structure where subsystem responsibility is visible from the directory tree.

Recommended direction:

- `tests/cli/`
- `tests/config/`
- `tests/runtime/`
- `tests/http/`
- `tests/server/`
- `tests/mcp/`
- `tests/workflow/`
- `tests/memory/`
- `tests/postgres/`
- `tests/postgres_integration/`
- `tests/support/`

This should be treated as the organizing model for `v0.5.5`.

It is acceptable if the first implementation pass does not fully populate every directory, but new placement decisions should move toward this structure rather than away from it.

## 10.2 How current large files should be treated

### `tests/test_coverage_targets.py`

Current problem:

- it is far too large
- it acts as a catch-all for multiple unrelated responsibilities
- preserving it as a dedicated `coverage_targets` island would continue that ambiguity

Recommended direction:

- dissolve it into responsibility-owned destinations
- move runtime/CLI scenarios into `tests/runtime/` and `tests/cli/`
- move workflow and in-memory repository scenarios into `tests/workflow/`
- move memory/embedding scenarios into `tests/memory/`
- move HTTP/server response shaping scenarios into `tests/http/` and `tests/server/`
- move MCP/runtime adapter scenarios into `tests/mcp/`
- move low-level PostgreSQL helper scenarios into `tests/postgres/`

Guidelines:

- do not preserve `coverage_targets` as a long-term parallel taxonomy
- treat existing coverage-target tests as branch/regression cases that belong to real subsystem owners
- if a test duplicates a clearer subsystem test, fold or remove the duplication rather than preserving both by habit

### `tests/test_server.py`

Current problem:

- it mixes server lifecycle, HTTP/runtime behavior, MCP-facing behavior, and response serialization concerns

Recommended direction:

- keep core server lifecycle and bootstrap behavior in `tests/server/`
- move HTTP request/route concerns into `tests/http/` where appropriate
- move MCP handler/resource/tool behavior into `tests/mcp/` where appropriate
- keep only genuinely server-owned integration points in `tests/server/`

### `tests/test_workflow_service.py`

Current problem:

- it mixes workspace registration, workflow lifecycle, checkpointing, completion, validation, and memory bridge interactions

Recommended direction:

- organize under `tests/workflow/`
- split by responsibility such as workspace registration, start/resume, checkpoints, completion, validation, and listing/status behavior
- keep workflow-memory bridge interactions in `tests/workflow/` when they are truly workflow-owned, otherwise move pure memory behavior to `tests/memory/`

### `tests/test_postgres_integration.py`

Current problem:

- it combines memory, workflow, closeout-memory, and database-backed integration flows in one file

Recommended direction:

- organize under `tests/postgres_integration/`
- split by functional integration flow such as workflow lifecycle, memory flows, closeout-memory behavior, resume/checkpoint flows, and observability or validation paths
- centralize expensive Docker/database setup in shared integration support

### Adjacent files that should be considered together

To avoid ending with a mixed old/new taxonomy, the following files should be reviewed together with the main large-file reorganization:

- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_mcp_tool_handlers.py`
- `tests/test_mcp_modules.py`
- `tests/test_postgres_db.py`
- `tests/test_postgres_helpers.py`

Those files are not all oversized, but some of their responsibility boundaries overlap directly with the large-file content that will be moved.

---

## 11. Shared helper strategy

Splitting files often exposes duplicated setup.

That is useful, but helper extraction should stay disciplined.

## 11.1 Good shared helper candidates

Reasonable shared candidates include:

- UUID builders
- timestamp builders
- common workflow payload builders
- common memory payload builders
- reusable fake repositories or stubs
- PostgreSQL integration setup helpers
- repeated response assertion helpers with a stable shape

## 11.2 Helpers to avoid over-abstracting

Be cautious with:

- giant fixture modules with unclear ownership
- helpers that hide all important setup
- assertion helpers that obscure what a test is actually proving
- one-size-fits-all builders that accept too many optional knobs

## 11.3 Placement guidance

Possible support locations:

- `tests/conftest.py` for widely shared fixtures
- domain-local `conftest.py` files inside responsibility-based subdirectories
- a small `tests/support/` subtree for reusable builders, factories, and integration helpers

Prefer domain-local support when only one subsystem needs it.

---

## 12. Coverage improvement strategy

## 12.1 Coverage philosophy

The purpose is not only to increase the percentage.

The purpose is to increase useful protection.

That means prioritizing tests that cover:

- meaningful branch decisions
- error cases that affect users or agents
- format/contract stability
- repository parity expectations
- recent bug or cleanup regression surfaces

## 12.2 High-value coverage candidates

The exact targets should be confirmed during implementation, but likely candidates include:

### Workflow and resume edge cases
- invalid identifier type handling
- not-found vs invalid-input distinctions
- running vs terminal workflow transitions
- checkpoint/complete sequencing constraints
- error detail consistency

### Server and transport behavior
- malformed input handling
- UUID/category misuse guidance
- status code and error payload consistency
- edge-case query/body parsing
- behavior when optional context is absent

### CLI and config behavior
- conflicting arguments
- missing required settings
- formatting differences between text and JSON paths
- failure rendering and exit-code behavior
- environment/config precedence edge cases

### PostgreSQL paths
- transaction rollback behavior
- null/optional field normalization
- observability/statistics edge cases
- empty-state queries
- parity with in-memory behavior where applicable

### MCP/tool handling
- parameter validation boundaries
- response shape consistency
- tool-specific error mapping
- optional field handling and defaults

## 12.3 Coverage sources to inspect

When selecting additions, prioritize:

- recent fixes and regressions
- branches that are only indirectly covered
- behavior with subtle conditional logic
- areas where current tests assert success but not failure semantics
- code paths with high operational importance

---

## 13. Implementation phases

## 13.1 Phase 1: inventory and mapping

Tasks:

- identify oversized test files
- identify natural scenario clusters inside each
- locate file-local fixtures/helpers
- identify current coverage weak spots worth addressing in this milestone

Deliverable:

- a split map per oversized file
- a shortlist of coverage additions ranked by value

## 13.2 Phase 2: define and begin the responsibility-based layout

Start by establishing the target `tests/` taxonomy and using it as the destination map for all subsequent moves.

Rationale:

- without a destination taxonomy, file splitting can create a new layer of accidental organization
- `tests/test_coverage_targets.py` is not the only mixed-responsibility file
- several adjacent files overlap in ownership and should be reorganized coherently

Expected result:

- a clear responsibility-based destination map for `tests/`
- reduced ambiguity about where moved tests belong
- less chance of ending with both old and new organizational models in parallel

## 13.3 Phase 3: dissolve catch-all and mixed-responsibility files into that layout

Start with `tests/test_coverage_targets.py`, but treat it as one input source among several, not as the organizing center.

Rationale:

- it is the largest file by far
- it contains the broadest mix of unrelated concerns
- it overlaps with responsibilities already present in `test_server.py`, `test_workflow_service.py`, `test_mcp_*`, `test_cli.py`, and PostgreSQL-focused files

Expected result:

- responsibility-owned destination files under the new `tests/` layout
- removal of catch-all sprawl
- preserved or improved branch protection
- a path toward dissolving other mixed files into the same structure

### Initial destination map for `tests/test_coverage_targets.py`

The current file should be dissolved into responsibility-owned files rather than preserved as a parallel `coverage_targets` subtree.

Representative destination mapping:

- runtime and database-health scenarios → `tests/runtime/`
- CLI scenarios → `tests/cli/`
- workflow service and in-memory workflow repository scenarios → `tests/workflow/`
- memory service, embeddings, serializers, and workflow memory bridge scenarios → `tests/memory/`
- HTTP app, HTTP handlers, and server response shaping scenarios → `tests/http/` and `tests/server/`
- MCP RPC and runtime adapter scenarios → `tests/mcp/`
- low-level PostgreSQL helper scenarios → `tests/postgres/`

Implementation notes for this phase:

- keep the existing helper fixtures/builders available to the new files only as needed
- move only genuinely shared setup into responsibility-local `conftest.py` files or `tests/support/`
- keep narrow helpers local when only one destination file uses them
- preserve explicit assertions even when extracting shared builders
- do not preserve the current file as a compatibility shell unless incremental migration truly requires it

## 13.4 Phase 4: reorganize neighboring large and overlapping suites

Address:

- `tests/test_postgres_integration.py`
- `tests/test_server.py`

Rationale:

- both are large
- both likely benefit from clearer domain grouping
- both protect high-risk integration surfaces

Expected result:

- better separation of functional flows
- easier focused test runs
- clearer debugging when failures occur

## 13.4 Phase 4: split workflow service tests

Address:

- `tests/test_workflow_service.py`

Expected result:

- lifecycle-specific grouping
- clearer service contract coverage
- easier future workflow refactoring

## 13.5 Phase 5: targeted coverage additions

After the structural splits settle, add tests for the most valuable uncovered or weakly asserted behaviors.

This order matters.

It is better to stabilize the new layout before adding many new tests.

## 13.6 Phase 6: cleanup and final validation

Tasks:

- remove dead helpers made obsolete by the split
- normalize naming
- ensure discovery still works cleanly
- run focused suites
- run the full suite
- run coverage and inspect misses that still matter

---

## 14. Validation strategy

## 14.1 During split work

After each split batch:

- run the affected file set or domain suite
- verify test discovery still works
- verify fixtures resolve correctly
- compare behavior before and after the split

## 14.2 During coverage additions

For each new coverage-oriented test:

- confirm it protects a real branch or behavior
- avoid adding tests that only execute lines without asserting outcomes
- verify failure assertions are specific and stable

## 14.3 Before milestone closeout

Minimum closeout validation should include:

- focused runs for each touched subsystem
- a full test suite run
- a coverage run
- review of remaining large files and misses to confirm no obvious follow-up was skipped unintentionally

---

## 15. Risks and mitigations

## 15.1 Main risks

### Discovery and fixture breakage
Splitting files can break imports, fixture resolution, or test collection.

### Over-abstraction
In an effort to reduce duplication, the suite may gain helpers that hide intent.

### Cosmetic churn without real value
A large rename/move diff may not materially improve maintainability if grouping is weak.

### Coverage inflation without quality
Coverage can go up while meaningful protection does not.

### Longer CI/debug cycles during transition
During the split, temporary instability in test discovery or support code may slow iteration.

## 15.2 Mitigations

- split incrementally
- keep groupings behavior-oriented
- introduce helpers only when they clearly improve readability
- validate each split before proceeding
- prefer high-value coverage additions over percentage chasing
- keep test names explicit and descriptive
- avoid giant all-at-once moves where possible

---

## 16. Naming and layout conventions

Recommended conventions for new test files:

- use directory names that reflect the subsystem
- use file names that reflect the behavior family
- keep `test_` prefixes so discovery remains obvious
- avoid opaque names like `test_misc.py`, `test_more.py`, or `test_part_3.py`

Examples of good names:

- `test_workflow_routes.py`
- `test_resume_and_checkpoint_flows.py`
- `test_validation_and_identifiers.py`
- `test_completion.py`

Examples to avoid:

- `test_misc.py`
- `test_extra.py`
- `test_part2.py`

---

## 17. Deliverables

A successful `0.5.5` milestone should leave behind:

- a clearer `tests/` structure
- split replacements for the worst oversized files
- stable fixture/helper organization
- targeted new tests in important weak spots
- healthy or improved coverage
- passing validation for touched areas and the full suite
- updated continuation notes for the next session
- a repository state that is easier to review and evolve

---

## 18. Suggested work breakdown

## 18.1 Stage A: planning and inventory
- confirm oversized-file priority list
- define target subdirectory structure
- identify current helper extraction candidates
- identify top coverage gaps

## 18.2 Stage B: establish the responsibility-based `tests/` layout
- define the target directory taxonomy
- decide destination ownership for current mixed-responsibility files
- identify the minimum shared support needed for the first migration steps

## 18.3 Stage C: dissolve coverage-target and overlapping tests into owned areas
- move `tests/test_coverage_targets.py` scenarios into responsibility-owned files
- update adjacent files where overlap would otherwise leave the taxonomy inconsistent
- preserve intent and discovery

## 18.4 Stage D: reorganize PostgreSQL integration, server, workflow, and MCP-adjacent suites
- group by functional responsibility and subsystem ownership
- centralize only the setup that truly deserves sharing

## 18.5 Stage E: add targeted coverage
- focus on important branches and regressions inside each responsibility area
- strengthen failure-path assertions

## 18.6 Stage F: final verification and closeout
- run focused suites
- run the full suite
- run coverage
- document what was improved and what remains

---

## 19. Closeout criteria

`0.5.5` can be considered complete when:

- the largest and most mixed-responsibility test files have been reorganized into coherent responsibility-owned units
- no replacement file or directory remains a new catch-all without justification
- important weak spots have gained meaningful tests
- suite readability has improved
- the `tests/` layout makes subsystem ownership clearer
- test discovery and fixtures remain stable
- full validation passes
- coverage remains healthy and ideally improves beyond the current baseline

---

## 20. Immediate next steps

1. define the responsibility-based target layout for `tests/`
2. map current mixed-responsibility files into that destination structure
3. start dissolving `tests/test_coverage_targets.py` and adjacent overlapping suites into owned areas in small, validated steps
4. continue the same approach for PostgreSQL integration, server, workflow, MCP, and CLI-adjacent tests
5. add the highest-value coverage improvements after the new structure is stable
6. close the milestone with full-suite and coverage verification