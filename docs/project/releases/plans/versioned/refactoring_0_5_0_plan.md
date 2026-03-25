# Refactoring 0.5.0 Plan

## 1. Purpose

This document defines the implementation plan for the `0.5.0` milestone.

The goal of `0.5.0` is to improve the internal structure of `ctxledger` without changing its intended external behavior.

This milestone intentionally prioritizes:

- refactoring `src/`
- refactoring `tests/`
- reducing duplicated logic
- improving module boundaries
- improving maintainability and reviewability
- preserving current behavior through disciplined validation

This milestone explicitly does **not** prioritize hierarchical memory retrieval as its primary scope.

That work is now deferred to `0.6.0`.

---

## 2. Roadmap shift for 0.5.0 and 0.6.0

## 2.1 Updated milestone intent

### 0.5.0
`0.5.0` is now the **refactoring milestone**.

Focus:

- file-level refactoring inside existing modules
- cross-file refactoring of duplicated logic
- test-suite structure cleanup
- improved reuse of helpers and serializers
- safer internal architecture for future feature work

### 0.6.0
Hierarchical memory retrieval moves here.

Focus:

- hierarchical memory retrieval
- summary layers
- relation-aware context assembly
- richer multi-layer `memory_get_context` behavior

---

## 3. Why this milestone exists

The repository now has meaningful implementation breadth across:

- workflow runtime
- MCP handlers
- HTTP runtime
- memory services
- observability CLI
- PostgreSQL and in-memory repositories
- Grafana/dashboard support
- broad automated test coverage

At this stage, the next highest-value work is not only adding new features.

It is improving the internal shape of the codebase so that:

- future features are easier to implement
- duplicate logic does not drift inconsistently
- tests stay readable and maintainable
- runtime-visible behavior remains stable while internals improve
- later milestones such as `0.6.0` can build on cleaner abstractions

This milestone addresses that need.

---

## 4. Primary objective

Refactor the existing codebase in a way that:

- does **not** intentionally change the supported product surface
- reduces duplication within individual files first
- then reduces duplication across files
- keeps behavior protected by tests throughout the work
- leaves the repository easier to extend and review

---

## 5. Scope of 0.5.0

## 5.1 In scope

### Internal refactoring in `src/`
Refine implementation structure in application code without changing intended behavior.

Examples:

- helper extraction
- internal API cleanup
- repeated validation logic consolidation
- serializer/result-shaping cleanup
- repeated formatting/path/UUID parsing logic consolidation
- repeated response-construction cleanup
- repeated repository query/result normalization cleanup

### Internal refactoring in `tests/`
Improve maintainability and signal quality of the test suite.

Examples:

- shared fixtures
- helper builders
- shared fake/stub factories
- repeated assertion pattern cleanup
- repeated setup/teardown simplification
- grouping related test helpers by domain
- reducing copy-pasted test payloads where it improves clarity

### Two-stage duplication reduction
This milestone should follow a deliberate sequence:

1. **within-file duplication cleanup**
2. **cross-file duplication cleanup**

This ordering is intentional.

It reduces risk by first making local structure clearer before extracting reusable logic across module boundaries.

### Refactoring plan and traceability
The implementation should be guided by an explicit written plan and should leave enough documentation for future sessions to continue safely.

---

## 5.2 Explicitly out of scope

The following should **not** be treated as `0.5.0` requirements unless they are strictly necessary to preserve behavior during refactoring:

- new product-facing workflow features
- new product-facing memory retrieval features
- hierarchical retrieval
- relation-aware retrieval UX
- broad CLI surface expansion
- browser-native operator UI
- semantic behavior redesign
- storage model redesign
- large migration of canonical schema semantics
- speculative architecture churn without concrete duplication payoff

---

## 6. Refactoring principles

## 6.1 Behavior preservation first
Refactoring should preserve the existing supported behavior.

Do not change behavior casually under the label of cleanup.

If behavior must change for correctness or consistency, that change should be:

- explicit
- narrowly scoped
- documented
- validated with tests

## 6.2 Small, reviewable steps
Prefer a sequence of small, understandable changes over large sweeping rewrites.

## 6.3 Extraction only after clarity
Do not extract shared helpers too early.

First simplify duplicated logic in place.
Then extract the shared pattern only once the common shape is truly clear.

## 6.4 Readability over abstraction count
Do not introduce extra indirection unless it clearly improves maintainability.

A small amount of duplication can be better than a confusing abstraction.

## 6.5 Tests are protection, not decoration
When refactoring, tests are the primary safety mechanism.

If tests are hard to understand or maintain, that is itself a refactoring target.

## 6.6 Preserve honest boundaries
Do not blur canonical workflow logic, memory logic, transport logic, and observability logic unless the shared behavior is genuinely generic.

---

## 7. Refactoring sequence

## 7.1 Phase 1: Baseline and inventory

### Goals
- identify high-value duplication
- identify risky areas
- define validation checkpoints
- avoid blind rewrites

### Tasks
- inventory repeated logic in `src/`
- inventory repeated test scaffolding in `tests/`
- classify duplication by:
  - within-file duplication
  - cross-file duplication
  - low-risk extraction candidates
  - high-risk extraction candidates
- identify modules with the highest change density and widest surface area

### Deliverable
A working duplication map or implementation checklist derived from this plan.

---

## 7.2 Phase 2: File-level refactoring first

### Purpose
Reduce duplication *inside individual files* before extracting helpers across files.

### Typical targets
- repeated local validation branches
- repeated payload shaping
- repeated formatting helpers
- repeated conditional rendering blocks
- repeated table/JSON/text output shaping
- repeated fake object builders in tests
- repeated fixture setup blocks

### Expected result
Each touched file should become easier to read on its own before any cross-file helper extraction begins.

---

## 7.3 Phase 3: Cross-file refactoring second

### Purpose
Once local patterns are clear, reduce duplication *across files*.

### Typical targets
- shared response helpers
- shared serialization helpers
- shared parsing/validation helpers
- shared test builders / fixtures / fake services
- shared runtime introspection formatting helpers
- shared observability output helpers
- shared workflow/memory test data constructors

### Expected result
Cross-file reuse should be introduced only where the shared abstraction is genuinely stable and understandable.

---

## 7.4 Phase 4: Validation and regression hardening

### Purpose
Prove that the refactoring preserved behavior.

### Tasks
- rerun focused tests after each meaningful refactor step
- rerun broader suites after grouped refactor batches
- add missing tests if a refactor reveals an unprotected behavior
- ensure any newly extracted helper remains well covered indirectly or directly

---

## 8. Candidate refactoring areas

The exact implementation order can evolve, but the following areas are likely strong candidates.

## 8.1 CLI and presentation logic
Potential duplication themes:

- text vs JSON rendering shape logic
- repeated argument parsing patterns
- repeated service bootstrap logic
- repeated missing-database-url handling
- repeated error-to-exit-code formatting

Possible outcomes:

- shared CLI bootstrap helper(s)
- shared output rendering helper(s)
- domain-specific formatting helpers

## 8.2 HTTP and MCP transport layers
Potential duplication themes:

- request parsing
- UUID validation
- error payload shaping
- repeated success/error response construction
- resource/tool response adapters

Possible outcomes:

- shared request validation helpers
- shared response factory helpers
- narrower transport adapters with clearer boundaries

## 8.3 Memory and workflow service layers
Potential duplication themes:

- repeated result metadata assembly
- repeated status/detail payload construction
- repeated lookup validation flows
- repeated normalization behavior

Possible outcomes:

- domain-local helper extraction
- cleaner typed internal helper functions
- more consistent result assembly paths

## 8.4 Repository and statistics aggregation code
Potential duplication themes:

- count aggregation patterns
- timestamp summary shaping
- status breakdown normalization
- in-memory vs PostgreSQL parity logic

Possible outcomes:

- shared aggregation contracts
- reusable normalization helpers
- clearer parity expectations between repository implementations

## 8.5 Test suite structure
Potential duplication themes:

- fake service definitions
- repeated fixture assembly
- repeated UUID and timestamp builders
- repeated payload assertions
- repeated CLI/runtime startup setup

Possible outcomes:

- shared test helpers
- shared builders/factories
- reduced boilerplate without hiding test intent

---

## 9. Risk management

## 9.1 Main risks

### Behavioral drift
A refactor accidentally changes runtime-visible behavior.

### Over-abstraction
A cleanup introduces abstractions that are harder to maintain than the original duplication.

### Test opacity
Shared helpers make tests shorter but less readable.

### Mixed-purpose changes
A refactor PR also introduces feature changes, making validation harder.

---

## 9.2 Mitigations

- keep changes behavior-preserving by default
- prefer small commits/PRs grouped by duplication theme
- rerun focused tests early and often
- extract only after common patterns are explicit
- avoid combining refactoring with unrelated feature work
- keep test helpers explicit and domain-named

---

## 10. Validation strategy

## 10.1 Validation philosophy
Validation should be layered.

Use the smallest test scope that proves the recent change, then expand outward.

## 10.2 Expected validation loop

### After small/local refactors
Run focused file or domain tests.

Examples:
- CLI-only tests after CLI cleanup
- server/runtime tests after transport cleanup
- memory tests after memory helper extraction

### After grouped changes
Run broader suites that cover the affected subsystem.

### Before milestone closeout
Run the full suite.

## 10.3 Minimum closeout expectation
Before declaring `0.5.0` complete:

- targeted suites for touched areas should pass
- the full test suite should pass
- no intentional product-surface regression should remain open
- docs should reflect that `0.5.0` was a refactoring release and `0.6.0` holds hierarchical retrieval

---

## 11. Deliverables

A successful `0.5.0` should leave behind:

- cleaner `src/` internals
- cleaner `tests/` structure
- reduced within-file duplication
- reduced cross-file duplication where justified
- preserved behavior verified by tests
- updated roadmap / planning docs
- updated continuation notes for the next session
- a repository state that makes `0.6.0` hierarchical retrieval safer to begin

---

## 12. Non-goals and anti-patterns

Avoid the following:

- rewriting large subsystems because they feel old
- extracting helpers that are only shared twice but still semantically different
- merging unrelated domains into one utility module
- replacing explicit tests with overly generic meta-tests
- reducing line count at the expense of clarity
- changing public behavior without deliberate documentation and validation

---

## 13. Suggested work breakdown

## 13.1 Stage A: documentation and inventory
- update roadmap to move hierarchical retrieval from `0.5.0` to `0.6.0`
- declare `0.5.0` as refactoring-focused
- capture duplication candidates and priority areas

## 13.2 Stage B: within-file cleanup
- address obvious repeated blocks inside high-value files
- keep changes narrow and easy to validate

## 13.3 Stage C: cross-file cleanup
- extract shared logic once local patterns are stable
- favor domain-scoped helpers over giant generic utility modules

## 13.4 Stage D: test cleanup
- simplify repeated setup and builders
- preserve test readability and intent

## 13.5 Stage E: final verification
- rerun focused and full validation
- close out docs and session notes

---

## 14. Candidate high-priority files to inspect first

The exact list can evolve, but likely first-pass candidates include:

### Application code
- `src/ctxledger/__init__.py`
- `src/ctxledger/config.py`
- `src/ctxledger/memory/service.py`
- `src/ctxledger/workflow/service.py`
- `src/ctxledger/workflow/memory_bridge.py`
- `src/ctxledger/db/postgres.py`

### Test code
- `tests/test_cli.py`
- `tests/test_server.py`
- `tests/test_config.py`
- `tests/test_coverage_targets.py`

These files are likely to yield meaningful duplication reduction with high impact on maintainability.

---

## 15. Closeout criteria for 0.5.0

`0.5.0` can be considered complete when:

- the roadmap clearly positions `0.5.0` as refactoring and `0.6.0` as hierarchical retrieval
- a meaningful duplication-reduction pass has been completed in both `src/` and `tests/`
- refactoring has happened in the intended order:
  - within-file first
  - cross-file second
- existing supported behavior remains intact
- test coverage remains healthy and the full suite passes
- docs and continuation notes reflect the completed work honestly

---

## 16. Immediate next steps

1. update planning/roadmap docs so `0.5.0` becomes the refactoring milestone and hierarchical retrieval moves to `0.6.0`
2. review `src/` and `tests/` for high-value within-file duplication candidates
3. create a duplication inventory grouped by:
   - file-local duplication
   - cross-file duplication
4. start with the highest-value low-risk within-file refactors
5. validate each batch with focused tests before broader reruns