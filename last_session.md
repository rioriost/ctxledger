# ctxledger last session

## Summary
`0.5.0` is closed out as a **refactoring milestone** and tagged as `v0.5.0`.

A short `0.5.1` follow-up is now planned before `0.6.0`.

`0.5.1` is intended as a **targeted connection-pooling refactoring and runtime hardening step** focused on adopting `psycopg-pool` for PostgreSQL-backed execution paths.

This work loop made substantial progress on that hardening step:
- PostgreSQL unit-of-work construction now requires an explicit shared pool instead of silently creating ad hoc pools
- CLI PostgreSQL bootstrap paths were refactored to own and close shared pools explicitly
- server/runtime bootstrap paths were corrected so HTTP/runtime wiring can initialize a real workflow service again
- helper, CLI, coverage-target, and server tests were updated to reflect the new pool ownership rules
- resume-related PostgreSQL indexes were added to the canonical schema for verify report and projection-failure lookup paths

`0.6.0` remains the next feature milestone after that, and its scope is:

- hierarchical memory retrieval
- summary layers
- relation-aware context assembly
- more multi-layer `memory_get_context` behavior

## Final 0.5.0 status

### Validation
- focused validation remained green throughout the refactoring wave
- final full-suite result:
  - `python -m pytest -q`
  - `799 passed, 1 skipped`

### Skipped test
The single skipped test remains expected:
- real OpenAI integration requires `OPENAI_API_KEY`

### Release judgment
- internal `0.5.0` release judgment: **GO**
- release tag created:
  - `v0.5.0`

## What 0.5.0 completed
`0.5.0` delivered meaningful duplication reduction and internal cleanup across both `src/` and `tests/` without intentionally changing the supported product surface.

High-value areas cleaned up included:
- CLI bootstrap and formatting helpers
- server test setup and handler builders
- MCP resource parsing helpers
- HTTP handler request/error helpers
- server runtime introspection helper paths
- MCP RPC parsing helpers
- in-memory repository query helpers
- PostgreSQL parsing helpers
- configuration parsing helpers
- HTTP app request helpers
- runtime server response helpers

Net effect:
- cleaner local structure
- reduced repeated logic
- preserved behavior
- strong test-backed confidence for future work

## 0.5.1 immediate direction

### Core implementation direction
Before beginning `0.6.0` feature development, the next work loop should implement PostgreSQL connection pooling with `psycopg-pool`.

Current intent:
- keep PostgreSQL canonical
- preserve the existing unit-of-work and repository boundaries
- replace per-unit-of-work fresh connection creation with pooled acquisition
- improve runtime efficiency and connection lifecycle discipline
- align implementation with the architecture documentation that already describes a PostgreSQL connection pool

### Why 0.5.1 is being added
This follow-up milestone was triggered by investigation into a `workflow_resume` timeout seen at the start of the current session.

Current judgment after the latest investigation:
- the `workflow_resume` application logic itself still does not look inherently complex enough to be the primary bottleneck
- the previous HTTP/runtime failure mode was at least partly explained by server bootstrap wiring leaving `workflow_service` uninitialized on the HTTP path
- that wiring issue has now been corrected, and both CLI and HTTP/runtime dispatch paths can successfully return resume data for the currently inspected workflow
- added debug-level stage timing in `WorkflowService.resume_workflow()` currently suggests the local lookup stages complete quickly under the present dataset
- the current PostgreSQL path no longer silently creates ad hoc pools through the unit-of-work factory
- connection pooling remains a worthwhile refactoring and hardening step even though the original timeout is **not currently reproduced** in the latest local checks

### 0.5.1 plan document
The new implementation plan for this work is:

- `docs/plans/connection_pooling_0_5_1_plan.md`

### Recommended immediate next steps for 0.5.1
1. update `docs/roadmap.md` to introduce `0.5.1`
2. align `docs/architecture.md` with the planned/actual pool lifecycle wording
3. keep refining pool ownership boundaries for:
   - server bootstrap
   - CLI bootstrap
   - PostgreSQL unit-of-work creation
4. confirm schema/index application on the target database(s), especially the newly added resume-related indexes
5. investigate whether any remaining `workflow_resume` timeout depends on:
   - a different workflow instance
   - a different database state
   - a different transport/context-server timeout budget
   - a cold-start/bootstrap path rather than the steady-state resume query path
6. run focused workflow and PostgreSQL integration validation again after any further runtime or schema changes

## 0.6.0 starting direction

### Core implementation direction
For `0.6.0`, hierarchical memory should be implemented with PostgreSQL still remaining the canonical system of record.

As part of the implementation foundation, `0.6.0` should add **Apache AGE** to PostgreSQL and use **Cypher** as a supporting mechanism for hierarchical memory and relation-aware traversal.

Current intent:
- keep PostgreSQL canonical
- add Apache AGE as an extension layer for graph-oriented memory relationships
- use Cypher to assist hierarchical and relation-aware retrieval flows
- avoid turning `0.6.0` into a broad architecture rewrite beyond what hierarchical memory requires

### Why AGE is included in 0.6.0
The current judgment is that AGE should be added in `0.6.0` as a forward-looking foundation for:
- graph-structured memory relations
- top-down or relation-aware traversal
- future expansion beyond plain similarity retrieval
- cleaner support for hierarchical retrieval than forcing all such behavior into ad hoc relational assembly

This does **not** change the rule that PostgreSQL remains canonical.

## Mnemis direction
Do **not** try to align implementation with Mnemis during `0.6.0`.

Instead:
- `0.6.0` should focus on getting ctxledger’s own hierarchical memory implementation working first
- `0.7.0` should explicitly evaluate whether ctxledger should move closer to Mnemis-style design

Reference repository for later review:
- `https://github.com/microsoft/Mnemis`

Useful Mnemis note for later:
- Mnemis emphasizes dual-route retrieval on hierarchical graphs
- that makes it relevant to `0.7.0` design evaluation
- but it should not distort the execution scope of `0.6.0`

## Recommended later next steps for 0.6.0
After `0.5.1` pooling work is complete:

1. define the minimal hierarchical memory data model needed for `0.6.0`
2. identify where Apache AGE must be introduced:
   - schema
   - local/dev setup
   - repository/service boundaries
   - tests
3. decide which memory relations belong in graph form first
4. define the first `memory_get_context` hierarchical retrieval slice
5. add focused tests before broad expansion
6. keep `0.7.0` Mnemis comparison as a separate future evaluation step

## Important files for next session
- `docs/roadmap.md`
- `docs/architecture.md`
- `docs/plans/connection_pooling_0_5_1_plan.md`
- `docs/plans/hierarchical_memory_0_6_0_plan.md`
- `last_session.md`
- `src/ctxledger/server.py`
- `src/ctxledger/runtime/server_factory.py`
- `src/ctxledger/runtime/protocols.py`
- `src/ctxledger/http_app.py`
- `src/ctxledger/workflow/service.py`
- `src/ctxledger/db/postgres.py`
- `src/ctxledger/db/__init__.py`
- `src/ctxledger/config.py`
- `schemas/postgres.sql`
- `README.md`

## Notes on local workspace state
Tracked refactoring work has been committed.

Current investigation notes:
- local CLI `resume-workflow` against workflow `86b84bab-05cc-4405-b4dc-536e6f0b7e7e` succeeded once `CTXLEDGER_DATABASE_URL` was provided
- local HTTP/runtime dispatch for the same workflow also succeeded after restoring default workflow-service-factory wiring in `create_server()`
- the previously observed HTTP `503 server_not_ready` state was caused by bootstrap wiring leaving `workflow_service_factory` unset on the server path
- debug-level timing added to `WorkflowService.resume_workflow()` is now available for future reproduction attempts
- temporary local probe scripts used during this investigation were removed after use
- no reliable local reproduction of the original `workflow_resume` timeout remains at this point

Known remaining local/generated artifacts may still exist, such as:
- coverage output
- local certificate material

These are not part of the intended milestone record unless explicitly needed later.