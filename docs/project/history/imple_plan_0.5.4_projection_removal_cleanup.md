# ctxledger v0.5.4 Implementation Plan: Remove Remaining Local `.agent/` Projection Remnants

## Status

- Draft
- Intended release: `v0.5.4`
- Purpose: repository cleanup and surface simplification before `v0.6.0`

## Objective

Remove the remaining code, configuration, persistence, API, CLI, test, and documentation remnants of the deprecated feature that writes projection artifacts under `.agent/`, while preserving:

- canonical workflow lifecycle behavior
- memory features
- MCP and HTTP workflow operations unrelated to projections
- database integrity for non-projection features
- operational clarity for future `v0.6.0` work

This plan is intentionally focused on **safe deletion** and **surface contraction**, not on redesigning unrelated systems.

---

## 1. Background

`v0.5.3` deprecated user-facing local projection access, especially repository-local `.agent/` outputs such as:

- `.agent/resume.json`
- `.agent/resume.md`

However, the repository still appears to contain projection-oriented remnants in several places, including:

- workflow-domain models
- in-memory and PostgreSQL persistence abstractions
- CLI output and commands
- HTTP and MCP mutation/read routes for projection failure handling
- runtime serializers and response builders
- tests and docs
- compatibility stubs such as the removed projection writer package

That leaves the codebase in an awkward in-between state:

1. the product direction says local `.agent/` projection output is gone
2. the code still models projections as an active first-class concern
3. some operational and testing surfaces still expose projection lifecycle concepts
4. the remaining footprint increases maintenance cost and upgrade confusion

For `v0.6.0`, this should be cleaned up first so the next development cycle starts from a smaller and clearer base.

---

## 2. Desired product direction for `v0.5.4`

After `v0.5.4`:

- `ctxledger` should treat PostgreSQL-backed workflow and memory state as canonical
- workflow resume should be exposed through canonical runtime interfaces only
- repository-local `.agent/` resume projection generation should be fully absent
- projection-specific persistence and failure lifecycle code should be removed if it only existed to support `.agent/` outputs
- user-facing CLI, HTTP, and MCP surfaces should no longer mention projection concepts
- tests and docs should align with the simplified non-projection model

---

## 3. Cleanup principles

### 3.1 Safety principle

Prefer removing entire isolated projection paths over partially editing shared logic.  
Deletion is safer than mutation when the feature is already deprecated.

### 3.2 Compatibility principle

Preserve behavior for:

- workspace registration
- workflow start
- workflow resume
- workflow checkpoint
- workflow complete
- memory search and context retrieval
- runtime introspection
- health/readiness behavior

### 3.3 Efficiency principle

Use the smallest set of coordinated removals that eliminates the projection subsystem end to end:

- delete dead models
- delete dead repositories
- delete dead handlers/routes/tools
- simplify resume payloads
- rewrite only those tests/docs that directly reference projections

### 3.4 Non-goal principle

Do **not** broaden the scope into:

- memory model redesign
- runtime transport redesign
- database migration framework redesign
- large naming cleanup unrelated to projection removal

### 3.5 Non-impact boundaries

The following areas should be treated as explicitly **out of bounds for behavior change** during the `v0.5.4` cleanup unless a change is strictly required to remove projection coupling:

- workspace registration semantics
- workflow start semantics
- workflow checkpoint persistence and verification semantics
- workflow complete semantics, including completion-memory behavior
- canonical workflow resume classification rules unrelated to projection state
- memory search scoring behavior unrelated to projection-derived freshness inputs
- MCP lifecycle behavior unrelated to projection routes/tools
- HTTP server startup, shutdown, health, and readiness behavior unrelated to projection routes
- PostgreSQL repository behavior for non-projection entities
- existing public payload fields that are not projection-specific

If a proposed code change would alter one of these areas, it should be treated as a separate task and deferred unless it is the minimum change required to keep the cleanup coherent.

### 3.6 Decision rules for efficient deletion

When deciding how to remove a projection remnant, apply these rules:

1. **Delete entire isolated surfaces first**
   - if a handler, route, tool, schema, or test exists only for projection behavior, delete it rather than abstracting it

2. **Prefer subtraction over substitution**
   - if a projection-only field is present in a payload or model, remove it rather than replacing it with a new concept in `v0.5.4`

3. **Preserve stable canonical paths**
   - if a code path serves canonical workflow or memory behavior and only contains a small projection branch, delete the branch and keep the rest intact

4. **Avoid speculative compatibility layers**
   - do not add new aliases, adapters, or stubs unless they are required to keep the repository buildable during the cleanup window

5. **Keep database cleanup secondary**
   - remove code-level dependencies on projection tables first
   - only perform schema/table retirement if it is clearly low-risk and already operationally supported

6. **Use test edits proportionate to value**
   - delete projection-dedicated tests
   - rename fixture strings or expected fields when the broader test still provides useful coverage for non-projection behavior

---

## 4. Repository-visible impact areas

## 4.1 Domain and workflow service layer

Likely projection remnants include:

- `ProjectionStatus`
- `ProjectionArtifactType`
- `ProjectionInfo`
- `ProjectionFailureInfo`
- `RecordProjectionStateInput`
- `RecordProjectionFailureInput`
- projection-bearing fields on workflow resume models
- projection-related warning generation
- projection failure counting in stats
- projection-related repositories on unit-of-work contracts

### Cleanup direction

- remove projection-specific enums, dataclasses, and input models
- remove projection-bearing fields from workflow resume responses/models if they only exist for `.agent/` projection support
- remove projection failure aggregation from workflow stats
- simplify resume logic so it no longer reasons about projection freshness, missing projections, or projection failure closure
- preserve resumable/blocked/terminal classification using canonical checkpoint/attempt/workflow state only

---

## 4.2 Persistence layer

Likely projection remnants include:

- in-memory projection state repositories
- in-memory projection failure repositories
- projection collections inside in-memory store snapshots
- PostgreSQL projection repositories
- projection-related SQL access methods
- projection-related unit-of-work properties

### Cleanup direction

- remove projection repositories from persistence contracts
- remove in-memory backing store maps related to projections
- remove PostgreSQL repository implementations for projection state/failure lifecycle
- remove unit-of-work wiring for projection repositories
- keep all non-projection repositories unchanged

### Efficiency note

If projection tables remain in historical schemas for compatibility, `v0.5.4` does not need to delete old tables immediately unless schema ownership and migration discipline are already in place.  
Code removal can happen first, schema retirement can be staged if needed.

---

## 4.3 CLI surface

Likely projection remnants include:

- `write-resume-projection` command
- projection fields in `resume-workflow` textual output
- projection failure counts in `stats`
- projection failure inspection output
- `.agent/resume.json` / `.agent/resume.md` references

### Cleanup direction

- remove the `write-resume-projection` command entirely
- remove projection sections from `resume-workflow` output
- remove projection-related counters from `stats`
- remove projection-failure-specific CLI reporting paths
- preserve all canonical workflow and memory CLI flows

---

## 4.4 HTTP and MCP surface

Likely projection remnants include:

- projection failure mutation endpoints
- closed projection failure history endpoints
- MCP tools for projection failure ignore/resolve
- projection-related tool schemas
- route registration for projection endpoints
- runtime introspection listing of projection routes/tools

### Cleanup direction

- remove projection-failure HTTP endpoints
- remove MCP projection-failure tools and schemas
- remove projection-specific runtime route registrations
- update introspection outputs accordingly
- preserve canonical `workflow_resume`, workflow mutation, and memory tools/resources

### Safety note

This is a good cleanup target because projection failure endpoints are tightly coupled to the deprecated projection subsystem and have weak value once `.agent/` projections are gone.

---

## 4.5 Memory freshness / ordering logic

Some current workflow freshness signals may still include projection-derived timestamps and failure counts, for example conceptual fields such as:

- latest projection canonical update
- latest projection successful write
- open projection failure count

### Cleanup direction

- remove projection-derived freshness signals from workflow ordering
- keep ordering based on:
  - workflow terminality
  - latest attempt terminality
  - latest attempt existence
  - latest checkpoint existence/time
  - latest verify report time
  - latest episode time
  - latest attempt start time
  - workflow updated time

### Benefit

This simplifies ordering logic and removes coupling between memory retrieval behavior and a deleted file-output subsystem.

---

## 4.6 Tests

Likely affected files include at least:

- `tests/test_cli.py`
- `tests/test_server.py`
- `tests/test_mcp_tool_handlers.py`
- `tests/test_postgres_integration.py`
- `tests/test_coverage_targets.py`
- any dedicated projection writer tests
- any tests importing projection config/models

### Cleanup direction

- delete dedicated projection writer tests
- delete projection failure endpoint/tool tests
- delete write-resume-projection command tests
- remove projection assertions from resume/stats tests
- update coverage-target tests to stop referencing projection freshness keys
- preserve and re-center coverage on canonical workflow behavior

### Efficiency note

Where tests use projection words only as arbitrary string fixtures, prefer renaming fixture strings instead of deleting good coverage.

---

## 4.7 Documentation

Likely affected docs include:

- architecture docs describing projections as active infrastructure
- security docs for projection failure endpoints
- deployment docs or examples mentioning `.agent/`
- changelog or implementation notes that should reflect final cleanup
- any deprecation-plan docs that should remain historical but not normative

### Cleanup direction

- update current product docs to remove active projection guidance
- keep historical release-planning documents as historical records when appropriate
- ensure user-facing docs describe canonical resume access only
- remove endpoint references that no longer exist

---

## 5. Recommended scope for `v0.5.4`

## In scope

- remove projection-specific CLI command and output
- remove projection-specific HTTP and MCP endpoints/tools/schemas
- remove projection-specific workflow-domain models and repository interfaces
- remove in-memory and PostgreSQL projection repository implementations
- remove projection-derived serializer fields from active responses
- remove or update projection-related tests
- update docs to match the simplified product surface

## Out of scope unless discovered necessary

- destructive database migrations that drop historical projection tables
- large refactors unrelated to projection removal
- changing canonical workflow semantics
- redesigning memory APIs
- changing release/versioning strategy beyond documenting `v0.5.4`
- behavior changes to non-projection CLI, HTTP, MCP, memory, or persistence paths
- opportunistic renaming of unrelated fields, APIs, or internal abstractions
- performance tuning work not directly caused by projection-removal fallout

### Explicit non-impact expectations

The cleanup should leave the following externally observable behaviors unchanged except for the removal of projection-specific surface area:

- `workspace_register`
- `workflow_start`
- `workflow_resume`
- `workflow_checkpoint`
- `workflow_complete`
- `memory_search`
- `memory_get_context`
- runtime introspection for still-supported routes/tools/resources
- non-projection CLI command outputs and exit-code behavior
- non-projection HTTP endpoint paths and response semantics

---

## 6. Implementation strategy

## Phase 1: Inventory and deletion map

### Tasks

- enumerate remaining projection-specific files, types, handlers, tests, and docs
- classify each item as:
  - delete entirely
  - update to remove projection references
  - keep as historical doc only
- identify shared code paths that should be simplified after deletion

### Expected result

A precise removal set with low ambiguity and no accidental scope growth.

### Verification

- repository grep for:
  - `.agent/`
  - `write-resume-projection`
  - projection enums/types/handlers
- produce a before/after checklist

### Concrete removal checklist

#### A. User-facing CLI and output
- remove `write-resume-projection` command registration
- remove any CLI helper dedicated to projection writing
- remove projection sections from `resume-workflow` text output
- remove projection-related warning rendering in `resume-workflow`
- remove `closed_projection_failures` display from `resume-workflow`
- remove projection-related counters from `stats`
- remove projection-related failure-list rendering if it only exists for `.agent/` projection failures

#### B. HTTP and MCP public surface
- remove HTTP handlers for:
  - closed projection failure history
  - projection failure ignore
  - projection failure resolve
- remove HTTP route registration for those handlers
- remove MCP tool handlers for projection failure ignore/resolve
- remove MCP tool schema definitions for projection failure actions
- remove projection tools/routes from runtime introspection output
- remove projection-related server protocol declarations used only by those routes

#### C. Workflow/domain model cleanup
- remove `ProjectionStatus`
- remove `ProjectionArtifactType`
- remove `ProjectionInfo`
- remove `ProjectionFailureInfo`
- remove `RecordProjectionStateInput`
- remove `RecordProjectionFailureInput`
- remove projection-bearing fields from workflow resume models
- remove projection-related warnings and helper branches from workflow service
- remove projection-related stats fields if they are only about the deprecated subsystem

#### D. Persistence cleanup
- remove projection repository interfaces from unit-of-work contracts
- remove in-memory projection repositories
- remove projection state/failure maps from in-memory store and snapshots
- remove PostgreSQL projection repository implementations
- remove projection repository wiring from PostgreSQL unit-of-work construction
- remove projection-only imports from persistence modules

#### E. Resume serialization and response cleanup
- remove `projections` from serialized workflow resume payloads
- remove `closed_projection_failures` from serialized workflow resume payloads
- remove dedicated projection-failure history serializers
- remove response builders dedicated to projection-failure history/actions
- keep canonical workflow resume payload shape otherwise stable

#### F. Memory freshness / ordering cleanup
- remove projection-derived freshness keys from workflow ordering inputs
- remove projection-derived timestamps from candidate signal payloads
- remove projection open-failure count from ordering logic
- preserve checkpoint/verify/attempt/episode/workflow-based ordering

#### G. Projection package and compatibility remnants
- remove `src/ctxledger/projection/writer.py`
- remove any remaining projection package exports
- remove compatibility stubs whose only purpose is to mention removed `.agent/` projection writing

#### H. Test cleanup
- delete dedicated projection writer tests
- delete CLI tests for `write-resume-projection`
- delete HTTP/MCP tests for projection failure lifecycle routes/tools
- remove projection-specific assertions from workflow resume/stats tests
- rename incidental fixture strings that still mention projections
- update coverage-target tests to use non-projection freshness keys

#### I. Documentation cleanup
- remove active docs that describe `.agent/resume.json` or `.agent/resume.md`
- remove docs for projection failure HTTP/MCP actions
- update architecture docs so projections are not described as active runtime behavior
- add `v0.5.4` changelog/release note entry summarizing the cleanup
- keep historical deprecation-planning docs only as historical references

### File-by-file task map

#### `src/ctxledger/__init__.py`
- remove `write-resume-projection` command dispatch
- remove projection-related CLI output blocks from:
  - resume rendering
  - stats rendering
  - failure rendering
- remove projection-related stats JSON fields
- preserve all workflow and memory command behavior unrelated to projections

#### `src/ctxledger/workflow/service.py`
- remove projection enums and projection data models
- remove projection-related input models
- remove projection-bearing fields from workflow resume structures
- remove projection warning generation and projection failure history logic
- preserve canonical resume classification and workflow lifecycle semantics

#### `src/ctxledger/db/__init__.py`
- remove in-memory projection state repository
- remove in-memory projection failure repository
- remove projection storage from `InMemoryUnitOfWork`
- remove projection storage from `InMemoryStore`
- remove projection-related exports and imports

#### `src/ctxledger/db/postgres.py`
- remove PostgreSQL projection state repository
- remove PostgreSQL projection failure repository
- remove projection repository wiring from `PostgresUnitOfWork`
- remove projection-specific SQL query paths
- avoid touching non-projection persistence code unless required for compile/runtime cleanup

#### `src/ctxledger/http_app.py`
- remove projection-failure route imports
- remove FastAPI route registration for projection-failure endpoints
- preserve runtime/debug/workflow resume routes that remain supported

#### `src/ctxledger/mcp/tool_handlers.py`
- remove projection-failure tool handlers
- remove optional projection-type parsing helper if no longer needed
- remove projection-only workflow service calls
- preserve all workflow and memory handlers unrelated to projections

#### `src/ctxledger/mcp/tool_schemas.py`
- remove projection-failure tool schemas
- remove projection-type schema dependencies
- preserve all non-projection schemas unchanged

#### `src/ctxledger/memory/service.py`
- remove projection-derived workflow freshness inputs
- simplify freshness signal payloads to canonical workflow/attempt/checkpoint/episode signals only
- preserve search and context behavior otherwise

#### `src/ctxledger/projection/writer.py`
- delete the module entirely if no compatibility reason remains
- if package-level cleanup is needed, remove any remaining imports/exports that keep the package alive

#### `src/ctxledger/runtime/http_handlers.py`
- remove projection-failure request parsing
- remove closed projection failure history handler
- remove projection-failure ignore/resolve handlers
- remove projection-related exports

#### `src/ctxledger/runtime/http_runtime.py`
- remove projection tools from registered tool list
- remove projection tool dispatch wiring
- remove projection HTTP route registration
- ensure runtime introspection reflects the reduced surface

#### `src/ctxledger/runtime/protocols.py`
- remove projection-specific protocol requirements
- simplify server/runtime protocol surfaces to supported non-projection capabilities only

#### `src/ctxledger/runtime/serializers.py`
- remove projection fields from serialized workflow resume payloads
- remove closed projection failure history serializer
- preserve stable serialization for remaining workflow and memory payloads

#### `src/ctxledger/runtime/server_responses.py`
- remove projection-failure action response builders
- remove closed projection failure history response builder
- simplify workflow resume response building to canonical data only

#### `src/ctxledger/runtime/types.py`
- remove projection-specific response types if they exist only for deleted routes/tools
- preserve generic response types still used by workflow, memory, and runtime introspection flows

#### `src/ctxledger/server.py`
- remove server delegation methods dedicated to projection-failure responses/history
- preserve workflow resume, runtime introspection, and health/readiness behavior

#### `tests/test_cli.py`
- delete tests for `write-resume-projection`
- remove projection sections/counters from CLI output expectations
- keep workflow and memory CLI coverage

#### `tests/test_server.py`
- remove projection endpoint/tool/runtime expectations
- update runtime introspection expectations after route/tool removal
- keep non-projection HTTP and server lifecycle coverage

#### `tests/test_mcp_tool_handlers.py`
- delete projection-failure tool handler coverage
- update schema/runtime expectations as needed
- keep workflow and memory MCP coverage

#### `tests/test_postgres_integration.py`
- delete projection-specific persistence/integration tests
- remove projection config/model imports
- preserve workflow and memory integration coverage

#### `tests/test_coverage_targets.py`
- remove projection-specific symbols and fixture fields
- replace projection-derived freshness keys with non-projection equivalents
- preserve coverage of ordering/serialization/branch behavior

#### Documentation update targets
- `docs/architecture.md`
- `docs/operations/deployment/deployment.md`
- `docs/operations/security/SECURITY.md`
- `docs/project/releases/CHANGELOG.md`

For these files:
- remove active projection feature descriptions
- remove projection-failure endpoint guidance
- add `v0.5.4` cleanup note where appropriate
- keep historical planning docs intact unless they incorrectly present old behavior as current

### Milestone checklist

#### Milestone 1 — Surface removal
- [ ] CLI no longer exposes `write-resume-projection`
- [ ] CLI resume output no longer shows projections
- [ ] CLI stats/failure output no longer references projection state
- [ ] HTTP projection-failure routes removed
- [ ] MCP projection-failure tools removed
- [ ] runtime introspection no longer lists projection routes/tools

##### Milestone 1 implementation checklist
- [ ] remove `write-resume-projection` from CLI parser construction
- [ ] remove `write-resume-projection` from CLI command dispatch
- [ ] remove projection-only CLI helper code that exists solely to support `.agent` output
- [ ] remove `Projections:` section from resume text output
- [ ] remove projection-only warning-detail formatting from resume text output
- [ ] remove `Closed projection failures:` section from resume text output
- [ ] remove projection-specific stats counters and labels from CLI output and JSON payloads
- [ ] remove projection-only failure-report formatting paths from CLI output and JSON payloads
- [ ] remove projection-failure HTTP handlers and route registrations
- [ ] remove projection-failure MCP handlers and schemas
- [ ] remove projection-only runtime introspection registrations and expectations
- [ ] confirm no supported public CLI, HTTP, or MCP path still advertises `.agent` projection behavior

#### Milestone 2 — Core model and persistence removal
- [ ] projection enums/models removed from workflow domain
- [ ] workflow resume payload/model simplified
- [ ] in-memory projection repositories removed
- [ ] PostgreSQL projection repositories removed
- [ ] unit-of-work contracts no longer mention projection repositories
- [ ] memory freshness logic no longer depends on projection-derived state

#### Milestone 3 — Test stabilization
- [ ] projection-dedicated tests deleted
- [ ] projection imports removed from remaining tests
- [ ] coverage-target fixtures renamed/simplified
- [ ] focused workflow/runtime/memory/persistence suites pass
- [ ] full suite passes

#### Milestone 4 — Documentation and release closeout
- [ ] current docs no longer describe `.agent/` projection output
- [ ] security/deployment/API docs no longer list projection-failure routes
- [ ] changelog includes `v0.5.4` cleanup note
- [ ] final grep confirms projection remnants are gone from active runtime paths

---

## Phase 2: Remove user-facing surfaces first

### Tasks

- remove CLI command for local resume projection writing
- remove projection sections from resume output
- remove projection counters and failure reporting from stats/failures output
- remove HTTP routes and MCP tools for projection failure lifecycle
- remove related schemas and route registration

### Expected result

No user-facing command, route, or MCP surface should still advertise projection functionality.

### Verification

- CLI parser no longer exposes projection command
- runtime introspection no longer lists projection routes/tools
- tests for workflow and memory surfaces still pass after surface removal

### Suggested implementation batch for this phase

1. remove the `write-resume-projection` command from CLI dispatch and parser wiring
2. remove projection-related text sections from resume output
3. remove projection-related stats/failure output
4. remove projection-failure HTTP handlers and route registration
5. remove projection-failure MCP tool handlers and schema registration
6. verify runtime introspection output no longer advertises projection surfaces

### Focused validation commands for Milestone 1

Run these after the surface-removal patch before moving to deeper model/persistence cleanup:

1. CLI and workflow-facing tests
   - `pytest -q tests/test_cli.py tests/test_server.py`
2. MCP surface tests
   - `pytest -q tests/test_mcp_tool_handlers.py tests/test_mcp_modules.py`
3. Coverage-oriented branch checks that touch runtime and serialization behavior
   - `pytest -q tests/test_coverage_targets.py`
4. Public-surface residue grep
   - verify no active surface code still contains:
     - `write-resume-projection`
     - `.agent/resume.json`
     - `.agent/resume.md`
     - `projection_failures_ignore`
     - `projection_failures_resolve`
     - `closed_projection_failures`

The Milestone 1 patch should not proceed to Milestone 2 until these focused checks are green or any failures are clearly understood as expected fallout from deleted projection-only surfaces.

---

## Phase 3: Remove workflow and persistence internals

### Tasks

- delete projection enums/dataclasses/input models
- remove projection-bearing fields from resume/response models
- delete projection repository protocols and implementations
- remove projection repositories from unit-of-work types and constructors
- simplify workflow service and freshness logic

### Expected result

Core workflow and persistence code no longer model repository-local projection state as a first-class concern.

### Verification

- type checking / tests pass
- workflow resume still works based on canonical state only
- memory freshness ordering still behaves deterministically

### Suggested implementation batch for this phase

1. remove projection dataclasses/enums/input models from workflow domain code
2. remove projection-bearing resume fields and internal branching
3. remove projection repository interfaces from unit-of-work definitions
4. delete in-memory projection repositories and backing-store fields
5. delete PostgreSQL projection repositories and unit-of-work wiring
6. simplify workflow ordering and freshness calculations to non-projection signals only

---

## Phase 4: Test cleanup and coverage stabilization

### Tasks

- delete projection-dedicated tests
- update coverage-target suites and fixtures
- rename incidental test strings/fields that still mention projections
- rerun focused and full test suites

### Expected result

Tests validate the simpler non-projection architecture and coverage remains healthy.

### Verification

Recommended sequence:

1. focused workflow/runtime tests
2. focused persistence tests
3. focused memory tests
4. full suite

### Concrete validation checklist

- confirm test collection no longer imports removed projection models
- confirm no test asserts `.agent/resume.json` or `.agent/resume.md`
- confirm no test expects projection failure routes/tools
- confirm resume serialization tests still pass with simplified payloads
- confirm memory ordering tests pass after signal-key simplification
- confirm persistence tests pass without projection repositories present

---

## Phase 5: Documentation cleanup

### Tasks

- remove current-state docs that instruct or describe `.agent/` projection output
- remove docs for projection failure routes/tools
- add changelog note for `v0.5.4`
- note that canonical workflow resume interfaces remain the supported path

### Expected result

Repository docs match the actual product surface with no contradictory guidance.

### Verification

- docs grep shows no active user guidance for `.agent/` projection output
- removed endpoints are absent from security/deployment/API docs

---

## 7. Detailed code-change plan

## 7.1 Delete candidates

These should be evaluated as likely full deletions:

- `src/ctxledger/projection/writer.py`
  - if only retained as a removal stub, remove package/module entirely unless import compatibility requires one final transitional release
- dedicated projection writer tests
- CLI handler path for `write-resume-projection`
- HTTP handlers dedicated to projection failure lifecycle
- MCP tool handlers dedicated to projection failure lifecycle
- tool schemas dedicated to projection failure lifecycle

---

## 7.2 Simplification candidates

These should likely be simplified rather than deleted:

### `src/ctxledger/workflow/service.py`

Remove:
- projection enums and models
- projection fields from resume payloads
- projection failure state handling
- projection warning generation

Keep:
- workspace/workflow/attempt/checkpoint/verify lifecycle
- completion memory bridge behavior
- canonical resume computation

### `src/ctxledger/memory/service.py`

Remove:
- projection-derived freshness inputs used only for ordering

Keep:
- ordering by workflow/attempt/checkpoint/episode signals
- lexical/semantic memory behavior

### `src/ctxledger/runtime/serializers.py`

Remove:
- serialized `projections`
- serialized `closed_projection_failures`
- projection-history serializers

Keep:
- workflow resume serialization
- memory serializers
- runtime introspection serializers

### `src/ctxledger/server.py` and response builders

Remove:
- projection-history response builders
- projection-failure action response builders
- projection-specific delegation methods

Keep:
- workflow resume response
- runtime introspection
- memory and workflow service access

### `src/ctxledger/db/__init__.py` and `src/ctxledger/db/postgres.py`

Remove:
- projection repository imports and implementations
- projection state/failure backing stores
- projection unit-of-work attributes

Keep:
- workspace/workflow/attempt/checkpoint/verify/memory repositories

---

## 7.3 Schema and data handling note

### Option A: code-only retirement in `v0.5.4`
- remove all projection-related code
- leave projection tables in place if they are harmless historical data
- fastest and lowest-risk option

### Option B: schema retirement in `v0.5.4`
- also remove obsolete projection tables/DDL references
- cleaner final state, but higher migration risk

### Recommendation
Use **Option A** unless schema migration infrastructure is already mature and tested.  
The primary goal is to remove active projection behavior before `v0.6.0`, not to maximize schema cleanliness in one release.

---

## 8. Risk analysis

## Risk 1: Hidden coupling in workflow resume

### Description
Projection fields may still be assumed by serializers, tests, or response builders.

### Mitigation
- remove user-facing surfaces first
- then remove internal fields in one coordinated pass
- rerun focused resume serialization and workflow tests after each layer

---

## Risk 2: Memory ordering regressions

### Description
Memory freshness ordering may currently depend on projection-derived timestamps.

### Mitigation
- explicitly redefine ordering around non-projection signals
- update tests to lock in expected ordering after simplification
- compare before/after behavior for non-projection cases

---

## Risk 3: Runtime introspection drift

### Description
Projection routes/tools may disappear from runtime registration but still remain in docs/tests/schemas.

### Mitigation
- remove route/tool registration and schema definitions together
- verify introspection outputs directly
- update HTTP/MCP tests in the same change set

---

## Risk 4: Incomplete test cleanup

### Description
Residual imports, fixture names, or string constants may still reference projection artifacts and block test collection.

### Mitigation
- run repository-wide grep for projection-related identifiers after edits
- treat collection errors as a first-class validation step
- update arbitrary fixture strings where necessary instead of deleting useful tests

## Risk 5: Accidental regression in non-projection behavior

### Description
Because projection remnants are spread across shared workflow, runtime, serializer, and persistence code, an overly broad cleanup could unintentionally change canonical workflow or memory behavior.

### Mitigation
- apply the non-impact boundaries in this plan as hard decision rules
- remove public projection surfaces before editing shared internals
- prefer deleting projection-only branches over refactoring adjacent non-projection code
- validate focused workflow, runtime, memory, and persistence suites after each cleanup slice
- defer any change that improves design quality but is not required for projection removal

## Risk 6: Cleanup expands into a redesign

### Description
The repository still contains multiple kinds of projection residue, and there is a natural temptation to use `v0.5.4` to redesign payloads, persistence contracts, or runtime layering more broadly.

### Mitigation
- keep `v0.5.4` release work framed as removal, not replacement
- use the concise release-oriented task list as the authoritative execution scope
- treat any proposal that introduces new concepts, payload structures, or abstraction layers as a follow-up candidate for `v0.6.0`, not part of the cleanup release

---

## 9. Acceptance criteria

`v0.5.4` is complete when all of the following are true:

1. no active CLI command exists for writing local `.agent/` resume projections
2. no active workflow resume output includes projection sections or projection failure history
3. no active HTTP route exists for projection failure ignore/resolve/history
4. no active MCP tool exists for projection failure ignore/resolve
5. workflow/memory runtime introspection does not list projection surfaces
6. workflow-domain and persistence code no longer require projection state/failure models to function
7. tests pass after projection-specific cleanup
8. docs no longer describe `.agent/` projection output as a supported feature
9. repository-wide grep for `.agent/` and core projection identifiers shows only intentional historical references, if any
10. focused regression validation confirms that non-projection workflow, memory, runtime, and persistence behavior remains unchanged aside from deleted projection-specific surfaces

### Acceptance grep checklist

The active codebase should no longer contain these in supported runtime paths:

- `.agent/resume.json`
- `.agent/resume.md`
- `write-resume-projection`
- `record_resume_projection`
- `ProjectionSettings`
- `ProjectionStatus`
- `ProjectionArtifactType`
- `ProjectionInfo`
- `RecordProjectionStateInput`
- `projection_failures_ignore`
- `projection_failures_resolve`
- `closed_projection_failures`

Historical planning documents may remain if clearly non-normative.

---

## 10. Recommended execution order

1. inventory all remaining projection remnants
2. remove user-facing CLI surface
3. remove HTTP/MCP projection surfaces
4. simplify serializers and server response builders
5. remove workflow-domain projection models
6. remove persistence repositories and unit-of-work wiring
7. update memory ordering logic
8. clean tests
9. clean docs
10. run full validation

This order minimizes time spent maintaining compatibility for already-deleted public surfaces.

---

## 11. Suggested commit breakdown

### Commit 1
Remove CLI, HTTP, and MCP projection-facing surfaces

### Commit 2
Remove projection models and workflow/persistence wiring

### Commit 3
Update tests and coverage targets for non-projection architecture

### Commit 4
Clean docs and release notes for `v0.5.4`

Optional:
### Commit 5
Schema cleanup, only if deliberately included

---

## 12. Validation plan

## 12.1 Fast verification
- repo grep for projection identifiers
- import/test collection check
- focused workflow resume tests
- focused runtime introspection tests

## 12.2 Regression verification
- workflow service tests
- server tests
- MCP handler tests
- PostgreSQL persistence tests
- memory service tests

## 12.3 Final verification
- full test suite
- coverage run
- manual inspection of:
  - CLI help
  - runtime introspection payloads
  - resume response payload shape

### Recommended validation command groups

#### Group A — Fast collection and surface checks
- run test collection first to catch removed-import regressions early
- run focused CLI/server/MCP tests after surface deletion
- verify CLI help and runtime introspection outputs manually or via tests

#### Group B — Core workflow and memory regression checks
- run workflow service tests
- run memory service tests
- run serialization/response-builder tests
- confirm resume payload shape changes are reflected consistently

#### Group C — Persistence regression checks
- run in-memory persistence tests
- run PostgreSQL repository tests
- run PostgreSQL integration tests that remain after projection cleanup
- confirm non-projection persistence behavior is unchanged

#### Group D — Closeout checks
- run full test suite
- run coverage
- run final repository grep for deprecated projection identifiers
- review docs diffs to ensure no active projection guidance remains

## 12.4 Execution checklist

### Pre-change checklist
- confirm the work is happening on a dedicated `v0.5.4` cleanup branch
- confirm the repository is clean or that any unrelated local edits are committed or stashed
- confirm current tests are green enough to establish a baseline for comparison
- capture a baseline inventory of projection-related residue with repository grep
- note any historical database tables or compatibility concerns before code deletion begins

### Surface-removal checklist
- remove CLI exposure for `write-resume-projection`
- remove projection-specific HTTP routes
- remove projection-specific MCP tools
- remove projection-specific runtime introspection entries
- remove projection fields from active workflow resume output and serialization
- rerun focused surface validation before proceeding deeper

### Core-removal checklist
- remove projection domain types and inputs
- remove projection repository interfaces and implementations
- remove projection wiring from in-memory and PostgreSQL unit-of-work construction
- simplify workflow resume logic to canonical state only
- simplify memory freshness ordering to non-projection signals only
- rerun focused workflow, memory, and persistence validation before test cleanup

### Test and documentation checklist
- delete projection-dedicated tests
- update remaining tests to remove projection imports and assertions
- update current-state docs to remove `.agent` projection guidance
- update changelog or release-note material for `v0.5.4`
- rerun full validation and final grep after documentation cleanup

## 12.5 Rollback strategy

### Rollback goals
If cleanup work introduces regressions, the team should be able to:
- restore the last known-good public workflow and memory behavior quickly
- isolate whether the breakage came from surface deletion, model deletion, or persistence simplification
- avoid partial reintroduction of the old `.agent` projection subsystem unless absolutely necessary

### Recommended rollback approach
1. keep the cleanup split across small commits aligned to the milestone/commit plan
2. if a regression appears, revert the most recent cleanup slice first rather than abandoning the full branch immediately
3. prefer reverting:
   - surface-removal commit
   - then core-model/persistence removal commit
   - then test/doc cleanup commit
   in reverse order of introduction
4. only restore deprecated projection internals if preserving canonical workflow behavior truly requires it
5. if a bug is limited to serialization or route registration, prefer a narrow corrective patch over broad rollback

### Practical rollback checkpoints
Maintain restorable checkpoints at:
- before Milestone 1 surface removal
- after Milestone 1 surface removal
- after Milestone 2 core model and persistence removal
- after Milestone 3 test stabilization
- final pre-release validation state

### Rollback validation
After any rollback:
- rerun focused workflow resume tests
- rerun focused runtime introspection tests
- rerun focused memory and persistence regression tests relevant to the reverted slice
- confirm the repository no longer sits in a partially deleted inconsistent state

---

## 13. Recommended next implementation step

Start with **Milestone 1 — Surface removal** and complete it before touching deeper persistence internals:

1. remove `write-resume-projection`
2. remove projection-failure HTTP/MCP routes and schemas
3. remove projection fields from serialized workflow resume output
4. update runtime introspection expectations
5. run the fast verification group

After that, proceed to **Milestone 2 — Core model and persistence removal** in one coordinated branch of work so that workflow models, serializers, repositories, and tests stay aligned.

That sequencing immediately aligns the public surface with the product direction and reduces downstream cleanup complexity.

## 13.1 Concise release-oriented task list

### Release task group 1 — Public surface removal
- remove `write-resume-projection` from CLI parsing and dispatch
- remove projection sections from workflow resume CLI output
- remove projection-related counters and failure output from CLI status/reporting paths
- remove projection-failure HTTP endpoints
- remove projection-failure MCP tools and schemas
- update runtime introspection outputs to reflect the reduced supported surface
- avoid any unrelated changes to still-supported CLI, HTTP, or MCP behavior while doing so
- complete the Milestone 1 implementation checklist before opening model/persistence deletions
- run the Milestone 1 focused validation commands and keep the results as the baseline gate for proceeding

### Release task group 2 — Core model and persistence cleanup
- remove projection enums, records, and input types from workflow domain code
- remove projection-related fields from workflow resume payloads and response builders
- remove in-memory projection repositories and backing-store state
- remove PostgreSQL projection repositories and unit-of-work wiring
- simplify memory freshness ordering to canonical non-projection workflow signals
- stop immediately if a proposed change would alter non-projection workflow or memory semantics rather than merely removing projection coupling

### Release task group 3 — Test stabilization
- delete projection-dedicated tests
- update remaining tests to remove projection imports and assertions
- rename incidental projection fixture strings where coverage should be preserved
- rerun focused workflow, runtime, memory, and persistence suites
- rerun the full suite and coverage checks

### Release task group 4 — Documentation and closeout
- remove current-state `.agent` projection guidance from docs
- remove projection-failure endpoint references from security/deployment/API docs
- add a `v0.5.4` changelog note for the cleanup
- run final grep-based residue verification
- prepare the branch for release closeout once validation is complete

---

## 14. Summary

`v0.5.4` should be a focused cleanup release that fully removes the remaining remnants of repository-local `.agent/` projection output before `v0.6.0` begins.

The safest and most efficient approach is:

- remove user-facing surfaces first
- then delete projection-specific internals
- preserve canonical workflow and memory behavior
- keep schema retirement optional unless migration work is already well-controlled

This leaves the repository smaller, easier to reason about, and better prepared for `v0.6.0`.

---

## Appendix A: Repository-informed residual inventory

This appendix captures the currently visible projection-related residue that should guide execution ordering.  It is intentionally operational and file-oriented so implementation work can proceed without re-discovering the same footprint repeatedly.

### A.1 Active code paths that still expose projection concepts

#### `src/ctxledger/__init__.py`
Residuals currently include:
- `write-resume-projection` command dispatch
- projection-related sections in `resume-workflow` text output
- `closed_projection_failures` rendering
- projection-related stats/failure output fields

Why it matters:
- this is direct user-facing surface area
- removing it early reduces compatibility pressure on internal code

#### `src/ctxledger/http_app.py`
Residuals currently include:
- imports for projection-failure HTTP handlers
- route registration for:
  - closed projection failures
  - projection failure ignore
  - projection failure resolve

Why it matters:
- these routes keep deprecated projection lifecycle operations publicly reachable

#### `src/ctxledger/runtime/http_runtime.py`
Residuals currently include:
- projection-failure tools in `registered_tools()`
- projection-failure schemas in `tool_schema()`
- projection-failure dispatch wiring in `dispatch_tool()`
- projection-failure route registration in `register_http_runtime_handlers()`

Why it matters:
- runtime introspection continues to advertise projection features as supported

#### `src/ctxledger/runtime/http_handlers.py`
Residuals currently include:
- projection-failure route constants
- closed projection failure path parsing
- projection-type parsing helper
- projection-failure request parsing
- projection-failure HTTP handlers
- projection-related exports

Why it matters:
- these are isolated surface adapters and are strong delete candidates

#### `src/ctxledger/mcp/tool_handlers.py`
Residuals currently include:
- `ProjectionArtifactType` import
- projection-type parsing helper
- projection-failure ignore tool handler
- projection-failure resolve tool handler
- workflow-service calls for projection failure mutation

Why it matters:
- these handlers are feature-isolated and should be removed with the HTTP surface cleanup

#### `src/ctxledger/mcp/tool_schemas.py`
Residuals currently include:
- `ProjectionArtifactType` import
- projection-failure action schemas

Why it matters:
- schema deletion should happen in the same patch as handler deletion to avoid introspection drift

---

### A.2 Workflow and serialization internals that still model projections

#### `src/ctxledger/workflow/service.py`
Residuals currently appear to include:
- projection enums and dataclasses
- projection-related input models
- projection-bearing workflow resume fields
- projection failure lifecycle support
- projection-related stats and warning concepts

Why it matters:
- this is the main domain root of projection coupling
- it should be simplified only after public surfaces are removed

#### `src/ctxledger/runtime/serializers.py`
Residuals currently include:
- `projections` in serialized workflow resume payloads
- optional inclusion of `closed_projection_failures`
- dedicated closed projection failure serializer helpers

Why it matters:
- payload simplification must stay synchronized with workflow resume model cleanup and test updates

#### `src/ctxledger/runtime/server_responses.py`
Residuals currently appear to include:
- workflow resume response paths that still know about closed projection failures
- dedicated projection failure response builders/history builders
- projection-type imports

Why it matters:
- response builders should be reduced once workflow resume serialization has been simplified

#### `src/ctxledger/server.py`
Residuals likely include:
- delegation methods or builder hooks related only to projection-failure responses/history

Why it matters:
- these should disappear after response-builder cleanup so the server surface matches supported capabilities

---

### A.3 Persistence and unit-of-work residue

#### `src/ctxledger/db/__init__.py`
Residuals currently include:
- projection repository imports/exports
- in-memory projection state repository
- in-memory projection failure repository
- in-memory store backing maps for projection state/failure
- unit-of-work wiring for projection repositories

Why it matters:
- these are central cleanup targets for code-only retirement of the projection subsystem

#### `src/ctxledger/db/postgres.py`
Residuals currently include:
- projection repository imports
- PostgreSQL projection state repository
- PostgreSQL projection failure repository
- SQL against projection tables
- unit-of-work wiring for projection repositories

Why it matters:
- this is the largest persistence-side deletion area
- non-projection PostgreSQL behavior should be preserved while these repositories are removed

#### Historical schema note
Projection tables may still exist in the database schema even after code removal.

Operational interpretation:
- code deletion should proceed first
- schema/table retirement can remain optional for `v0.5.4`
- if tables are left in place, they should be treated as historical compatibility residue rather than supported runtime features

---

### A.4 Memory-ordering coupling

#### `src/ctxledger/memory/service.py`
Residuals currently include projection-derived freshness signals such as conceptual fields for:
- latest projection canonical update
- latest projection successful write
- open projection failure count
- projection-backed ordering inputs sourced from unit-of-work workflow lookup

Why it matters:
- this is not user-facing by itself, but it couples memory retrieval behavior to the deprecated projection subsystem
- it should be simplified to canonical workflow and episode signals only

---

### A.5 Compatibility residue package

#### `src/ctxledger/projection/writer.py`
Residual currently appears to be a removal stub that still references the old local `.agent` projection writer behavior.

Why it matters:
- if no supported import-compatibility requirement remains for `v0.5.4`, this module should be deleted entirely
- retaining the stub beyond the cleanup release would continue to preserve conceptual surface area for a removed feature

---

### A.6 Test residue clusters

#### `tests/test_cli.py`
Residuals likely include:
- `write-resume-projection` command tests
- `.agent/resume.json` and `.agent/resume.md` expectations
- projection fields/counters in stats and resume output expectations
- projection failure reporting assertions

#### `tests/test_server.py`
Residuals likely include:
- projection route expectations
- projection tool/runtime introspection expectations
- projection config/model imports in fixtures

#### `tests/test_mcp_tool_handlers.py`
Residuals likely include:
- projection-failure tool handler coverage
- projection-type argument parsing expectations

#### `tests/test_postgres_integration.py`
Residuals likely include:
- projection model/config imports
- projection-specific persistence or resume behavior tests

#### `tests/test_coverage_targets.py`
Residuals likely include:
- projection-derived freshness keys used only to exercise branch coverage
- projection-named fixtures/strings that can be renamed instead of deleted

#### Dedicated projection tests
Any test file dedicated solely to projection writing or projection lifecycle behavior should be treated as a likely full deletion target.

Why this cluster matters:
- test collection failures are one of the highest-probability regressions during cleanup
- delete or rewrite test residue in lockstep with the corresponding production-code surface

---

### A.7 Documentation residue clusters

#### Current-state docs that should be updated
Priority review targets:
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/SECURITY.md`
- `docs/CHANGELOG.md`

Likely residue:
- projections described as active architecture/runtime behavior
- projection-failure endpoint guidance
- `.agent` examples
- release evidence or changelog entries that need cleanup context

#### Historical docs that may remain
Historical planning documents can remain if they are clearly understood as historical and not current product guidance.

Why it matters:
- documentation should stop advertising deleted surfaces
- historical planning artifacts do not need aggressive deletion if they are non-normative

---

### A.8 Recommended practical use of this appendix

Use this appendix as the working removal map:

1. clear Section A.1 first
2. then simplify Section A.2 and A.3 together
3. then update Section A.4 and A.6 together
4. finish with Section A.7 and final grep validation

That order minimizes false starts and keeps public-surface cleanup ahead of deeper internal deletions.