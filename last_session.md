# ctxledger last session

## Summary

Continued the `0.5.2` `workflow_resume` timeout hardening investigation in a live Docker-authenticated environment.

This session confirmed that the previously hardened resume path now succeeds end-to-end in repeated real MCP workflow scenarios, removed a concrete `workspace_id` vs `workflow_instance_id` runtime misuse path, aligned focused regression tests, and uncovered a separate deployed logging/runtime issue that currently suppresses the new resume timing debug events in the live uvicorn process even when `CTXLEDGER_LOG_LEVEL=debug` is present.

## What changed in this session

Runtime, test, and local operator-support changes were made around resume correctness and live observation.

Key updates:
- fixed workspace resume fallback identifier forwarding in `src/ctxledger/runtime/server_responses.py`
- updated focused regression expectations in `tests/test_coverage_targets.py`
- added a local Docker Compose override for debug logging in:
  - `docker/overrides/debug-logging.yml`
- attempted a deployed logging initialization fix in:
  - `src/ctxledger/http_app.py`

## Main implementation and investigation results

### 1. A real identifier-category bug was confirmed and fixed

A concrete runtime misuse path was found in `build_workspace_resume_resource_response()`.

In the non-UoW fallback branch, the code was passing:

- `resume_result.workspace.workspace_id`

into:

- `build_workflow_resume_response(...)`

That function expects a `workflow_instance_id`, not a `workspace_id`.

This was fixed so the fallback branch now forwards:

- `resume_result.workflow_instance.workflow_instance_id`

This aligns the runtime with the `0.5.2` goal of reducing ambiguity and preventing workspace/workflow UUID misuse from reappearing in resume-oriented paths.

### 2. Focused regression tests were aligned with the fixed behavior

After the runtime identifier fix, several focused coverage tests still encoded the old incorrect expectation that the workspace resume fallback would forward a `workspace_id`.

Those expectations were updated in `tests/test_coverage_targets.py`, including:
- the resume-result branch test
- the workspace mismatch branch
- the non-success propagation branch

This keeps regression coverage aligned with the corrected runtime behavior.

### 3. The live authenticated MCP workflow path now succeeds repeatedly

A real authenticated local stack was brought up using:
- main Docker Compose
- small-auth overlay
- observability overlay

After obtaining the actual bearer token, the live smoke workflow scenario succeeded end to end.

Representative successful live workflow runs produced:

#### First authenticated smoke run
- `workspace_id`: `a2451772-290a-464a-9c88-8aca539afb56`
- `workflow_instance_id`: `e49fb4ca-53b2-4e1e-82fd-5e55d730caa2`
- `attempt_id`: `ef97cd4d-9ab3-4f0c-8908-5fca1345cf65`

#### Debug-override smoke run
- `workspace_id`: `20271329-e2f2-441f-aa56-e1fc6f14cdec`
- `workflow_instance_id`: `1b07056f-d4ac-4c01-8322-4d41d8dd4bce`
- `attempt_id`: `961fbe3d-6681-4046-8e05-146a987620bd`

#### Post-fix rebuild smoke run
- `workspace_id`: `d4a12cd4-92e4-4fb2-bf7c-b7f732af8053`
- `workflow_instance_id`: `81c04a31-a7b5-448d-9c82-c22f056f65ce`
- `attempt_id`: `46ef99a9-59d8-4a4b-b833-89356db63349`

Successful operations in these runs included:
- `initialize`
- `tools/list`
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `resources/read` for workspace resume
- `resources/read` for workflow detail
- `workflow_complete`

This is strong evidence that the current live authenticated stack can complete `workflow_resume` successfully in a representative workflow scenario.

### 4. The original timeout symptom did not reproduce in the live smoke path

This is the most important live operational result from the session.

Repeated authenticated end-to-end workflow runs did **not** reproduce:
- MCP timeout
- HTTP timeout
- visible resume latency warning
- resume-path failure

Current evidence suggests:
- the `0.5.2` hardening work substantially improved the main path
- the earlier timeout may be scenario-specific, load-sensitive, or already mitigated
- the timeout-prone case is not currently reproducible in the tested local Docker stack with the smoke scenario

### 5. A separate deployed logging/runtime bug is now the main blocker to deeper timing analysis

Even after enabling a debug logging override in Docker, the live `ctxledger-server-private` process did not emit the expected resume-stage debug timing events.

The session confirmed all of the following:

#### Environment/settings side
Inside `ctxledger-server-private`:
- `CTXLEDGER_LOG_LEVEL=debug`
- `load_settings().logging.level.value == "debug"`
- `load_settings().logging.structured == True`

So the environment variables and settings parsing are correct.

#### Live effective logger state
Inside the running server container, the effective logger levels remained:
- root logger: `30` (`WARNING`)
- `ctxledger.workflow.service`: `30`
- `ctxledger.server`: `30`

Observed logger details:
- root logger level: `30`
- root handlers: `[]`
- workflow-service logger level: `0` (`NOTSET`)
- workflow-service propagate: `True`

This means the workflow-service logger is not independently suppressing debug; it is simply inheriting `WARNING` from the root logger.

#### Control proof
In a one-off Python process inside the same container, manually running:

- `logging.basicConfig(level=logging.DEBUG, force=True)`

correctly changed:
- root effective level to `10`
- workflow-service effective level to `10`
- `logger.isEnabledFor(logging.DEBUG)` to `True`

So:
- Python logging semantics are fine
- the workflow logger is fine
- the missing piece is process-time application/persistence of root logging configuration in the deployed uvicorn path

### 6. Module-import startup behavior is involved, but the final deployed fix is still incomplete

The live container runs:

- `uvicorn ctxledger.http_app:app --host 0.0.0.0 --port 8080`

Because of that, the module-level app creation path matters.

A follow-up change was attempted in `src/ctxledger/http_app.py` so `create_default_fastapi_app()` would:
1. load settings
2. create the server
3. run `server.startup()`
4. return the app

This produced duplicate startup log lines in the live container, confirming earlier startup invocation was occurring.

A fresh one-off import inside the container also showed that this import path can now configure logging correctly in a short-lived process:
- root level became `10`
- root handlers were present

However, the long-running serving process still showed effective logger levels at `WARNING`, and the expected `resume_workflow ...` debug events were still missing from live server logs.

So the remaining issue is now best understood as a **deployed uvicorn logging/runtime interaction**, not a missing environment variable or a missing logger in the workflow service itself.

### 7. The attempted import-time startup approach also exposed an operator/runtime smell

A fresh one-off import of `ctxledger.http_app` in the container produced a cleanup warning related to pool finalization:

- `ConnectionPool.__del__`
- `PythonFinalizationError: cannot join thread at interpreter shutdown`

This happened because server startup and pool creation occurred during import in a short-lived process without a normal shutdown lifecycle.

That is a useful signal that import-time startup may not be the right final design for production/runtime correctness, even though it helped narrow the logging issue.

## Current runtime/operational conclusions

### What is now strongly supported
- live authenticated `workflow_resume` works in the tested local stack
- the `workspace_id` vs `workflow_instance_id` runtime misuse path in workspace resume fallback is fixed
- repeated smoke workflow scenarios do not reproduce the original timeout symptom
- the main remaining blocker to deeper stage-by-stage timing analysis is a distinct deployed logging/runtime issue

### What remains unresolved
- why the long-running uvicorn serving process retains effective root logging at `WARNING` despite:
  - `CTXLEDGER_LOG_LEVEL=debug`
  - correct settings parsing
  - successful startup invocation
- whether the original timeout can still be reproduced under:
  - heavier data volume
  - different caller timeout budgets
  - higher pool contention
  - a more pathological projection/failure state

## Tests and live validation completed

### Source-level validation
- diagnostics were clean after edits to:
  - `src/ctxledger/runtime/server_responses.py`
  - `tests/test_coverage_targets.py`
  - `src/ctxledger/http_app.py`
  - `docker/overrides/debug-logging.yml`

### Live environment validation
The Docker-authenticated stack was observed healthy:
- `ctxledger-traefik`
- `ctxledger-server-private`
- `ctxledger-grafana`
- `ctxledger-auth-small`
- `ctxledger-postgres`

### Live workflow validation
Multiple authenticated workflow smoke scenarios completed successfully with:
- tool calls succeeding
- `workflow_resume` succeeding
- workspace and workflow resource reads succeeding
- workflow completion succeeding

## Important files for next session

Primary runtime and investigation files:
- `last_session.md`
- `src/ctxledger/runtime/server_responses.py`
- `src/ctxledger/http_app.py`
- `src/ctxledger/server.py`
- `src/ctxledger/workflow/service.py`
- `src/ctxledger/db/postgres.py`

Primary validation/support files:
- `tests/test_coverage_targets.py`
- `tests/test_workflow_service.py`
- `tests/test_postgres_db.py`
- `docker/overrides/debug-logging.yml`
- `docker/docker-compose.yml`
- `docker/docker-compose.small-auth.yml`
- `scripts/mcp_http_smoke.py`

Planning context:
- `docs/plans/workflow_resume_timeout_0_5_2_plan.md`

## Specific code observations to remember

- `build_workspace_resume_resource_response()` fallback branch must forward `workflow_instance_id`, not `workspace_id`
- `ResumeWorkflowInput.include_closed_projection_failures` remains in place and main resume still excludes closed history by default
- the live authenticated workflow scenario currently completes without reproducing timeout
- in the running container:
  - `CTXLEDGER_LOG_LEVEL=debug` is present
  - settings load as debug
  - but root logger effective level remains `WARNING`
- a fresh one-off Python process inside the same container can configure logging correctly with `basicConfig(... DEBUG ...)`
- the remaining observability issue is therefore specific to the long-running uvicorn serving process/runtime initialization path
- the current `http_app.py` import-time startup change produced duplicate startup logs and exposed a pool finalization warning in short-lived imports, so treat that change as diagnostic/narrowing evidence rather than proven final architecture

## Remaining work / likely next focus

The original timeout symptom is no longer reproduced in the tested live smoke path, so the work should now be framed more carefully.

Recommended next actions:

1. Decide whether to treat the timeout-hardening objective as:
   - largely validated for the representative smoke path, with no current reproduction
   - or still requiring a more pathological reproduction scenario before closeout

2. Investigate the separate deployed logging/runtime bug:
   - determine why root effective logging remains `WARNING` in the live uvicorn serving process
   - inspect uvicorn logging initialization/override behavior
   - avoid relying on import-time startup if a cleaner lifecycle-safe fix exists

3. Once deployed debug visibility actually works, rerun the authenticated workflow scenario and collect:
   - `uow_enter_duration_ms`
   - `pool_checkout_duration_ms`
   - `session_setup_duration_ms`
   - `projection_lookup_duration_ms`
   - `projection_failure_lookup_duration_ms`
   - `response_assembly_duration_ms`
   - total `duration_ms`

4. If a timeout-prone scenario can be reproduced later, compare those timings with the actual caller/context timeout budget and only then decide whether additional query reshaping is still necessary.

## Validation status

This session should be treated as:
- runtime hardening still operational
- workspace/workflow identifier misuse path fixed
- focused tests aligned
- live authenticated resume success confirmed repeatedly
- original timeout symptom not currently reproducible in the tested smoke scenario
- deployed debug timing visibility still blocked by a separate logging/runtime issue

## Continuation note

Resume from the `0.5.2` live investigation with a split mindset:

1. do **not** assume the timeout is still reproducible
2. treat live smoke success as meaningful evidence that the hardening helped
3. next focus on the uvicorn/deployed logging suppression bug so stage timing debug events become visible in the real server process
4. after that, either:
   - close out timeout hardening as “not currently reproducible in representative live flow”
   - or design a more pathological reproduction scenario if stronger proof is still needed